import cv2
import numpy as np
from PIL import Image
import tensorflow as tf

class ImageProcessor:
    def __init__(self, target_size=(224, 224)):
        self.target_size = target_size
    
    def load_and_preprocess_image(self, image_path):
        try:
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            image = image.resize(self.target_size, Image.Resampling.LANCZOS)
            
            image_array = np.array(image, dtype=np.float32)
            
            image_array = np.expand_dims(image_array, axis=0)
            
            return image_array
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    def preprocess_batch(self, image_paths):
        processed_images = []
        valid_paths = []
        
        for path in image_paths:
            img = self.load_and_preprocess_image(path)
            if img is not None:
                processed_images.append(img)
                valid_paths.append(path)
        
        if processed_images:
            return np.vstack(processed_images), valid_paths
        else:
            return np.array([]), []
    
    def get_image_info(self, image_path):
        try:
            with Image.open(image_path) as img:
                return {
                    'path': image_path,
                    'size': img.size,
                    'mode': img.mode,
                    'format': img.format
                }
        except Exception as e:
            return {'path': image_path, 'error': str(e)}