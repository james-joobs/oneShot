#!/usr/bin/env python3
"""
Extract embeddings from images using a trained DINOv2 model.
This creates the embeddings.npy file needed for PCA fitting.
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Optional
import json
from tqdm import tqdm
from torchvision import transforms
import argparse


class EmbeddingExtractor:
    """Extract embeddings from images using DINOv2 model."""
    
    def __init__(self, model_path: Optional[str] = None, 
                 model_name: str = "facebook/dinov2-small",
                 device: str = "auto"):
        """
        Args:
            model_path: Path to trained model checkpoint (optional)
            model_name: Base DINOv2 model name
            device: Device to use ('cuda', 'cpu', or 'auto')
        """
        self.device = device if device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.transform = None
        
        self._load_model(model_path, model_name)
        self._setup_transforms()
    
    def _load_model(self, model_path: Optional[str], model_name: str):
        """Load the DINOv2 model."""
        self.is_trained_model = False
        
        if model_path and Path(model_path).exists():
            # Load trained model
            print(f"Loading trained model from {model_path}")
            try:
                from dinov2_finetune import DINOv2RetrievalModel
                self.model = DINOv2RetrievalModel(model_name=model_name)
                
                checkpoint = torch.load(model_path, map_location=self.device)
                if 'model_state_dict' in checkpoint:
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                else:
                    self.model.load_state_dict(checkpoint)
                    
                self.is_trained_model = True
                print("✅ Loaded trained model with projection head")
            except Exception as e:
                print(f"❌ Failed to load trained model: {e}")
                print("🔄 Falling back to base DINOv2 model")
                self._load_base_model(model_name)
        else:
            # Load base DINOv2 model
            self._load_base_model(model_name)
    
    def _load_base_model(self, model_name: str):
        """Load base DINOv2 model from HuggingFace."""
        print(f"Loading base DINOv2 model: {model_name}")
        from transformers import AutoModel
        
        self.model = AutoModel.from_pretrained(model_name)
        self.is_trained_model = False  # This is a base model
        print("✅ Loaded base DINOv2 model")
    
    def _setup_transforms(self):
        """Setup image preprocessing transforms."""
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def extract_single_embedding(self, image_path: str) -> np.ndarray:
        """
        Extract embedding from a single image.
        
        Args:
            image_path: Path to image
        Returns:
            Embedding vector
        """
        try:
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')
            input_tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            # Extract embedding
            with torch.no_grad():
                if self.is_trained_model:
                    # Trained model with projection head - returns tensor directly
                    embedding = self.model(input_tensor)
                else:
                    # Base DINOv2 model from HuggingFace
                    outputs = self.model(input_tensor)
                    
                    # Extract tensor from the model outputs
                    if hasattr(outputs, 'last_hidden_state'):
                        # Use CLS token (first token)
                        embedding = outputs.last_hidden_state[:, 0, :]
                    elif hasattr(outputs, 'pooler_output') and outputs.pooler_output is not None:
                        # Use pooler output if available
                        embedding = outputs.pooler_output
                    elif isinstance(outputs, tuple) and len(outputs) > 0:
                        # Tuple output - take first element and CLS token
                        embedding = outputs[0][:, 0, :]
                    else:
                        # Direct tensor access as fallback
                        if hasattr(outputs, 'shape') and len(outputs.shape) == 3:
                            embedding = outputs[:, 0, :]  # Take CLS token
                        else:
                            raise ValueError(f"Cannot extract embedding from output type: {type(outputs)}")
                
                # Convert to numpy
                if isinstance(embedding, torch.Tensor):
                    embedding = embedding.cpu().numpy()
                else:
                    raise ValueError(f"Expected torch.Tensor but got {type(embedding)}")
                
                # Remove batch dimension if present
                if len(embedding.shape) > 1:
                    embedding = embedding[0]
                
                # L2 normalize
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                
                return embedding
                
        except Exception as e:
            print(f"❌ Failed to process {image_path}: {e}")
            return None
    
    def extract_embeddings_from_directory(self, image_dir: str, 
                                        extensions: List[str] = ['.jpg', '.jpeg', '.png'],
                                        max_images: Optional[int] = None) -> tuple:
        """
        Extract embeddings from all images in a directory.
        
        Args:
            image_dir: Directory containing images
            extensions: Image file extensions to process
            max_images: Maximum number of images to process
        Returns:
            (embeddings_array, image_paths_list)
        """
        image_dir = Path(image_dir)
        
        # Find all images
        image_paths = []
        for ext in extensions:
            image_paths.extend(image_dir.glob(f'**/*{ext}'))
            image_paths.extend(image_dir.glob(f'**/*{ext.upper()}'))
        
        if max_images:
            image_paths = image_paths[:max_images]
        
        print(f"Found {len(image_paths)} images to process")
        
        if not image_paths:
            raise ValueError(f"No images found in {image_dir}")
        
        # Extract embeddings
        embeddings = []
        valid_paths = []
        
        self.model.eval()
        self.model.to(self.device)
        
        for img_path in tqdm(image_paths, desc="Extracting embeddings"):
            embedding = self.extract_single_embedding(str(img_path))
            if embedding is not None:
                embeddings.append(embedding)
                valid_paths.append(str(img_path))
        
        if not embeddings:
            raise ValueError("No valid embeddings extracted")
        
        embeddings_array = np.array(embeddings)
        print(f"✅ Extracted {len(embeddings_array)} embeddings with shape {embeddings_array.shape}")
        
        return embeddings_array, valid_paths
    
    def extract_embeddings_from_csv(self, csv_path: str, 
                                   max_images: Optional[int] = None) -> tuple:
        """
        Extract embeddings from images listed in a CSV file.
        
        Args:
            csv_path: Path to CSV file with image paths
            max_images: Maximum number of images to process
        Returns:
            (embeddings_array, image_paths_list)
        """
        import pandas as pd
        
        df = pd.read_csv(csv_path)
        
        # Get unique image paths
        image_paths = set()
        if 'image_a' in df.columns:
            image_paths.update(df['image_a'].tolist())
        if 'image_b' in df.columns:
            image_paths.update(df['image_b'].tolist())
        if 'path' in df.columns:
            image_paths.update(df['path'].tolist())
        
        image_paths = list(image_paths)
        
        if max_images:
            image_paths = image_paths[:max_images]
        
        print(f"Found {len(image_paths)} unique images in CSV")
        
        # Extract embeddings
        embeddings = []
        valid_paths = []
        
        self.model.eval()
        self.model.to(self.device)
        
        for img_path in tqdm(image_paths, desc="Extracting embeddings from CSV"):
            if Path(img_path).exists():
                embedding = self.extract_single_embedding(img_path)
                if embedding is not None:
                    embeddings.append(embedding)
                    valid_paths.append(img_path)
            else:
                print(f"⚠️ Image not found: {img_path}")
        
        if not embeddings:
            raise ValueError("No valid embeddings extracted")
        
        embeddings_array = np.array(embeddings)
        print(f"✅ Extracted {len(embeddings_array)} embeddings with shape {embeddings_array.shape}")
        
        return embeddings_array, valid_paths


def save_embeddings(embeddings: np.ndarray, paths: List[str], 
                   output_dir: str, name_prefix: str = "embeddings"):
    """Save embeddings and metadata."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Save embeddings
    embeddings_path = output_dir / f"{name_prefix}.npy"
    np.save(embeddings_path, embeddings)
    
    # Save metadata
    metadata = {
        'num_embeddings': len(embeddings),
        'embedding_dim': embeddings.shape[1],
        'image_paths': paths,
        'mean_norm': float(np.mean(np.linalg.norm(embeddings, axis=1))),
        'std_norm': float(np.std(np.linalg.norm(embeddings, axis=1)))
    }
    
    metadata_path = output_dir / f"{name_prefix}_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"💾 Saved embeddings to {embeddings_path}")
    print(f"💾 Saved metadata to {metadata_path}")
    
    return embeddings_path, metadata_path


