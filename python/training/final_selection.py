#!/usr/bin/env python3
"""
Final selection algorithm with quality metrics for photo curation.
Implements submodular optimization for diverse, high-quality photo selection.
"""

import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import json
from scipy.spatial.distance import cdist
from PIL import Image
import exifread


@dataclass
class PhotoCandidate:
    """Complete photo candidate with all metrics."""
    path: str
    cluster_id: int
    scene_embedding: np.ndarray
    face_ids: List[int]
    similarity_score: float
    quality_score: float
    aesthetic_score: float
    diversity_bonus: float = 0.0
    final_score: float = 0.0


class QualityMetrics:
    """Photo quality assessment metrics."""
    
    @staticmethod
    def compute_sharpness(image_path: str) -> float:
        """
        Compute image sharpness using Laplacian variance.
        
        Args:
            image_path: Path to image
        Returns:
            Sharpness score (0-1)
        """
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0.0
        
        # Resize for consistent computation
        h, w = img.shape
        if max(h, w) > 640:
            scale = 640 / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h))
        
        # Compute Laplacian
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        variance = laplacian.var()
        
        # Normalize to 0-1 range (empirically determined)
        normalized = min(variance / 1000.0, 1.0)
        
        return float(normalized)
    
    @staticmethod
    def compute_exposure_quality(image_path: str) -> float:
        """
        Compute exposure quality based on histogram analysis.
        
        Args:
            image_path: Path to image
        Returns:
            Exposure quality score (0-1)
        """
        img = cv2.imread(image_path)
        if img is None:
            return 0.0
        
        # Convert to LAB color space
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        
        # Compute histogram
        hist, _ = np.histogram(l_channel, bins=256, range=(0, 256))
        hist = hist.astype(float) / hist.sum()
        
        # Check for clipping (over/under exposure)
        underexposed = hist[:10].sum()
        overexposed = hist[-10:].sum()
        clipping_penalty = (underexposed + overexposed) * 2
        
        # Compute entropy (higher is better)
        hist_nonzero = hist[hist > 0]
        entropy = -np.sum(hist_nonzero * np.log2(hist_nonzero))
        entropy_normalized = entropy / 8.0  # Max entropy is 8 for uniform distribution
        
        # Combined score
        score = entropy_normalized * (1 - clipping_penalty)
        
        return float(np.clip(score, 0, 1))
    
    @staticmethod
    def detect_eyes_open(face_landmarks: Dict) -> bool:
        """
        Detect if eyes are open based on face landmarks.
        
        Args:
            face_landmarks: Face landmarks dictionary
        Returns:
            True if eyes appear open
        """
        if not face_landmarks:
            return True  # Default to open if no landmarks
        
        # Check eye aspect ratio
        left_eye = face_landmarks.get('left_eye', [])
        right_eye = face_landmarks.get('right_eye', [])
        
        if len(left_eye) < 6 or len(right_eye) < 6:
            return True
        
        def eye_aspect_ratio(eye):
            # Compute distances between eye landmarks
            vertical_1 = np.linalg.norm(
                np.array(eye[1]) - np.array(eye[5])
            )
            vertical_2 = np.linalg.norm(
                np.array(eye[2]) - np.array(eye[4])
            )
            horizontal = np.linalg.norm(
                np.array(eye[0]) - np.array(eye[3])
            )
            
            if horizontal == 0:
                return 0
            
            return (vertical_1 + vertical_2) / (2.0 * horizontal)
        
        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        
        # Threshold for open eyes (empirically determined)
        return (left_ear + right_ear) / 2 > 0.2
    
    @staticmethod
    def compute_composition_score(image_path: str) -> float:
        """
        Compute composition score using rule of thirds and balance.
        
        Args:
            image_path: Path to image
        Returns:
            Composition score (0-1)
        """
        img = cv2.imread(image_path)
        if img is None:
            return 0.5
        
        h, w = img.shape[:2]
        
        # Convert to grayscale for edge detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Rule of thirds analysis
        third_lines_x = [w // 3, 2 * w // 3]
        third_lines_y = [h // 3, 2 * h // 3]
        
        # Count edge pixels near third lines
        proximity_threshold = min(w, h) // 30
        thirds_score = 0
        
        for x in third_lines_x:
            region = edges[:, max(0, x-proximity_threshold):min(w, x+proximity_threshold)]
            thirds_score += region.sum() / 255
        
        for y in third_lines_y:
            region = edges[max(0, y-proximity_threshold):min(h, y+proximity_threshold), :]
            thirds_score += region.sum() / 255
        
        # Normalize
        max_possible = proximity_threshold * 2 * (h * 2 + w * 2)
        thirds_score = min(thirds_score / max_possible * 10, 1.0)
        
        # Balance analysis (center of mass)
        moments = cv2.moments(edges)
        if moments['m00'] > 0:
            cx = moments['m10'] / moments['m00']
            cy = moments['m01'] / moments['m00']
            
            # Distance from center
            center_dist = np.sqrt((cx - w/2)**2 + (cy - h/2)**2)
            max_dist = np.sqrt((w/2)**2 + (h/2)**2)
            balance_score = 1 - (center_dist / max_dist)
        else:
            balance_score = 0.5
        
        # Combined score
        return float((thirds_score + balance_score) / 2)


class AestheticScorer:
    """Neural aesthetic scoring (simplified version)."""
    
    def __init__(self, use_ml_model: bool = False, model_path: Optional[str] = None):
        """
        Args:
            use_ml_model: Whether to use ML model for scoring
            model_path: Path to aesthetic scoring model
        """
        self.use_ml_model = use_ml_model
        self.model = None
        
        if use_ml_model and model_path:
            # Load TFLite model for aesthetic scoring
            import tensorflow as tf
            self.interpreter = tf.lite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
    
    def compute_aesthetic_score(self, image_path: str) -> float:
        """
        Compute aesthetic score for image.
        
        Args:
            image_path: Path to image
        Returns:
            Aesthetic score (0-1)
        """
        if self.use_ml_model and self.interpreter:
            return self._compute_ml_aesthetic_score(image_path)
        else:
            return self._compute_heuristic_aesthetic_score(image_path)
    
    def _compute_heuristic_aesthetic_score(self, image_path: str) -> float:
        """Heuristic-based aesthetic scoring."""
        img = cv2.imread(image_path)
        if img is None:
            return 0.5
        
        scores = []
        
        # Color vibrancy
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].mean() / 255
        scores.append(min(saturation * 2, 1.0))  # Moderate saturation is good
        
        # Contrast
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        contrast = gray.std() / 128
        scores.append(min(contrast, 1.0))
        
        # Color harmony (simplified)
        hist_h = cv2.calcHist([hsv], [0], None, [180], [0, 180])
        hist_h = hist_h.flatten() / hist_h.sum()
        
        # Find dominant hues
        dominant_hues = np.argsort(hist_h)[-3:]
        hue_distances = []
        for i in range(len(dominant_hues)):
            for j in range(i+1, len(dominant_hues)):
                dist = min(abs(dominant_hues[i] - dominant_hues[j]),
                          180 - abs(dominant_hues[i] - dominant_hues[j]))
                hue_distances.append(dist)
        
        # Complementary colors (180°) or triadic (120°) are harmonious
        if hue_distances:
            harmony = 0
            for dist in hue_distances:
                if abs(dist - 180) < 30:  # Complementary
                    harmony = max(harmony, 1.0)
                elif abs(dist - 120) < 30:  # Triadic
                    harmony = max(harmony, 0.8)
                elif abs(dist - 60) < 20:  # Analogous
                    harmony = max(harmony, 0.6)
            scores.append(harmony)
        
        # Composition score
        comp_score = QualityMetrics.compute_composition_score(image_path)
        scores.append(comp_score)
        
        return float(np.mean(scores))
    
    def _compute_ml_aesthetic_score(self, image_path: str) -> float:
        """ML model-based aesthetic scoring."""
        # Load and preprocess image
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224))
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = np.expand_dims(img_array, axis=0)
        
        # Run inference
        self.interpreter.set_tensor(self.input_details[0]['index'], img_array)
        self.interpreter.invoke()
        
        # Get score
        score = self.interpreter.get_tensor(self.output_details[0]['index'])[0, 0]
        
        return float(np.clip(score, 0, 1))


