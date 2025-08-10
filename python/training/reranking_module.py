#!/usr/bin/env python3
"""
On-device re-ranking module specification using ORB+RANSAC.
Designed for efficient re-ranking within photo session clusters.
"""

import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json
from pathlib import Path
from sklearn.cluster import DBSCAN


@dataclass
class RerankingCandidate:
    """Candidate photo for re-ranking."""
    image_path: str
    scene_embedding: np.ndarray
    initial_score: float
    cluster_id: Optional[int] = None
    orb_features: Optional[Tuple[np.ndarray, np.ndarray]] = None


class SessionClusterer:
    """Cluster photos within sessions based on scene embeddings."""
    
    def __init__(self, eps: float = 0.25, min_samples: int = 2,
                 metric: str = 'cosine'):
        """
        Args:
            eps: Maximum distance between samples (cosine distance)
            min_samples: Minimum samples to form a cluster
            metric: Distance metric ('cosine' or 'euclidean')
        """
        self.eps = eps
        self.min_samples = min_samples
        self.metric = metric
    
    def cluster_session(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Cluster photos within a session.
        
        Args:
            embeddings: Scene embeddings of shape (N, D)
        Returns:
            Cluster labels (-1 for noise)
        """
        # Apply DBSCAN clustering
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric=self.metric
        ).fit(embeddings)
        
        return clustering.labels_
    
    def get_cluster_representatives(self, embeddings: np.ndarray,
                                   labels: np.ndarray,
                                   max_per_cluster: int = 30) -> Dict[int, List[int]]:
        """
        Get top candidates from each cluster.
        
        Args:
            embeddings: Scene embeddings
            labels: Cluster labels
            max_per_cluster: Maximum candidates per cluster
        Returns:
            Dictionary mapping cluster_id to list of indices
        """
        representatives = {}
        
        for cluster_id in np.unique(labels):
            if cluster_id == -1:  # Skip noise
                continue
            
            # Get indices for this cluster
            cluster_indices = np.where(labels == cluster_id)[0]
            
            if len(cluster_indices) <= max_per_cluster:
                representatives[cluster_id] = cluster_indices.tolist()
            else:
                # Select diverse representatives
                cluster_embeddings = embeddings[cluster_indices]
                
                # Compute centroid
                centroid = np.mean(cluster_embeddings, axis=0)
                
                # Sort by distance to centroid
                distances = np.linalg.norm(
                    cluster_embeddings - centroid, axis=1
                )
                sorted_indices = cluster_indices[np.argsort(distances)]
                
                # Take evenly spaced samples
                step = len(sorted_indices) / max_per_cluster
                selected = [sorted_indices[int(i * step)] 
                           for i in range(max_per_cluster)]
                
                representatives[cluster_id] = selected
        
        return representatives


class ORBReranker:
    """ORB-based re-ranking within clusters."""
    
    def __init__(self, n_features: int = 500, scale_factor: float = 1.2,
                 n_levels: int = 8, edge_threshold: int = 31,
                 first_level: int = 0, wta_k: int = 2,
                 score_type: int = cv2.ORB_HARRIS_SCORE,
                 patch_size: int = 31, fast_threshold: int = 20):
        """
        Initialize ORB detector with optimized parameters.
        """
        self.orb = cv2.ORB_create(
            nfeatures=n_features,
            scaleFactor=scale_factor,
            nLevels=n_levels,
            edgeThreshold=edge_threshold,
            firstLevel=first_level,
            WTA_K=wta_k,
            scoreType=score_type,
            patchSize=patch_size,
            fastThreshold=fast_threshold
        )
        
        # Matcher for ORB descriptors
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        # RANSAC parameters
        self.ransac_reproj_threshold = 3.0
        self.min_inliers = 50
        self.min_inlier_ratio = 0.3
    
    def extract_orb_features(self, image_path: str,
                            max_size: int = 640) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract ORB features from image.
        
        Args:
            image_path: Path to image
            max_size: Maximum image dimension for feature extraction
        Returns:
            Keypoints and descriptors
        """
        # Load image
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return np.array([]), None
        
        # Resize if needed
        h, w = img.shape
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Extract features
        keypoints, descriptors = self.orb.detectAndCompute(img, None)
        
        if descriptors is None:
            return np.array([]), None
        
        # Convert keypoints to numpy array
        kp_array = np.array([[kp.pt[0], kp.pt[1], kp.size, kp.angle] 
                            for kp in keypoints])
        
        return kp_array, descriptors
    
    def match_and_verify(self, desc1: np.ndarray, desc2: np.ndarray,
                        kp1: np.ndarray, kp2: np.ndarray) -> Dict[str, float]:
        """
        Match descriptors and verify with RANSAC.
        
        Args:
            desc1, desc2: ORB descriptors
            kp1, kp2: Keypoint arrays
        Returns:
            Matching statistics
        """
        if desc1 is None or desc2 is None:
            return {'inlier_ratio': 0.0, 'num_inliers': 0}
        
        # Match descriptors using KNN
        matches = self.matcher.knnMatch(desc1, desc2, k=2)
        
        # Apply Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        
        if len(good_matches) < 4:
            return {'inlier_ratio': 0.0, 'num_inliers': 0}
        
        # Get matched points
        src_pts = np.float32([kp1[m.queryIdx][:2] for m in good_matches])
        dst_pts = np.float32([kp2[m.trainIdx][:2] for m in good_matches])
        
        # Find homography with RANSAC
        M, mask = cv2.findHomography(
            src_pts, dst_pts, cv2.RANSAC, self.ransac_reproj_threshold
        )
        
        if mask is None:
            return {'inlier_ratio': 0.0, 'num_inliers': 0}
        
        num_inliers = mask.ravel().sum()
        inlier_ratio = num_inliers / len(good_matches)
        
        return {
            'inlier_ratio': float(inlier_ratio),
            'num_inliers': int(num_inliers),
            'total_matches': len(good_matches)
        }
    
    def rerank_cluster(self, candidates: List[RerankingCandidate],
                      alpha: float = 0.7, beta: float = 0.3) -> List[Tuple[int, float]]:
        """
        Re-rank candidates within a cluster.
        
        Args:
            candidates: List of candidates to re-rank
            alpha: Weight for scene similarity
            beta: Weight for ORB inlier ratio
        Returns:
            List of (index, score) tuples sorted by score
        """
        n = len(candidates)
        if n <= 1:
            return [(0, candidates[0].initial_score)] if n == 1 else []
        
        # Extract ORB features if not cached
        for i, cand in enumerate(candidates):
            if cand.orb_features is None:
                kp, desc = self.extract_orb_features(cand.image_path)
                cand.orb_features = (kp, desc)
        
        # Compute pairwise ORB similarities
        orb_similarities = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i + 1, n):
                kp1, desc1 = candidates[i].orb_features
                kp2, desc2 = candidates[j].orb_features
                
                if desc1 is not None and desc2 is not None:
                    match_result = self.match_and_verify(desc1, desc2, kp1, kp2)
                    similarity = match_result['inlier_ratio']
                    orb_similarities[i, j] = similarity
                    orb_similarities[j, i] = similarity
        
        # Compute scene similarities
        scene_embeddings = np.array([c.scene_embedding for c in candidates])
        scene_similarities = np.dot(scene_embeddings, scene_embeddings.T)
        
        # Combine scores
        combined_scores = []
        for i in range(n):
            # Average similarity to other images in cluster
            scene_sim = np.mean([scene_similarities[i, j] 
                                for j in range(n) if j != i])
            orb_sim = np.mean([orb_similarities[i, j] 
                              for j in range(n) if j != i])
            
            rerank_score = alpha * scene_sim + beta * orb_sim
            combined_scores.append((i, rerank_score))
        
        # Sort by score
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        
        return combined_scores


