import 'dart:math';

/// PCA transformation for embedding post-processing
class PCATransform {
  static const int inputDim = 384;
  static const int outputDim = 23;
  static const bool useWhitening = true;

  // PCA mean vector
  static final List<double> mean = [
    -0.013803, -0.007072, 0.034905, 0.007253, -0.007504, 0.009974, -0.009355,
    -0.005958, 0.009884, 0.008746,
    // ... 374 more values
  ];

  // Transformation matrix (components or whitening matrix)
  static final List<List<double>> transformMatrix = [
    [
      -0.104300,
      0.090145,
      0.133198,
      -0.138666,
      0.028372, /* ... 379 more values */
    ],
    [
      -0.092811,
      -0.020006,
      -0.171275,
      -0.014348,
      -0.114708, /* ... 379 more values */
    ],
    [
      0.062292,
      -0.110130,
      -0.049796,
      -0.273441,
      -0.146171, /* ... 379 more values */
    ],
    // ... 20 more rows
  ];

  /// Apply PCA transformation to embedding
  static List<double> transform(List<double> embedding) {
    if (embedding.length != inputDim) {
      throw ArgumentError('Input embedding must have dimension $inputDim');
    }

    // Center the embedding
    List<double> centered = [];
    for (int i = 0; i < inputDim; i++) {
      centered.add(embedding[i] - mean[i]);
    }

    // Apply transformation
    List<double> result = List.filled(outputDim, 0.0);
    for (int i = 0; i < outputDim; i++) {
      double sum = 0.0;
      for (int j = 0; j < inputDim; j++) {
        sum += transformMatrix[i][j] * centered[j];
      }
      result[i] = sum;
    }

    // L2 normalize the result
    double norm = 0.0;
    for (double val in result) {
      norm += val * val;
    }
    norm = sqrt(norm);

    if (norm > 0) {
      for (int i = 0; i < result.length; i++) {
        result[i] /= norm;
      }
    }

    return result;
  }
}
