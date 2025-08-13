import 'dart:math' as math;
import 'package:image/image.dart' as img;

class QualityScores {
  final double sharpness; // [0,1]
  final double exposure; // [0,1]
  final double noise; // [0,1] lower noise → higher score
  final double aesthetic; // [0,1]
  final double faceQuality; // [0,1]
  final double eyesOpen; // [0,1]

  const QualityScores({
    required this.sharpness,
    required this.exposure,
    required this.noise,
    required this.aesthetic,
    required this.faceQuality,
    required this.eyesOpen,
  });
}

class QualityMetrics {
  // Variance of Laplacian style sharpness (normalized)
  static double computeSharpness(img.Image image) {
    final grayscale = img.grayscale(image);
    final width = grayscale.width;
    final height = grayscale.height;
    double variance = 0.0;
    double mean = 0.0;
    int count = 0;

    // Simple 3x3 Laplacian kernel
    const kernel = [
      0,
      1,
      0,
      1,
      -4,
      1,
      0,
      1,
      0,
    ];

    for (int y = 1; y < height - 1; y++) {
      for (int x = 1; x < width - 1; x++) {
        int idx = 0;
        double v = 0.0;
        for (int ky = -1; ky <= 1; ky++) {
          for (int kx = -1; kx <= 1; kx++) {
            final px = grayscale.getPixel(x + kx, y + ky);
            final intensity = img.getLuminance(px).toDouble();
            v += intensity * kernel[idx++];
          }
        }
        mean += v;
        variance += v * v;
        count++;
      }
    }
    if (count == 0) return 0.0;
    mean /= count;
    variance = variance / count - mean * mean;
    // Normalize with a soft function
    return 1.0 - math.exp(-variance / 10000.0).clamp(0.0, 1.0);
  }

  // Simple exposure score using histogram spread around mid gray
  static double computeExposure(img.Image image) {
    final grayscale = img.grayscale(image);
    final hist = List<int>.filled(256, 0);
    final total = grayscale.width * grayscale.height;
    for (int y = 0; y < grayscale.height; y++) {
      for (int x = 0; x < grayscale.width; x++) {
        final px = grayscale.getPixel(x, y);
        final int lum = img.getLuminance(px).toInt();
        hist[lum]++;
      }
    }
    // Measure distance from ideal mid histogram (avoid clipped extremes)
    final low = hist.sublist(0, 10).reduce((a, b) => a + b) / total;
    final high = hist.sublist(246, 256).reduce((a, b) => a + b) / total;
    final clipped = (low + high).clamp(0.0, 1.0);
    final score = (1.0 - clipped) * 0.7 + histogramSpread(hist) * 0.3;
    return score.clamp(0.0, 1.0);
  }

  static double histogramSpread(List<int> hist) {
    final total = hist.reduce((a, b) => a + b);
    double mean = 0.0;
    for (int i = 0; i < hist.length; i++) {
      mean += hist[i] * i;
    }
    mean /= math.max(1, total);
    double variance = 0.0;
    for (int i = 0; i < hist.length; i++) {
      final d = (i - mean);
      variance += hist[i] * d * d;
    }
    variance /= math.max(1, total);
    return (1.0 - math.exp(-variance / 4000.0)).clamp(0.0, 1.0);
  }
}
