import 'dart:typed_data';
import '../services/asset_photo_service.dart';
import '../services/tflite_service.dart';
import 'embedding_runner.dart';

class TFLiteEmbeddingRunner implements EmbeddingRunner {
  final TFLiteService _tflite;
  TFLiteEmbeddingRunner(this._tflite);

  @override
  Future<void> initialize() => _tflite.initialize();

  @override
  Future<EmbeddingPair> extract(AssetPhoto photo) async {
    final full = await _tflite.extractFeaturesFromAssetPhoto(photo);
    // Simple background-masked proxy using a deterministic light transform
    final masked = Float32List.fromList(full);
    for (int i = 0; i < masked.length; i += 7) {
      masked[i] *= 0.9;
    }
    return EmbeddingPair(fullFrame: full, peopleMasked: masked);
  }

  @override
  double cosine(Float32List a, Float32List b) => _tflite.calculateSimilarity(a, b);
}