class OnDeviceReranker:
    """Complete on-device re-ranking pipeline."""
    
    def __init__(self, cluster_eps: float = 0.25,
                 cluster_min_samples: int = 2,
                 max_candidates_per_cluster: int = 30,
                 rerank_alpha: float = 0.7,
                 rerank_beta: float = 0.3):
        """
        Initialize re-ranking pipeline.
        """
        self.clusterer = SessionClusterer(
            eps=cluster_eps,
            min_samples=cluster_min_samples
        )
        self.orb_reranker = ORBReranker()
        self.max_candidates = max_candidates_per_cluster
        self.rerank_alpha = rerank_alpha
        self.rerank_beta = rerank_beta
    
    def process_session(self, photos: List[Dict]) -> List[Dict]:
        """
        Process a photo session with clustering and re-ranking.
        
        Args:
            photos: List of photo dictionaries with 'path' and 'embedding'
        Returns:
            Processed photos with cluster assignments and reranked scores
        """
        if not photos:
            return []
        
        # Extract embeddings
        embeddings = np.array([p['embedding'] for p in photos])
        
        # Cluster photos
        cluster_labels = self.clusterer.cluster_session(embeddings)
        
        # Get representatives from each cluster
        representatives = self.clusterer.get_cluster_representatives(
            embeddings, cluster_labels, self.max_candidates
        )
        
        # Process each cluster
        results = []
        
        for cluster_id, indices in representatives.items():
            # Create candidates
            candidates = []
            for idx in indices:
                candidate = RerankingCandidate(
                    image_path=photos[idx]['path'],
                    scene_embedding=embeddings[idx],
                    initial_score=photos[idx].get('score', 0.5),
                    cluster_id=cluster_id
                )
                candidates.append(candidate)
            
            # Re-rank within cluster
            reranked = self.orb_reranker.rerank_cluster(
                candidates, self.rerank_alpha, self.rerank_beta
            )
            
            # Add results
            for rank, (cand_idx, score) in enumerate(reranked):
                orig_idx = indices[cand_idx]
                results.append({
                    'path': photos[orig_idx]['path'],
                    'cluster_id': int(cluster_id),
                    'cluster_rank': rank,
                    'reranked_score': float(score),
                    'original_score': photos[orig_idx].get('score', 0.5)
                })
        
        # Add noise points (unclustered)
        noise_indices = np.where(cluster_labels == -1)[0]
        for idx in noise_indices:
            results.append({
                'path': photos[idx]['path'],
                'cluster_id': -1,
                'cluster_rank': 0,
                'reranked_score': photos[idx].get('score', 0.5),
                'original_score': photos[idx].get('score', 0.5)
            })
        
        return results


