import 'dart:typed_data';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:photo_manager/photo_manager.dart';
import 'package:tflite_flutter/tflite_flutter.dart';
import 'asset_photo_service.dart';

class TFLiteService {
  // Try multiple model paths for compatibility
  static const List<String> _modelPaths = [
    'assets/models/dinov2_vits14_embed.tflite',
    'assets/models/dinov2_vits14_embed_dynamic.tflite', 
    'assets/models/similarity_model_dynamic.tflite',
    'assets/models/dinov2_trained_float32.tflite', // Keep as last fallback
  ];
  // Default fallback size; actual size read from model at init
  static const int _defaultInputSize = 224;
  static const double _similarityThreshold = 0.8;

  Interpreter? _interpreter;
  bool _isInitialized = false;
  int _inputH = _defaultInputSize;
  int _inputW = _defaultInputSize;
  int _inputC = 3;

  Future<void> initialize() async {
    if (_isInitialized) return;

    // Try multiple models for compatibility
    Exception? lastError;
    for (final modelPath in _modelPaths) {
      debugPrint('TFLite: Trying model $modelPath');
      
      // Try multiple interpreter configurations for each model
      final attempts = <InterpreterOptions Function()>[
        // Default fast path
        () => InterpreterOptions()..threads = 4,
        // Simpler config (no explicit threads)
        () => InterpreterOptions(),
        // NNAPI-enabled path for some devices
        () => InterpreterOptions()..useNnApiForAndroid = true,
      ];

        for (final buildOptions in attempts) {
          try {
            final options = buildOptions();
            _interpreter =
                await Interpreter.fromAsset(modelPath, options: options);
            
            // Determine input/output shapes and resize if needed
            var inShape = _interpreter!.getInputTensor(0).shape;
            // Expect NHWC. Some models ship with dynamic dims (-1) or 0.
            if (inShape.length == 4 &&
                (inShape[1] == -1 ||
                    inShape[2] == -1 ||
                    inShape[1] == 0 ||
                    inShape[2] == 0)) {
              // Use sensible default
              inShape = [1, _defaultInputSize, _defaultInputSize, 3];
              _interpreter!.resizeInputTensor(0, inShape);
              _interpreter!.allocateTensors();
            }

            if (inShape.length != 4) {
              throw Exception(
                  'Unexpected model input rank ${inShape.length}, expected 4D NHWC');
            }
            _inputH = inShape[1];
            _inputW = inShape[2];
            _inputC = inShape[3];

            // Output shape for logging
            final outShape = _interpreter!.getOutputTensor(0).shape;
            _isInitialized = true;
            debugPrint(
                'TFLite: Successfully loaded $modelPath. Input shape: $inShape, Output shape: $outShape');
            return;
          } catch (e) {
            debugPrint('TFLite: Failed to load $modelPath with options: $e');
            lastError = Exception(e.toString());
          }
        }
      }

    throw Exception(
        'Failed to load TFLite model: ${lastError ?? 'unknown error'}');
  }

  Future<Float32List> extractFeatures(AssetEntity asset) async {
    if (!_isInitialized || _interpreter == null) {
      throw Exception('TFLite service not initialized');
    }

    // Get image data
    final file = await asset.file;
    if (file == null) throw Exception('Could not load image file');

    // Decode and preprocess image
    final bytes = await file.readAsBytes();
    img.Image? image = img.decodeImage(bytes);
    if (image == null) throw Exception('Could not decode image');

    // Resize to model input size
    image = img.copyResize(image, width: _inputW, height: _inputH);

    // Convert to 4D NHWC nested list double[][][][]
    final input = _imageToNHWC(image);

    // Prepare output buffer matching tensor shape
    final outShape = _interpreter!.getOutputTensor(0).shape;
    final output = _zerosLike(outShape);
    _interpreter!.run(input, output);

    return _flattenOutput(output, outShape);
  }

  Future<Float32List> extractFeaturesFromAssetPhoto(
      AssetPhoto assetPhoto) async {
    if (!_isInitialized || _interpreter == null) {
      debugPrint(
          'TFLite: Service not initialized! _isInitialized: $_isInitialized, _interpreter: $_interpreter');
      throw Exception('TFLite service not initialized');
    }

    try {
      debugPrint('TFLite: Processing ${assetPhoto.name}');

      // Get image data from asset
      final bytes = await assetPhoto.originBytes;
      debugPrint('TFLite: Loaded ${bytes.length} bytes for ${assetPhoto.name}');

      // Decode and preprocess image
      img.Image? image = img.decodeImage(bytes);
      if (image == null) {
        debugPrint('TFLite: Failed to decode image ${assetPhoto.name}');
        throw Exception('Could not decode image ${assetPhoto.name}');
      }

      debugPrint('TFLite: Decoded image ${image.width}x${image.height}');

      // Resize to model input size
      image = img.copyResize(image, width: _inputW, height: _inputH);

      // Convert to 4D NHWC nested list
      final input = _imageToNHWC(image);

      // Prepare output buffer matching tensor shape
      final outShape = _interpreter!.getOutputTensor(0).shape;
      final output = _zerosLike(outShape);
      _interpreter!.run(input, output);

      final features = _flattenOutput(output, outShape);
      debugPrint('TFLite: Successfully processed ${assetPhoto.name}');
      return features;
    } catch (e) {
      debugPrint('TFLite: Error processing ${assetPhoto.name}: $e');
      rethrow;
    }
  }