def main():
    """Main extraction function."""
    parser = argparse.ArgumentParser(description='Extract embeddings from images')
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--image_dir', type=str,
                           help='Directory containing images')
    input_group.add_argument('--csv_path', type=str,
                           help='CSV file with image paths')
    
    # Model options
    parser.add_argument('--model_path', type=str, default=None,
                       help='Path to trained model checkpoint')
    parser.add_argument('--model_name', type=str, default='facebook/dinov2-small',
                       help='Base DINOv2 model name')
    
    # Output options
    parser.add_argument('--output_dir', type=str, default='./embeddings',
                       help='Output directory for embeddings')
    parser.add_argument('--name_prefix', type=str, default='embeddings',
                       help='Prefix for output files')
    
    # Processing options
    parser.add_argument('--max_images', type=int, default=None,
                       help='Maximum number of images to process')
    parser.add_argument('--device', type=str, default='auto',
                       choices=['auto', 'cuda', 'cpu'],
                       help='Device to use for inference')
    
    args = parser.parse_args()
    
    print("🚀 Starting embedding extraction...")
    print(f"Device: {args.device}")
    
    # Initialize extractor
    extractor = EmbeddingExtractor(
        model_path=args.model_path,
        model_name=args.model_name,
        device=args.device
    )
    
    # Extract embeddings
    if args.image_dir:
        print(f"📁 Processing images from directory: {args.image_dir}")
        embeddings, paths = extractor.extract_embeddings_from_directory(
            args.image_dir, max_images=args.max_images
        )
    else:
        print(f"📄 Processing images from CSV: {args.csv_path}")
        embeddings, paths = extractor.extract_embeddings_from_csv(
            args.csv_path, max_images=args.max_images
        )
    
    # Save results
    embeddings_path, metadata_path = save_embeddings(
        embeddings, paths, args.output_dir, args.name_prefix
    )
    
    print(f"\n✅ Extraction complete!")
    print(f"📊 Extracted {len(embeddings)} embeddings")
    print(f"📏 Embedding dimension: {embeddings.shape[1]}")
    print(f"💾 Embeddings file: {embeddings_path}")
    
    print(f"\n🔄 Next steps:")
    print(f"uv run fit-pca --embeddings_path {embeddings_path} --save_dir pca_params")


if __name__ == '__main__':
    main()