class DuplicateWeights {
  final double backgroundMaskedWeight;
  final double backgroundFullWeight;
  final double faceSetWeight;

  const DuplicateWeights({
    this.backgroundMaskedWeight = 0.45,
    this.backgroundFullWeight = 0.20,
    this.faceSetWeight = 0.35,
  });
}

class RankingWeights {
  final double aestheticWeight;
  final double sharpnessWeight;
  final double exposureWeight;
  final double faceQualityWeight;
  final double eyesOpenWeight; // 1 - blinkRate

  const RankingWeights({
    this.aestheticWeight = 0.4,
    this.sharpnessWeight = 0.2,
    this.exposureWeight = 0.15,
    this.faceQualityWeight = 0.15,
    this.eyesOpenWeight = 0.1,
  });
}

class Thresholds {
  final double duplicateScoreThreshold;

  const Thresholds({
    this.duplicateScoreThreshold = 0.78,
  });
}


