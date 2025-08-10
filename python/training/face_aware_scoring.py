#!/usr/bin/env python3
"""
Face-aware scoring module for photo duplicate detection.
Combines scene embeddings with face recognition for improved accuracy.
"""

import numpy as np
import cv2
import face_recognition
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import json
import tensorflow as tf
from PIL import Image


@dataclass
class FaceData:
    """Face detection and embedding data."""
    bbox: Tuple[int, int, int, int]  # (top, right, bottom, left)
    embedding: np.ndarray
    confidence: float
    landmarks: Optional[Dict] = None


@dataclass
class PhotoFeatures:
    """Combined features for a photo."""
    path: str
    scene_embedding: np.ndarray
    faces: List[FaceData]
    quality_score: float
    aesthetic_score: float


class FaceDetector:
    """Face detection and embedding extraction."""
    
    def __init__(self, model: str = 'hog', encoding_model: str = 'large'):
        """
        Args:
            model: Detection model ('hog' or 'cnn')
            encoding_model: Face encoding model ('small' or 'large')
        """
        self.detection_model = model
        self.encoding_model = encoding_model
        self.num_jitters = 1  # Number of re-samplings for face encoding
    
    def detect_and_encode_faces(self, image_path: str) -> List[FaceData]:
        """
        Detect faces and extract embeddings.
        
        Args:
            image_path: Path to image
        Returns:
            List of FaceData objects
        """
        # Load image
        image = face_recognition.load_image_file(image_path)
        
        # Detect face locations
        face_locations = face_recognition.face_locations(
            image, model=self.detection_model
        )
        
        if not face_locations:
            return []
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(
            image, face_locations, num_jitters=self.num_jitters,
            model=self.encoding_model
        )
        
        # Get face landmarks (optional, for quality assessment)
        face_landmarks = face_recognition.face_landmarks(image, face_locations)
        
        faces = []
        for loc, enc, landmarks in zip(face_locations, face_encodings, face_landmarks):
            # Calculate confidence based on face size
            top, right, bottom, left = loc
            face_area = (bottom - top) * (right - left)
            image_area = image.shape[0] * image.shape[1]
            confidence = min(face_area / image_area * 10, 1.0)  # Normalize
            
            face_data = FaceData(
                bbox=loc,
                embedding=enc,
                confidence=confidence,
                landmarks=landmarks
            )
            faces.append(face_data)
        
        return faces
    
    def compute_face_similarity(self, faces1: List[FaceData], 
                              faces2: List[FaceData],
                              threshold: float = 0.6) -> Tuple[float, List[Tuple[int, int]]]:
        """
        Compute similarity between two sets of faces.
        
        Args:
            faces1: Faces from first image
            faces2: Faces from second image
            threshold: Distance threshold for matching faces
        Returns:
            Jaccard similarity and list of matched face pairs
        """
        if not faces1 or not faces2:
            return 0.0, []
        
        # Compute pairwise distances
        distances = np.zeros((len(faces1), len(faces2)))
        for i, f1 in enumerate(faces1):
            for j, f2 in enumerate(faces2):
                distances[i, j] = face_recognition.face_distance(
                    [f1.embedding], f2.embedding
                )[0]
        
        # Find matches using Hungarian algorithm
        matches = []
        used_i = set()
        used_j = set()
        
        # Sort by distance
        indices = np.unravel_index(np.argsort(distances, axis=None), distances.shape)
        
        for i, j in zip(indices[0], indices[1]):
            if i not in used_i and j not in used_j:
                if distances[i, j] < threshold:
                    matches.append((i, j))
                    used_i.add(i)
                    used_j.add(j)
        
        # Calculate Jaccard similarity
        jaccard = len(matches) / (len(faces1) + len(faces2) - len(matches))
        
        return jaccard, matches