class SubmodularSelector:
    """Submodular optimization for diverse photo selection."""
    
    def __init__(self, lambda_diversity: float = 0.1):
        """
        Args:
            lambda_diversity: Weight for diversity term
        """
        self.lambda_diversity = lambda_diversity
    
    def select_diverse_subset(self, candidates: List[PhotoCandidate],
                             k: int) -> List[int]:
        """
        Select diverse subset using greedy submodular optimization.
        
        Args:
            candidates: List of photo candidates
            k: Number of photos to select
        Returns:
            Indices of selected photos
        """
        if len(candidates) <= k:
            return list(range(len(candidates)))
        
        # Extract embeddings
        embeddings = np.array([c.scene_embedding for c in candidates])
        scores = np.array([c.final_score for c in candidates])
        
        # Compute pairwise distances
        distances = cdist(embeddings, embeddings, metric='cosine')
        
        selected = []
        remaining = set(range(len(candidates)))
        
        # Greedy selection
        for _ in range(k):
            best_idx = -1
            best_gain = -float('inf')
            
            for idx in remaining:
                # Quality term
                quality_gain = scores[idx]
                
                # Diversity term (minimum distance to selected set)
                if selected:
                    min_dist = min(distances[idx, s] for s in selected)
                    diversity_gain = min_dist
                else:
                    diversity_gain = 1.0
                
                # Combined objective
                gain = quality_gain + self.lambda_diversity * diversity_gain
                
                if gain > best_gain:
                    best_gain = gain
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(best_idx)
                remaining.remove(best_idx)
        
        return selected


