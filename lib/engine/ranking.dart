import 'package:image/image.dart' as img;
import '../services/asset_photo_service.dart';
import 'quality_metrics.dart';
import 'weights.dart';

class RankedPhoto {
  final AssetPhoto photo;
  final double score;
  const RankedPhoto(this.photo, this.score);
}

class Ranker {
  final RankingWeights weights;
  const Ranker({this.weights = const RankingWeights()});

  Future<RankedPhoto> pickBest(List<AssetPhoto> group) async {
    RankedPhoto? best;
    for (final p in group) {
      final bytes = await p.originBytes;
      final im = img.decodeImage(bytes);
      if (im == null) continue;
      // Downscale for speed
      final resized = img.copyResize(im, width: 256);
      final sharp = QualityMetrics.computeSharpness(resized);
      final exposure = QualityMetrics.computeExposure(resized);
      // Placeholders: aesthetic/faceQuality/eyesOpen default to mid if unknown
      const aesthetic = 0.5;
      const faceQuality = 0.5;
      const eyesOpen = 0.5;
      final score = _rankScore(
        aesthetic: aesthetic,
        sharpness: sharp,
        exposure: exposure,
        faceQuality: faceQuality,
        eyesOpen: eyesOpen,
      );
      if (best == null || score > best.score) {
        best = RankedPhoto(p, score);
      }
    }
    return best ?? RankedPhoto(group.first, 0.0);
  }

  double _rankScore({
    required double aesthetic,
    required double sharpness,
    required double exposure,
    required double faceQuality,
    required double eyesOpen,
  }) {
    final w = weights;
    return w.aestheticWeight * aesthetic +
        w.sharpnessWeight * sharpness +
        w.exposureWeight * exposure +
        w.faceQualityWeight * faceQuality +
        w.eyesOpenWeight * eyesOpen;
  }
}