  // Build 4D NHWC nested list expected by tflite_flutter's run()
  List<List<List<List<double>>>> _imageToNHWC(img.Image image) {
    // ImageNet mean/std used by DINOv2
    const meanR = 0.485, meanG = 0.456, meanB = 0.406;
    const stdR = 0.229, stdG = 0.224, stdB = 0.225;

    final batch = List<List<List<List<double>>>>.generate(1, (_) {
      return List<List<List<double>>>.generate(_inputH, (y) {
        return List<List<double>>.generate(_inputW, (x) {
          final pixel = image.getPixel(x, y);
          final r = (pixel.r / 255.0 - meanR) / stdR;
          final g = (pixel.g / 255.0 - meanG) / stdG;
          final b = (pixel.b / 255.0 - meanB) / stdB;
          return <double>[r, g, b];
        }, growable: false);
      }, growable: false);
    }, growable: false);
    return batch;
  }

  // Create a nested zero list matching the given shape (up to 4D)
  dynamic _zerosLike(List<int> shape) {
    if (shape.isEmpty) return 0.0;
    if (shape.length == 1) {
      return List<double>.filled(shape[0], 0.0);
    } else if (shape.length == 2) {
      return List.generate(shape[0], (_) => List<double>.filled(shape[1], 0.0));
    } else if (shape.length == 3) {
      return List.generate(
        shape[0],
        (_) =>
            List.generate(shape[1], (_) => List<double>.filled(shape[2], 0.0)),
      );
    } else if (shape.length == 4) {
      return List.generate(
        shape[0],
        (_) => List.generate(
          shape[1],
          (_) => List.generate(
              shape[2], (_) => List<double>.filled(shape[3], 0.0)),
        ),
      );
    }
    throw Exception('Unsupported output rank: ${shape.length}');
  }

  // Flatten nested list output to a 1D Float32List (drop batch and any size-1 dims)
  Float32List _flattenOutput(dynamic output, List<int> shape) {
    if (shape.isEmpty) return Float32List(0);
    // Treat only the first batch (batch dimension 0)
    final noBatchShape = shape.sublist(1);
    int flat = 1;
    for (final d in noBatchShape) {
      flat *= (d <= 0 ? 1 : d);
    }
    final res = Float32List(flat);
    int idx = 0;

    void walk(dynamic node, int dim) {
      if (dim == noBatchShape.length) return;
      if (dim == noBatchShape.length - 1) {
        for (final v in node as List) {
          res[idx++] = (v as num).toDouble();
        }
      } else {
        for (final child in node as List) {
          walk(child, dim + 1);
        }
      }
    }

    // Select first batch if provided as a list of batches
    final first = (output is List && shape[0] >= 1) ? output[0] : output;
    walk(first, 0);
    return res;
  }

  double calculateSimilarity(Float32List features1, Float32List features2) {
    // Cosine similarity
    double dotProduct = 0.0;
    double norm1 = 0.0;
    double norm2 = 0.0;

    for (int i = 0; i < features1.length; i++) {
      dotProduct += features1[i] * features2[i];
      norm1 += features1[i] * features1[i];
      norm2 += features2[i] * features2[i];
    }

    norm1 = math.sqrt(norm1);
    norm2 = math.sqrt(norm2);

    if (norm1 == 0.0 || norm2 == 0.0) return 0.0;

    return dotProduct / (norm1 * norm2);
  }

  bool areSimilar(Float32List features1, Float32List features2) {
    return calculateSimilarity(features1, features2) >= _similarityThreshold;
  }


  void dispose() {
    _interpreter?.close();
    _interpreter = null;
    _isInitialized = false;
  }
}

extension Reshape on List<double> {
  List<List<double>> reshape(List<int> shape) {
    if (shape.length != 2) {
      throw ArgumentError('Only 2D reshape is supported');
    }

    final rows = shape[0];
    final cols = shape[1];

    if (rows * cols != length) {
      throw ArgumentError('Invalid shape for reshape');
    }

    final result = List.generate(rows, (_) => List<double>.filled(cols, 0.0));

    for (int i = 0; i < length; i++) {
      result[i ~/ cols][i % cols] = this[i];
    }

    return result;
  }
}

extension ReshapeFloat32 on Float32List {
  dynamic reshape(List<int> shape) {
    if (shape.length == 2) {
      final rows = shape[0];
      final cols = shape[1];

      if (rows * cols != length) {
        throw ArgumentError('Invalid shape for reshape');
      }

      final result = List.generate(rows, (_) => Float32List(cols));

      for (int i = 0; i < length; i++) {
        result[i ~/ cols][i % cols] = this[i];
      }

      return result;
    }

    throw ArgumentError('Unsupported shape dimensions');
  }
}