class FinalPhotoSelector:
    """Complete final selection pipeline."""
    
    def __init__(self, alpha: float = 0.55, beta: float = 0.2,
                 gamma: float = 0.15, delta: float = 0.1):
        """
        Args:
            alpha: Weight for similarity score
            beta: Weight for quality score
            gamma: Weight for aesthetic score
            delta: Weight for diversity bonus
        """
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta
        
        self.quality_metrics = QualityMetrics()
        self.aesthetic_scorer = AestheticScorer()
        self.submodular_selector = SubmodularSelector()
    
    def compute_final_scores(self, candidates: List[PhotoCandidate]) -> None:
        """
        Compute final scores for all candidates.
        
        Args:
            candidates: List of photo candidates
        """
        for candidate in candidates:
            # Compute quality components
            sharpness = self.quality_metrics.compute_sharpness(candidate.path)
            exposure = self.quality_metrics.compute_exposure_quality(candidate.path)
            
            # Combined quality score
            candidate.quality_score = (sharpness + exposure) / 2
            
            # Aesthetic score
            candidate.aesthetic_score = self.aesthetic_scorer.compute_aesthetic_score(
                candidate.path
            )
            
            # Initial final score (without diversity)
            candidate.final_score = (
                self.alpha * candidate.similarity_score +
                self.beta * candidate.quality_score +
                self.gamma * candidate.aesthetic_score
            )
    
    def select_best_photos(self, candidates: List[PhotoCandidate],
                          photos_per_cluster: int = 2) -> List[PhotoCandidate]:
        """
        Select best photos from candidates.
        
        Args:
            candidates: List of all photo candidates
            photos_per_cluster: Maximum photos to select per cluster
        Returns:
            Selected photos
        """
        # Compute final scores
        self.compute_final_scores(candidates)
        
        # Group by cluster
        clusters = {}
        for candidate in candidates:
            if candidate.cluster_id not in clusters:
                clusters[candidate.cluster_id] = []
            clusters[candidate.cluster_id].append(candidate)
        
        selected = []
        
        # Select from each cluster
        for cluster_id, cluster_candidates in clusters.items():
            if cluster_id == -1:  # Skip noise
                continue
            
            # Use submodular selection for diversity
            indices = self.submodular_selector.select_diverse_subset(
                cluster_candidates, photos_per_cluster
            )
            
            for idx in indices:
                selected.append(cluster_candidates[idx])
        
        return selected
    
    def export_selection_results(self, selected: List[PhotoCandidate],
                                output_path: str):
        """Export selection results to JSON."""
        results = []
        
        for photo in selected:
            results.append({
                'path': photo.path,
                'cluster_id': int(photo.cluster_id),
                'scores': {
                    'final': float(photo.final_score),
                    'similarity': float(photo.similarity_score),
                    'quality': float(photo.quality_score),
                    'aesthetic': float(photo.aesthetic_score),
                    'diversity': float(photo.diversity_bonus)
                },
                'face_ids': photo.face_ids
            })
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Selection results exported to {output_path}")


