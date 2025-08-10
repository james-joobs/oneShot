#!/usr/bin/env python3
"""
Auto-labeler for generating positive/negative training pairs for duplicate photo detection.
Groups photos by session (time/GPS proximity) and uses ORB+RANSAC for labeling.
"""

import os
import csv
import numpy as np
import cv2
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
from pathlib import Path
from tqdm import tqdm
import exifread
from geopy.distance import geodesic
from dataclasses import dataclass
import json


@dataclass
class PhotoMetadata:
    """Metadata for a photo."""
    path: str
    timestamp: Optional[datetime]
    gps_coords: Optional[Tuple[float, float]]  # (lat, lon)
    session_id: Optional[int] = None


class PhotoSessionGrouper:
    """Groups photos into sessions based on time and GPS proximity."""
    
    def __init__(self, time_threshold_seconds: int = 30, gps_threshold_meters: float = 50):
        self.time_threshold = timedelta(seconds=time_threshold_seconds)
        self.gps_threshold = gps_threshold_meters
    
    def extract_metadata(self, image_path: str) -> PhotoMetadata:
        """Extract timestamp and GPS from EXIF data."""
        timestamp = None
        gps_coords = None
        
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                
                # Extract timestamp
                date_taken = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
                if date_taken:
                    timestamp = datetime.strptime(str(date_taken), '%Y:%m:%d %H:%M:%S')
                
                # Extract GPS coordinates
                gps_lat = tags.get('GPS GPSLatitude')
                gps_lat_ref = tags.get('GPS GPSLatitudeRef')
                gps_lon = tags.get('GPS GPSLongitude')
                gps_lon_ref = tags.get('GPS GPSLongitudeRef')
                
                if all([gps_lat, gps_lat_ref, gps_lon, gps_lon_ref]):
                    lat = self._convert_to_degrees(gps_lat.values)
                    if str(gps_lat_ref) == 'S':
                        lat = -lat
                    lon = self._convert_to_degrees(gps_lon.values)
                    if str(gps_lon_ref) == 'W':
                        lon = -lon
                    gps_coords = (lat, lon)
        except Exception as e:
            print(f"Error extracting metadata from {image_path}: {e}")
        
        # Fallback to file modification time if no EXIF timestamp
        if timestamp is None:
            timestamp = datetime.fromtimestamp(os.path.getmtime(image_path))
        
        return PhotoMetadata(path=image_path, timestamp=timestamp, gps_coords=gps_coords)
    
    def _convert_to_degrees(self, value):
        """Convert GPS coordinates to degrees."""
        d = float(value[0].num) / float(value[0].den)
        m = float(value[1].num) / float(value[1].den)
        s = float(value[2].num) / float(value[2].den)
        return d + (m / 60.0) + (s / 3600.0)
    
    def group_by_session(self, photos: List[PhotoMetadata]) -> List[List[PhotoMetadata]]:
        """Group photos into sessions based on time and GPS proximity."""
        if not photos:
            return []
        
        # Sort by timestamp
        photos.sort(key=lambda x: x.timestamp if x.timestamp else datetime.min)
        
        sessions = []
        current_session = [photos[0]]
        current_session_id = 0
        photos[0].session_id = current_session_id
        
        for photo in photos[1:]:
            # Check if photo belongs to current session
            belongs_to_session = False
            
            for session_photo in current_session:
                # Check time proximity
                if photo.timestamp and session_photo.timestamp:
                    time_diff = abs(photo.timestamp - session_photo.timestamp)
                    if time_diff <= self.time_threshold:
                        # Check GPS proximity if available
                        if photo.gps_coords and session_photo.gps_coords:
                            distance = geodesic(photo.gps_coords, session_photo.gps_coords).meters
                            if distance <= self.gps_threshold:
                                belongs_to_session = True
                                break
                        else:
                            # Only time-based if no GPS
                            belongs_to_session = True
                            break
            
            if belongs_to_session:
                current_session.append(photo)
                photo.session_id = current_session_id
            else:
                # Start new session
                sessions.append(current_session)
                current_session_id += 1
                current_session = [photo]
                photo.session_id = current_session_id
        
        # Add last session
        if current_session:
            sessions.append(current_session)
        
        return sessions