def export_reranking_config(output_path: str):
    """Export re-ranking configuration for on-device use."""
    config = {
        'clustering': {
            'eps': 0.25,
            'min_samples': 2,
            'metric': 'cosine',
            'max_candidates_per_cluster': 30
        },
        'orb': {
            'n_features': 500,
            'scale_factor': 1.2,
            'n_levels': 8,
            'edge_threshold': 31,
            'patch_size': 31,
            'fast_threshold': 20
        },
        'ransac': {
            'reproj_threshold': 3.0,
            'min_inliers': 50,
            'min_inlier_ratio': 0.3
        },
        'reranking': {
            'alpha_scene': 0.7,
            'beta_orb': 0.3
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Re-ranking config exported to {output_path}")


def generate_native_binding_spec() -> str:
    """Generate specification for native ORB+RANSAC binding."""
    spec = '''
// Native binding specification for ORB+RANSAC re-ranking
// To be implemented as platform-specific native code (iOS/Android)

#pragma once

#include <vector>
#include <string>

namespace photo_reranking {

struct ORBConfig {
    int n_features = 500;
    float scale_factor = 1.2f;
    int n_levels = 8;
    int edge_threshold = 31;
    int first_level = 0;
    int wta_k = 2;
    int score_type = 0;  // HARRIS_SCORE
    int patch_size = 31;
    int fast_threshold = 20;
};

struct RANSACConfig {
    float reproj_threshold = 3.0f;
    int min_inliers = 50;
    float min_inlier_ratio = 0.3f;
};

struct MatchResult {
    float inlier_ratio;
    int num_inliers;
    int total_matches;
};

class ORBMatcher {
public:
    ORBMatcher(const ORBConfig& orb_config, const RANSACConfig& ransac_config);
    ~ORBMatcher();
    
    // Extract ORB features from image file
    bool extractFeatures(const std::string& image_path,
                        std::vector<float>& keypoints,
                        std::vector<uint8_t>& descriptors);
    
    // Match two sets of features and verify with RANSAC
    MatchResult matchAndVerify(const std::vector<uint8_t>& desc1,
                               const std::vector<uint8_t>& desc2,
                               const std::vector<float>& kp1,
                               const std::vector<float>& kp2);
    
private:
    class Impl;
    std::unique_ptr<Impl> impl;
};

// Flutter/Dart FFI interface
extern "C" {
    // Create matcher instance
    void* orb_matcher_create(int n_features, float scale_factor,
                             float ransac_threshold, int min_inliers);
    
    // Extract features
    int orb_extract_features(void* matcher, const char* image_path,
                            float** keypoints, int* kp_count,
                            uint8_t** descriptors, int* desc_count);
    
    // Match features
    float orb_match_features(void* matcher,
                            const uint8_t* desc1, int desc1_count,
                            const uint8_t* desc2, int desc2_count,
                            const float* kp1, int kp1_count,
                            const float* kp2, int kp2_count,
                            int* out_inliers);
    
    // Cleanup
    void orb_matcher_destroy(void* matcher);
    void orb_free_memory(void* ptr);
}

} // namespace photo_reranking
'''
    return spec


def main():
    """Test re-ranking module."""
    import argparse
    
    parser = argparse.ArgumentParser(description='On-device re-ranking module')
    parser.add_argument('--test_dir', type=str, help='Directory with test images')
    parser.add_argument('--export_config', type=str, 
                       help='Export configuration file')
    parser.add_argument('--export_native_spec', type=str,
                       help='Export native binding specification')
    
    args = parser.parse_args()
    
    # Export config
    if args.export_config:
        export_reranking_config(args.export_config)
    
    # Export native spec
    if args.export_native_spec:
        spec = generate_native_binding_spec()
        with open(args.export_native_spec, 'w') as f:
            f.write(spec)
        print(f"Native spec exported to {args.export_native_spec}")
    
    # Test re-ranking
    if args.test_dir:
        # Create dummy test data
        test_photos = []
        for img_path in Path(args.test_dir).glob('*.jpg'):
            # Generate random embedding
            embedding = np.random.randn(128)
            embedding /= np.linalg.norm(embedding)
            
            test_photos.append({
                'path': str(img_path),
                'embedding': embedding,
                'score': np.random.random()
            })
        
        if test_photos:
            # Process session
            reranker = OnDeviceReranker()
            results = reranker.process_session(test_photos)
            
            print(f"\nProcessed {len(test_photos)} photos")
            print(f"Found {len(set(r['cluster_id'] for r in results))} clusters")
            
            # Print top results per cluster
            clusters = {}
            for r in results:
                if r['cluster_id'] not in clusters:
                    clusters[r['cluster_id']] = []
                clusters[r['cluster_id']].append(r)
            
            for cluster_id, photos in clusters.items():
                photos.sort(key=lambda x: x['cluster_rank'])
                print(f"\nCluster {cluster_id}:")
                for p in photos[:3]:
                    print(f"  Rank {p['cluster_rank']}: {Path(p['path']).name} "
                          f"(score: {p['reranked_score']:.3f})")


if __name__ == '__main__':
    main()