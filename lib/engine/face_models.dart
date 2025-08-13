// Placeholder: face detection/ID would be provided by MediaPipe/ArcFace in prod.
// For MVP, we simulate a stable face-set signature per photo name.

import 'dart:math' as math;

import '../services/asset_photo_service.dart';

class FaceSetSignature {
  // A small fixed-length binary signature to approximate a set hash
  final List<int> bits; // 64 bits
  const FaceSetSignature(this.bits);
}

class FaceEngineMock {
  FaceSetSignature computeSignature(AssetPhoto photo) {
    final h = photo.name.hashCode;
    final rnd = math.Random(h.abs());
    final bits = List<int>.generate(64, (_) => rnd.nextBool() ? 1 : 0);
    return FaceSetSignature(bits);
  }

  // Jaccard-like similarity for bitsets
  double similarity(FaceSetSignature a, FaceSetSignature b) {
    int inter = 0;
    int union = 0;
    for (int i = 0; i < a.bits.length; i++) {
      final ai = a.bits[i];
      final bi = b.bits[i];
      if (ai == 1 || bi == 1) union++;
      if (ai == 1 && bi == 1) inter++;
    }
    if (union == 0) return 1.0;
    return inter / union;
  }
}


