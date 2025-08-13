import '../models/photo_cluster.dart';
import '../services/asset_photo_service.dart';
import 'embedding_runner.dart';
import 'face_models.dart';
import 'weights.dart';

class DuplicateGrouperConfig {
  final DuplicateWeights weights;
  final Thresholds thresholds;
  const DuplicateGrouperConfig({
    this.weights = const DuplicateWeights(),
    this.thresholds = const Thresholds(),
  });
}

class DuplicateGrouper {
  final EmbeddingRunner embeddingRunner;
  final FaceEngineMock faceEngine;
  final DuplicateGrouperConfig config;

  const DuplicateGrouper({
    required this.embeddingRunner,
    required this.faceEngine,
    this.config = const DuplicateGrouperConfig(),
  });

  Future<List<AssetPhotoCluster>> group(List<AssetPhoto> photos, {Function(int, int)? onProgress}) async {
    final embeddings = <AssetPhoto, EmbeddingPair>{};
    final faceSigs = <AssetPhoto, FaceSetSignature>{};

    for (int i = 0; i < photos.length; i++) {
      final p = photos[i];
      embeddings[p] = await embeddingRunner.extract(p);
      faceSigs[p] = faceEngine.computeSignature(p);
      onProgress?.call(i + 1, photos.length);
    }

    final List<AssetPhotoCluster> clusters = [];
    final processed = <AssetPhoto>{};
    int clusterId = 0;
    for (final photo in photos) {
      if (processed.contains(photo)) continue;
      final group = <AssetPhoto>[photo];
      final e0 = embeddings[photo]!;
      final f0 = faceSigs[photo]!;
      processed.add(photo);

      double simSum = 0.0;
      int simCount = 0;
      for (final other in photos) {
        if (processed.contains(other)) continue;
        final e1 = embeddings[other]!;
        final f1 = faceSigs[other]!;
        final dupScore = _duplicateScore(e0, e1, f0, f1);
        if (dupScore >= config.thresholds.duplicateScoreThreshold) {
          group.add(other);
          processed.add(other);
          simSum += dupScore;
          simCount++;
        }
      }

      clusters.add(AssetPhotoCluster(
        id: 'cluster_$clusterId',
        photos: group,
        representative: group.first, // ranking will pick later
        averageSimilarity: simCount == 0 ? 1.0 : simSum / simCount,
      ));
      clusterId++;
    }

    return clusters;
  }

  double _duplicateScore(EmbeddingPair a, EmbeddingPair b, FaceSetSignature fa, FaceSetSignature fb) {
    final simBgMasked = embeddingRunner.cosine(a.peopleMasked, b.peopleMasked);
    final simBgFull = embeddingRunner.cosine(a.fullFrame, b.fullFrame);
    final simFace = faceEngine.similarity(fa, fb);
    final w = config.weights;
    return w.backgroundMaskedWeight * simBgMasked +
        w.backgroundFullWeight * simBgFull +
        w.faceSetWeight * simFace;
  }
}


