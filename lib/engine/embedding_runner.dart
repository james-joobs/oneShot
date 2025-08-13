import 'dart:typed_data';
import '../services/asset_photo_service.dart';
import '../services/mock_tflite_service.dart';

class EmbeddingPair {
  final Float32List fullFrame;
  final Float32List peopleMasked;
  const EmbeddingPair({required this.fullFrame, required this.peopleMasked});
}

abstract class EmbeddingRunner {
  Future<void> initialize();
  Future<EmbeddingPair> extract(AssetPhoto photo);
  double cosine(Float32List a, Float32List b);
}

// MVP: reuse MockTFLiteService for both full and masked; simulate masking by small noise
class MockEmbeddingRunner implements EmbeddingRunner {
  final MockTFLiteService _mock;
  MockEmbeddingRunner(this._mock);

  @override
  Future<void> initialize() => _mock.initialize();

  @override
  Future<EmbeddingPair> extract(AssetPhoto photo) async {
    final full = await _mock.extractFeaturesFromAssetPhoto(photo);
    // Simulated masking: perturb a subset deterministically to mimic background-only stability
    final masked = Float32List.fromList(full);
    for (int i = 0; i < masked.length; i += 7) {
      masked[i] *= 0.9;
    }
    return EmbeddingPair(fullFrame: full, peopleMasked: masked);
  }

  @override
  double cosine(Float32List a, Float32List b) =>
      _mock.calculateSimilarity(a, b);
}