def generate_dart_selector() -> str:
    """Generate Dart code for final selection."""
    dart_code = '''
/// Final photo selection with quality metrics
class FinalPhotoSelector {
  static const double defaultAlpha = 0.55;  // Similarity weight
  static const double defaultBeta = 0.2;    // Quality weight
  static const double defaultGamma = 0.15;  // Aesthetic weight
  static const double defaultDelta = 0.1;   // Diversity weight
  
  final double alpha;
  final double beta;
  final double gamma;
  final double delta;
  
  FinalPhotoSelector({
    this.alpha = defaultAlpha,
    this.beta = defaultBeta,
    this.gamma = defaultGamma,
    this.delta = defaultDelta,
  });
  
  /// Compute final score for a photo
  double computeFinalScore({
    required double similarityScore,
    required double qualityScore,
    required double aestheticScore,
    double diversityBonus = 0.0,
  }) {
    return alpha * similarityScore +
           beta * qualityScore +
           gamma * aestheticScore +
           delta * diversityBonus;
  }
  
  /// Select diverse subset using greedy algorithm
  List<int> selectDiverseSubset(
    List<PhotoCandidate> candidates,
    int k,
  ) {
    if (candidates.length <= k) {
      return List.generate(candidates.length, (i) => i);
    }
    
    final selected = <int>[];
    final remaining = Set<int>.from(
      List.generate(candidates.length, (i) => i)
    );
    
    // Greedy selection
    for (int i = 0; i < k; i++) {
      int bestIdx = -1;
      double bestGain = double.negativeInfinity;
      
      for (int idx in remaining) {
        // Quality term
        double qualityGain = candidates[idx].finalScore;
        
        // Diversity term
        double diversityGain = 1.0;
        if (selected.isNotEmpty) {
          double minDist = double.infinity;
          for (int s in selected) {
            double dist = _cosineDistance(
              candidates[idx].embedding,
              candidates[s].embedding,
            );
            if (dist < minDist) minDist = dist;
          }
          diversityGain = minDist;
        }
        
        // Combined objective
        double gain = qualityGain + 0.1 * diversityGain;
        
        if (gain > bestGain) {
          bestGain = gain;
          bestIdx = idx;
        }
      }
      
      if (bestIdx >= 0) {
        selected.add(bestIdx);
        remaining.remove(bestIdx);
      }
    }
    
    return selected;
  }
  
  /// Compute cosine distance
  double _cosineDistance(List<double> a, List<double> b) {
    double sim = _cosineSimilarity(a, b);
    return 1.0 - sim;
  }
  
  double _cosineSimilarity(List<double> a, List<double> b) {
    double dot = 0.0;
    double normA = 0.0;
    double normB = 0.0;
    
    for (int i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    
    if (normA == 0 || normB == 0) return 0.0;
    return dot / (sqrt(normA) * sqrt(normB));
  }
}

class PhotoCandidate {
  final String path;
  final int clusterId;
  final List<double> embedding;
  final List<int> faceIds;
  double similarityScore;
  double qualityScore;
  double aestheticScore;
  double diversityBonus;
  double finalScore;
  
  PhotoCandidate({
    required this.path,
    required this.clusterId,
    required this.embedding,
    required this.faceIds,
    this.similarityScore = 0.0,
    this.qualityScore = 0.0,
    this.aestheticScore = 0.0,
    this.diversityBonus = 0.0,
    this.finalScore = 0.0,
  });
}
'''
    return dart_code


def main():
    """Test final selection."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Final photo selection')
    parser.add_argument('--candidates_json', type=str,
                       help='JSON file with photo candidates')
    parser.add_argument('--output_json', type=str,
                       help='Output JSON with selected photos')
    parser.add_argument('--photos_per_cluster', type=int, default=2,
                       help='Photos to select per cluster')
    parser.add_argument('--export_dart', type=str,
                       help='Export Dart code')
    
    args = parser.parse_args()
    
    # Export Dart code
    if args.export_dart:
        dart_code = generate_dart_selector()
        with open(args.export_dart, 'w') as f:
            f.write(dart_code)
        print(f"Dart code exported to {args.export_dart}")
    
    # Process candidates
    if args.candidates_json:
        # Load candidates
        with open(args.candidates_json, 'r') as f:
            candidates_data = json.load(f)
        
        # Create PhotoCandidate objects
        candidates = []
        for data in candidates_data:
            candidate = PhotoCandidate(
                path=data['path'],
                cluster_id=data['cluster_id'],
                scene_embedding=np.array(data['embedding']),
                face_ids=data.get('face_ids', []),
                similarity_score=data.get('similarity_score', 0.5),
                quality_score=0.0,
                aesthetic_score=0.0
            )
            candidates.append(candidate)
        
        # Select photos
        selector = FinalPhotoSelector()
        selected = selector.select_best_photos(
            candidates, args.photos_per_cluster
        )
        
        print(f"\nSelected {len(selected)} photos from {len(candidates)} candidates")
        
        # Export results
        if args.output_json:
            selector.export_selection_results(selected, args.output_json)


if __name__ == '__main__':
    main()