class ORBMatcher:
    """ORB feature matching with RANSAC for duplicate detection."""
    
    def __init__(self, n_features: int = 500, thumbnail_size: int = 320,
                 reproj_threshold: float = 3.0, min_inliers: int = 50,
                 min_inlier_ratio: float = 0.3):
        self.n_features = n_features
        self.thumbnail_size = thumbnail_size
        self.reproj_threshold = reproj_threshold
        self.min_inliers = min_inliers
        self.min_inlier_ratio = min_inlier_ratio
        self.orb = cv2.ORB_create(nfeatures=n_features)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    
    def load_and_resize(self, image_path: str) -> np.ndarray:
        """Load image and resize to thumbnail."""
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        h, w = img.shape
        if max(h, w) > self.thumbnail_size:
            scale = self.thumbnail_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        return img
    
    def extract_features(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Extract ORB keypoints and descriptors."""
        keypoints, descriptors = self.orb.detectAndCompute(image, None)
        if descriptors is None:
            return np.array([]), None
        
        # Convert keypoints to numpy array
        kp_array = np.array([[kp.pt[0], kp.pt[1]] for kp in keypoints])
        return kp_array, descriptors
    
    def match_images(self, img_path1: str, img_path2: str) -> Dict:
        """Match two images and return matching statistics."""
        try:
            # Load images
            img1 = self.load_and_resize(img_path1)
            img2 = self.load_and_resize(img_path2)
            
            # Extract features
            kp1, desc1 = self.extract_features(img1)
            kp2, desc2 = self.extract_features(img2)
            
            if desc1 is None or desc2 is None or len(kp1) < 4 or len(kp2) < 4:
                return {
                    'inliers': 0,
                    'total_matches': 0,
                    'inlier_ratio': 0.0,
                    'mean_parallax': float('inf'),
                    'is_duplicate': False
                }
            
            # Match descriptors
            matches = self.matcher.match(desc1, desc2)
            
            if len(matches) < 4:
                return {
                    'inliers': 0,
                    'total_matches': len(matches),
                    'inlier_ratio': 0.0,
                    'mean_parallax': float('inf'),
                    'is_duplicate': False
                }
            
            # Get matched points
            src_pts = np.float32([kp1[m.queryIdx] for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx] for m in matches]).reshape(-1, 1, 2)
            
            # Find homography with RANSAC
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, self.reproj_threshold)
            
            if mask is None:
                inliers = 0
            else:
                inliers = mask.ravel().sum()
            
            inlier_ratio = inliers / len(matches) if len(matches) > 0 else 0
            
            # Calculate mean parallax for inliers
            mean_parallax = float('inf')
            if inliers > 0 and mask is not None:
                inlier_src = src_pts[mask.ravel() == 1]
                inlier_dst = dst_pts[mask.ravel() == 1]
                parallax = np.linalg.norm(inlier_dst - inlier_src, axis=1)
                mean_parallax = np.mean(parallax)
            
            # Determine if duplicate
            is_duplicate = (inliers >= self.min_inliers and 
                          inlier_ratio >= self.min_inlier_ratio)
            
            return {
                'inliers': int(inliers),
                'total_matches': len(matches),
                'inlier_ratio': float(inlier_ratio),
                'mean_parallax': float(mean_parallax),
                'is_duplicate': is_duplicate
            }
            
        except Exception as e:
            print(f"Error matching {img_path1} and {img_path2}: {e}")
            return {
                'inliers': 0,
                'total_matches': 0,
                'inlier_ratio': 0.0,
                'mean_parallax': float('inf'),
                'is_duplicate': False
            }


class TrainingPairGenerator:
    """Generate training pairs with labels."""
    
    def __init__(self, session_grouper: PhotoSessionGrouper, orb_matcher: ORBMatcher):
        self.session_grouper = session_grouper
        self.orb_matcher = orb_matcher
    
    def generate_pairs(self, image_dir: str, output_csv: str, 
                       max_pairs_per_session: int = 50,
                       hard_negative_parallax_threshold: float = 5.0):
        """Generate training pairs and save to CSV."""
        
        # Find all images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        image_paths = []
        for ext in image_extensions:
            image_paths.extend(Path(image_dir).glob(f'**/*{ext}'))
            image_paths.extend(Path(image_dir).glob(f'**/*{ext.upper()}'))
        
        print(f"Found {len(image_paths)} images")
        
        # Extract metadata
        photos = []
        for path in tqdm(image_paths, desc="Extracting metadata"):
            metadata = self.session_grouper.extract_metadata(str(path))
            photos.append(metadata)
        
        # Group by session
        sessions = self.session_grouper.group_by_session(photos)
        print(f"Grouped into {len(sessions)} sessions")
        
        # Generate pairs
        pairs = []
        
        # Process each session
        for session_idx, session in enumerate(tqdm(sessions, desc="Processing sessions")):
            if len(session) < 2:
                continue
            
            # Generate positive and hard negative pairs within session
            session_pairs = []
            for i in range(len(session)):
                for j in range(i + 1, min(i + 10, len(session))):  # Limit comparisons
                    match_result = self.orb_matcher.match_images(
                        session[i].path, session[j].path
                    )
                    
                    if match_result['is_duplicate']:
                        # Positive pair
                        pairs.append({
                            'image_a': session[i].path,
                            'image_b': session[j].path,
                            'label': 'positive',
                            'session_a': session_idx,
                            'session_b': session_idx,
                            'inliers': match_result['inliers'],
                            'inlier_ratio': match_result['inlier_ratio'],
                            'mean_parallax': match_result['mean_parallax']
                        })
                    elif match_result['mean_parallax'] >= hard_negative_parallax_threshold:
                        # Hard negative (same session, different content)
                        pairs.append({
                            'image_a': session[i].path,
                            'image_b': session[j].path,
                            'label': 'hard_negative',
                            'session_a': session_idx,
                            'session_b': session_idx,
                            'inliers': match_result['inliers'],
                            'inlier_ratio': match_result['inlier_ratio'],
                            'mean_parallax': match_result['mean_parallax']
                        })
                    
                    if len(session_pairs) >= max_pairs_per_session:
                        break
                
                if len(session_pairs) >= max_pairs_per_session:
                    break
        
        # Generate strong negatives (different sessions)
        n_strong_negatives = min(len(pairs) // 2, len(sessions) * 10)
        for _ in range(n_strong_negatives):
            # Random pairs from different sessions
            if len(sessions) < 2:
                break
            
            session1_idx = np.random.randint(0, len(sessions))
            session2_idx = np.random.randint(0, len(sessions))
            
            if session1_idx == session2_idx:
                continue
            
            if len(sessions[session1_idx]) > 0 and len(sessions[session2_idx]) > 0:
                photo1 = np.random.choice(sessions[session1_idx])
                photo2 = np.random.choice(sessions[session2_idx])
                
                pairs.append({
                    'image_a': photo1.path,
                    'image_b': photo2.path,
                    'label': 'strong_negative',
                    'session_a': session1_idx,
                    'session_b': session2_idx,
                    'inliers': 0,
                    'inlier_ratio': 0.0,
                    'mean_parallax': float('inf')
                })
        
        # Save to CSV
        df = pd.DataFrame(pairs)
        df.to_csv(output_csv, index=False)
        
        # Print statistics
        print(f"\nGenerated {len(pairs)} training pairs:")
        print(f"  Positives: {len(df[df['label'] == 'positive'])}")
        print(f"  Hard negatives: {len(df[df['label'] == 'hard_negative'])}")
        print(f"  Strong negatives: {len(df[df['label'] == 'strong_negative'])}")
        print(f"Saved to {output_csv}")
        
        return df


def main():
    """Main function to run auto-labeling."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto-label training pairs for duplicate detection')
    parser.add_argument('--image_dir', type=str, required=True,
                       help='Directory containing images')
    parser.add_argument('--output_csv', type=str, default='pairs.csv',
                       help='Output CSV file for training pairs')
    parser.add_argument('--time_threshold', type=int, default=30,
                       help='Time threshold in seconds for session grouping')
    parser.add_argument('--gps_threshold', type=float, default=50,
                       help='GPS threshold in meters for session grouping')
    parser.add_argument('--n_features', type=int, default=500,
                       help='Number of ORB features to extract')
    parser.add_argument('--thumbnail_size', type=int, default=320,
                       help='Thumbnail size for feature extraction')
    parser.add_argument('--min_inliers', type=int, default=50,
                       help='Minimum inliers for positive match')
    parser.add_argument('--min_inlier_ratio', type=float, default=0.3,
                       help='Minimum inlier ratio for positive match')
    
    args = parser.parse_args()
    
    # Initialize components
    session_grouper = PhotoSessionGrouper(
        time_threshold_seconds=args.time_threshold,
        gps_threshold_meters=args.gps_threshold
    )
    
    orb_matcher = ORBMatcher(
        n_features=args.n_features,
        thumbnail_size=args.thumbnail_size,
        min_inliers=args.min_inliers,
        min_inlier_ratio=args.min_inlier_ratio
    )
    
    generator = TrainingPairGenerator(session_grouper, orb_matcher)
    
    # Generate pairs
    generator.generate_pairs(
        image_dir=args.image_dir,
        output_csv=args.output_csv
    )


if __name__ == '__main__':
    main()