class MobileFaceNetTFLite:
    """TFLite-based face recognition using MobileFaceNet."""
    
    def __init__(self, model_path: str):
        """
        Args:
            model_path: Path to MobileFaceNet TFLite model
        """
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # Get input size
        self.input_shape = self.input_details[0]['shape']
        self.input_size = (self.input_shape[1], self.input_shape[2])
    
    def extract_face_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """
        Extract face embedding using MobileFaceNet.
        
        Args:
            face_image: Face image array
        Returns:
            Face embedding vector
        """
        # Resize to model input size
        face_resized = cv2.resize(face_image, self.input_size)
        
        # Preprocess
        face_normalized = (face_resized.astype(np.float32) - 127.5) / 128.0
        
        # Add batch dimension
        input_data = np.expand_dims(face_normalized, axis=0)
        
        # Check if model expects int8 input
        if self.input_details[0]['dtype'] == np.int8:
            input_scale = self.input_details[0]['quantization'][0]
            input_zero_point = self.input_details[0]['quantization'][1]
            input_data = input_data / input_scale + input_zero_point
            input_data = np.clip(input_data, -128, 127).astype(np.int8)
        
        # Run inference
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        
        # Get output
        embedding = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        
        # Dequantize if needed
        if self.output_details[0]['dtype'] == np.int8:
            output_scale = self.output_details[0]['quantization'][0]
            output_zero_point = self.output_details[0]['quantization'][1]
            embedding = (embedding.astype(np.float32) - output_zero_point) * output_scale
        
        # L2 normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def detect_and_encode_faces_tflite(self, image_path: str) -> List[FaceData]:
        """
        Detect faces using OpenCV and encode using MobileFaceNet.
        
        Args:
            image_path: Path to image
        Returns:
            List of FaceData objects
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return []
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use OpenCV's face detector
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        faces_cv = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        
        faces = []
        for (x, y, w, h) in faces_cv:
            # Extract face region
            face_img = image_rgb[y:y+h, x:x+w]
            
            # Get embedding
            embedding = self.extract_face_embedding(face_img)
            
            # Calculate confidence
            face_area = w * h
            image_area = image.shape[0] * image.shape[1]
            confidence = min(face_area / image_area * 10, 1.0)
            
            face_data = FaceData(
                bbox=(y, x+w, y+h, x),  # Convert to face_recognition format
                embedding=embedding,
                confidence=confidence
            )
            faces.append(face_data)
        
        return faces


class FaceAwareScorer:
    """Combined scene and face-aware scoring."""
    
    def __init__(self, face_weight: float = 0.3, 
                 face_threshold: float = 0.6,
                 use_tflite: bool = False,
                 mobilefacenet_path: Optional[str] = None):
        """
        Args:
            face_weight: Weight for face similarity (0-1)
            face_threshold: Threshold for face matching
            use_tflite: Use TFLite MobileFaceNet instead of face_recognition
            mobilefacenet_path: Path to MobileFaceNet TFLite model
        """
        self.face_weight = face_weight
        self.face_threshold = face_threshold
        
        if use_tflite and mobilefacenet_path:
            self.face_model = MobileFaceNetTFLite(mobilefacenet_path)
            self.detect_faces = self.face_model.detect_and_encode_faces_tflite
        else:
            self.face_detector = FaceDetector()
            self.detect_faces = self.face_detector.detect_and_encode_faces
    
    def compute_combined_similarity(self, features1: PhotoFeatures,
                                   features2: PhotoFeatures) -> Dict[str, float]:
        """
        Compute combined similarity score.
        
        Args:
            features1: Features from first photo
            features2: Features from second photo
        Returns:
            Dictionary with similarity scores
        """
        # Scene similarity (cosine)
        scene_sim = np.dot(features1.scene_embedding, features2.scene_embedding)
        scene_sim = np.clip(scene_sim, -1, 1)
        
        # Face similarity
        if features1.faces and features2.faces:
            if hasattr(self, 'face_detector'):
                face_sim, matches = self.face_detector.compute_face_similarity(
                    features1.faces, features2.faces, self.face_threshold
                )
            else:
                # Simple Jaccard for TFLite version
                face_sim = self._compute_face_jaccard_tflite(
                    features1.faces, features2.faces
                )
                matches = []
        else:
            face_sim = 0.0
            matches = []
        
        # Combined score
        has_faces = bool(features1.faces or features2.faces)
        if has_faces:
            combined_score = (1 - self.face_weight) * scene_sim + self.face_weight * face_sim
        else:
            combined_score = scene_sim
        
        return {
            'combined_score': float(combined_score),
            'scene_similarity': float(scene_sim),
            'face_similarity': float(face_sim),
            'num_face_matches': len(matches),
            'has_faces': has_faces
        }
    
    def _compute_face_jaccard_tflite(self, faces1: List[FaceData],
                                    faces2: List[FaceData]) -> float:
        """Compute Jaccard similarity for TFLite face embeddings."""
        if not faces1 or not faces2:
            return 0.0
        
        matches = 0
        for f1 in faces1:
            for f2 in faces2:
                # Cosine similarity
                sim = np.dot(f1.embedding, f2.embedding)
                if sim > (1 - self.face_threshold):  # Convert threshold to similarity
                    matches += 1
                    break
        
        jaccard = matches / (len(faces1) + len(faces2) - matches)
        return jaccard
    
    def extract_photo_features(self, image_path: str,
                              scene_embedding: np.ndarray,
                              quality_fn=None,
                              aesthetic_fn=None) -> PhotoFeatures:
        """
        Extract all features for a photo.
        
        Args:
            image_path: Path to image
            scene_embedding: Pre-computed scene embedding
            quality_fn: Function to compute quality score
            aesthetic_fn: Function to compute aesthetic score
        Returns:
            PhotoFeatures object
        """
        # Detect faces
        faces = self.detect_faces(image_path)
        
        # Compute quality score
        quality_score = quality_fn(image_path) if quality_fn else 0.5
        
        # Compute aesthetic score
        aesthetic_score = aesthetic_fn(image_path) if aesthetic_fn else 0.5
        
        return PhotoFeatures(
            path=image_path,
            scene_embedding=scene_embedding,
            faces=faces,
            quality_score=quality_score,
            aesthetic_score=aesthetic_score
        )


def export_face_scorer_config(output_path: str, face_weight: float = 0.3,
                             face_threshold: float = 0.6):
    """Export face scorer configuration for on-device use."""
    config = {
        'face_weight': face_weight,
        'scene_weight': 1 - face_weight,
        'face_threshold': face_threshold,
        'face_model': 'mobilefacenet_int8',
        'face_input_size': [112, 112],
        'face_embedding_dim': 128
    }
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Face scorer config exported to {output_path}")


def generate_dart_face_scorer() -> str:
    """Generate Dart code for face-aware scoring."""
    dart_code = '''
/// Face-aware scoring for photo duplicate detection
class FaceAwareScorer {
  static const double defaultFaceWeight = 0.3;
  static const double defaultFaceThreshold = 0.6;
  
  final double faceWeight;
  final double faceThreshold;
  
  FaceAwareScorer({
    this.faceWeight = defaultFaceWeight,
    this.faceThreshold = defaultFaceThreshold,
  });
  
  /// Compute combined similarity score
  Map<String, double> computeCombinedSimilarity(
    List<double> sceneEmbedding1,
    List<double> sceneEmbedding2,
    List<FaceData>? faces1,
    List<FaceData>? faces2,
  ) {
    // Compute scene similarity (cosine)
    double sceneSim = _cosineSimilarity(sceneEmbedding1, sceneEmbedding2);
    
    // Compute face similarity
    double faceSim = 0.0;
    int numMatches = 0;
    
    if (faces1 != null && faces1.isNotEmpty && 
        faces2 != null && faces2.isNotEmpty) {
      var result = _computeFaceJaccard(faces1, faces2);
      faceSim = result['jaccard']!;
      numMatches = result['matches']!.toInt();
    }
    
    // Combined score
    bool hasFaces = (faces1?.isNotEmpty ?? false) || 
                   (faces2?.isNotEmpty ?? false);
    
    double combinedScore;
    if (hasFaces) {
      combinedScore = (1 - faceWeight) * sceneSim + faceWeight * faceSim;
    } else {
      combinedScore = sceneSim;
    }
    
    return {
      'combined_score': combinedScore,
      'scene_similarity': sceneSim,
      'face_similarity': faceSim,
      'num_face_matches': numMatches.toDouble(),
      'has_faces': hasFaces ? 1.0 : 0.0,
    };
  }
  
  /// Compute cosine similarity between embeddings
  double _cosineSimilarity(List<double> a, List<double> b) {
    if (a.length != b.length) {
      throw ArgumentError('Embeddings must have same dimension');
    }
    
    double dotProduct = 0.0;
    double normA = 0.0;
    double normB = 0.0;
    
    for (int i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    
    if (normA == 0 || normB == 0) return 0.0;
    
    return dotProduct / (sqrt(normA) * sqrt(normB));
  }
  
  /// Compute Jaccard similarity between face sets
  Map<String, double> _computeFaceJaccard(
    List<FaceData> faces1,
    List<FaceData> faces2,
  ) {
    int matches = 0;
    Set<int> matched2 = {};
    
    for (var f1 in faces1) {
      for (int j = 0; j < faces2.length; j++) {
        if (matched2.contains(j)) continue;
        
        var f2 = faces2[j];
        double sim = _cosineSimilarity(f1.embedding, f2.embedding);
        
        if (sim > (1 - faceThreshold)) {
          matches++;
          matched2.add(j);
          break;
        }
      }
    }
    
    double jaccard = matches / 
        (faces1.length + faces2.length - matches);
    
    return {
      'jaccard': jaccard,
      'matches': matches.toDouble(),
    };
  }
}

/// Face data container
class FaceData {
  final List<double> embedding;
  final Rect bbox;
  final double confidence;
  
  FaceData({
    required this.embedding,
    required this.bbox,
    required this.confidence,
  });
}
'''
    return dart_code


def main():
    """Test face-aware scoring."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Face-aware scoring')
    parser.add_argument('--image1', type=str, required=True)
    parser.add_argument('--image2', type=str, required=True)
    parser.add_argument('--use_tflite', action='store_true')
    parser.add_argument('--mobilefacenet_path', type=str, default=None)
    parser.add_argument('--export_config', type=str, default=None)
    parser.add_argument('--export_dart', type=str, default=None)
    
    args = parser.parse_args()
    
    # Export config if requested
    if args.export_config:
        export_face_scorer_config(args.export_config)
    
    # Export Dart code if requested
    if args.export_dart:
        dart_code = generate_dart_face_scorer()
        with open(args.export_dart, 'w') as f:
            f.write(dart_code)
        print(f"Dart code exported to {args.export_dart}")
    
    # Test scoring
    if args.image1 and args.image2:
        scorer = FaceAwareScorer(
            use_tflite=args.use_tflite,
            mobilefacenet_path=args.mobilefacenet_path
        )
        
        # Dummy scene embeddings for testing
        scene_emb1 = np.random.randn(128)
        scene_emb1 /= np.linalg.norm(scene_emb1)
        
        scene_emb2 = np.random.randn(128)
        scene_emb2 /= np.linalg.norm(scene_emb2)
        
        # Extract features
        features1 = scorer.extract_photo_features(args.image1, scene_emb1)
        features2 = scorer.extract_photo_features(args.image2, scene_emb2)
        
        # Compute similarity
        similarity = scorer.compute_combined_similarity(features1, features2)
        
        print(f"\nSimilarity results:")
        for key, value in similarity.items():
            print(f"  {key}: {value:.4f}")
        
        print(f"\nFaces detected:")
        print(f"  Image 1: {len(features1.faces)} faces")
        print(f"  Image 2: {len(features2.faces)} faces")


if __name__ == '__main__':
    main()