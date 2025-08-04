import os
import glob
import time
import numpy as np
from typing import List, Dict, Any
from models.mobilenet_similarity import MobileNetSimilarityModel
from preprocessing.image_processor import ImageProcessor
from similarity.similarity_calculator import SimilarityCalculator

class PhotoCurator:
    def __init__(self, similarity_threshold=0.85, target_size=(224, 224)):
        self.similarity_threshold = similarity_threshold
        self.target_size = target_size
        
        print("Initializing MobileNetV3 similarity model...")
        self.model = MobileNetSimilarityModel(
            input_shape=(*target_size, 3),
            embedding_dim=512
        )
        
        self.processor = ImageProcessor(target_size=target_size)
        self.similarity_calc = SimilarityCalculator(similarity_threshold=similarity_threshold)
        
        print("Model initialized successfully!")
    
    def process_photos(self, image_folder: str) -> Dict[str, Any]:
        print(f"Processing photos in: {image_folder}")
        
        image_paths = self._get_image_paths(image_folder)
        print(f"Found {len(image_paths)} images")
        
        if not image_paths:
            return {"error": "No images found in the specified folder"}
        
        start_time = time.time()
        
        embeddings, valid_paths = self._extract_embeddings(image_paths)
        
        if len(embeddings) == 0:
            return {"error": "No valid images could be processed"}
        
        print(f"Extracted embeddings for {len(valid_paths)} images")
        
        clusters = self.similarity_calc.greedy_clustering(embeddings, valid_paths)
        duplicate_pairs, similarity_matrix = self.similarity_calc.find_duplicate_pairs(embeddings, valid_paths)
        
        processing_time = time.time() - start_time
        
        results = {
            "total_images": len(image_paths),
            "processed_images": len(valid_paths),
            "clusters": clusters,
            "duplicate_pairs": duplicate_pairs,
            "processing_time_seconds": processing_time,
            "avg_time_per_image": processing_time / len(valid_paths) if valid_paths else 0,
            "similarity_matrix": similarity_matrix.tolist(),
            "recommended_photos": self._get_recommended_photos(clusters)
        }
        
        return results
    
    def _get_image_paths(self, folder: str) -> List[str]:
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff']
        image_paths = []
        
        for ext in extensions:
            pattern = os.path.join(folder, '**', ext)
            image_paths.extend(glob.glob(pattern, recursive=True))
            pattern = os.path.join(folder, '**', ext.upper())
            image_paths.extend(glob.glob(pattern, recursive=True))
        
        return sorted(list(set(image_paths)))
    
    def _extract_embeddings(self, image_paths: List[str]) -> tuple:
        embeddings = []
        valid_paths = []
        
        print("Extracting embeddings...")
        for i, path in enumerate(image_paths):
            if i % 10 == 0:
                print(f"Processing image {i+1}/{len(image_paths)}")
            
            img_array = self.processor.load_and_preprocess_image(path)
            if img_array is not None:
                embedding = self.model.get_embeddings(img_array)
                embeddings.append(embedding[0])
                valid_paths.append(path)
        
        return np.array(embeddings), valid_paths
    
    def _get_recommended_photos(self, clusters: List[Dict]) -> List[str]:
        recommended = []
        for cluster in clusters:
            recommended.append(cluster['representative'])
        return recommended
    
    def save_model_for_tflite(self, output_path: str):
        print(f"Saving model for TFLite conversion to: {output_path}")
        self.model.save_for_tflite(output_path)
        print("Model saved successfully!")
    
    def print_summary(self, results: Dict[str, Any]):
        print("\n" + "="*60)
        print("PHOTO CURATION RESULTS")
        print("="*60)
        print(f"Total images found: {results['total_images']}")
        print(f"Successfully processed: {results['processed_images']}")
        print(f"Processing time: {results['processing_time_seconds']:.2f} seconds")
        print(f"Average time per image: {results['avg_time_per_image']*1000:.1f} ms")
        print(f"Found {len(results['clusters'])} clusters")
        print(f"Found {len(results['duplicate_pairs'])} duplicate pairs")
        print(f"Recommended photos: {len(results['recommended_photos'])}")
        
        if results['duplicate_pairs']:
            print("\nDuplicate pairs found:")
            for pair in results['duplicate_pairs'][:5]:
                img1_name = os.path.basename(pair['image1'])
                img2_name = os.path.basename(pair['image2'])
                print(f"  {img1_name} <-> {img2_name} (similarity: {pair['similarity']:.3f})")
            if len(results['duplicate_pairs']) > 5:
                print(f"  ... and {len(results['duplicate_pairs']) - 5} more pairs")
        
        print(f"\nReduction: {results['total_images']} -> {len(results['recommended_photos'])} photos")
        reduction_percent = (1 - len(results['recommended_photos']) / results['total_images']) * 100
        print(f"Space saved: {reduction_percent:.1f}%")
        print("="*60)