#!/usr/bin/env python3
"""
PCA and whitening transformation for embedding dimension reduction.
Compatible with both PyTorch training and TFLite post-processing.
"""

import numpy as np
import torch
import torch.nn as nn
from sklearn.decomposition import PCA
from typing import Optional, Tuple, Dict
import json
import pickle
from pathlib import Path


class PCAWhitening:
    """PCA with whitening transformation."""
    
    def __init__(self, n_components: int = 128, whiten: bool = True,
                 variance_threshold: float = 0.95):
        """
        Args:
            n_components: Number of components to keep
            whiten: Whether to apply whitening
            variance_threshold: Minimum variance to retain (0.95 = 95%)
        """
        self.n_components = n_components
        self.whiten = whiten
        self.variance_threshold = variance_threshold
        self.pca = None
        self.mean_ = None
        self.components_ = None
        self.explained_variance_ = None
        self.whitening_matrix_ = None
    
    def fit(self, embeddings: np.ndarray):
        """
        Fit PCA on training embeddings.
        
        Args:
            embeddings: Training embeddings of shape (N, D)
        """
        # Validate and adjust n_components based on data
        n_samples, n_features = embeddings.shape
        max_components = min(n_samples, n_features)
        
        if self.n_components > max_components:
            print(f"⚠️  Requested {self.n_components} components, but maximum possible is {max_components}")
            print(f"🔧 Reducing to {max_components} components")
            self.n_components = max_components
        
        # Fit PCA
        self.pca = PCA(n_components=self.n_components, whiten=self.whiten)
        self.pca.fit(embeddings)
        
        # Store transformation parameters
        self.mean_ = self.pca.mean_
        self.components_ = self.pca.components_
        self.explained_variance_ = self.pca.explained_variance_
        
        # Find optimal number of components based on variance threshold
        cumsum_variance = np.cumsum(self.pca.explained_variance_ratio_)
        optimal_components = np.argmax(cumsum_variance >= self.variance_threshold) + 1
        
        # Ensure we don't exceed the minimum of samples or features
        max_possible = min(embeddings.shape[0] - 1, embeddings.shape[1])
        optimal_components = min(optimal_components, max_possible, self.n_components)
        
        if optimal_components < self.n_components:
            print(f"Reducing to {optimal_components} components to retain {self.variance_threshold*100}% variance")
            self.n_components = optimal_components
            self.components_ = self.components_[:optimal_components]
            self.explained_variance_ = self.explained_variance_[:optimal_components]
        
        # Compute whitening matrix if needed
        if self.whiten:
            # Whitening: W = D^(-1/2) * V^T where D is diagonal matrix of eigenvalues
            self.whitening_matrix_ = self.components_ / np.sqrt(self.explained_variance_[:, np.newaxis])
        
        print(f"PCA fitted: {self.n_components} components, "
              f"variance retained: {cumsum_variance[self.n_components-1]:.4f}")
    
    def transform(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Apply PCA transformation.
        
        Args:
            embeddings: Embeddings of shape (N, D)
        Returns:
            Transformed embeddings of shape (N, n_components)
        """
        if self.pca is None:
            raise ValueError("PCA not fitted. Call fit() first.")
        
        # Center the embeddings
        centered = embeddings - self.mean_
        
        # Apply PCA transformation
        if self.whiten and self.whitening_matrix_ is not None:
            transformed = np.dot(centered, self.whitening_matrix_.T)
        else:
            transformed = np.dot(centered, self.components_.T)
        
        return transformed
    
    def save(self, save_dir: str):
        """
        Save PCA parameters for later use.
        
        Args:
            save_dir: Directory to save parameters
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(exist_ok=True, parents=True)
        
        # Save as numpy arrays for compatibility
        np.save(save_dir / 'pca_mean.npy', self.mean_)
        np.save(save_dir / 'pca_components.npy', self.components_)
        np.save(save_dir / 'pca_explained_variance.npy', self.explained_variance_)
        
        if self.whitening_matrix_ is not None:
            np.save(save_dir / 'pca_whitening_matrix.npy', self.whitening_matrix_)
        
        # Save metadata
        metadata = {
            'n_components': int(self.n_components),
            'whiten': bool(self.whiten),
            'variance_threshold': float(self.variance_threshold),
            'input_dim': int(len(self.mean_)),
            'variance_retained': float(np.sum(self.pca.explained_variance_ratio_[:self.n_components]))
        }
        
        with open(save_dir / 'pca_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"PCA parameters saved to {save_dir}")
    
    def load(self, save_dir: str):
        """
        Load PCA parameters from disk.
        
        Args:
            save_dir: Directory containing saved parameters
        """
        save_dir = Path(save_dir)
        
        # Load numpy arrays
        self.mean_ = np.load(save_dir / 'pca_mean.npy')
        self.components_ = np.load(save_dir / 'pca_components.npy')
        self.explained_variance_ = np.load(save_dir / 'pca_explained_variance.npy')
        
        if (save_dir / 'pca_whitening_matrix.npy').exists():
            self.whitening_matrix_ = np.load(save_dir / 'pca_whitening_matrix.npy')
        
        # Load metadata
        with open(save_dir / 'pca_metadata.json', 'r') as f:
            metadata = json.load(f)
        
        self.n_components = metadata['n_components']
        self.whiten = metadata['whiten']
        self.variance_threshold = metadata['variance_threshold']
        
        print(f"PCA parameters loaded from {save_dir}")
    
    def export_for_tflite(self, export_path: str):
        """
        Export PCA parameters in a format suitable for TFLite post-processing.
        
        Args:
            export_path: Path to save the exported parameters
        """
        export_data = {
            'mean': self.mean_.tolist(),
            'transform_matrix': self.whitening_matrix_.tolist() if self.whitening_matrix_ is not None else self.components_.tolist(),
            'n_components': int(self.n_components),
            'input_dim': int(len(self.mean_)),
            'use_whitening': bool(self.whiten)
        }
        
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"PCA parameters exported for TFLite to {export_path}")
    
    def to_dart_code(self) -> str:
        """
        Generate Dart code for on-device PCA transformation.
        
        Returns:
            Dart code as string
        """
        dart_code = f'''
/// PCA transformation for embedding post-processing
class PCATransform {{
  static const int inputDim = {len(self.mean_)};
  static const int outputDim = {self.n_components};
  static const bool useWhitening = {str(self.whiten).lower()};
  
  // PCA mean vector
  static final List<double> mean = [
    {', '.join([f'{x:.6f}' for x in self.mean_[:10]])}{',' if len(self.mean_) > 10 else ''}
    {'// ... ' + str(len(self.mean_) - 10) + ' more values' if len(self.mean_) > 10 else ''}
  ];
  
  // Transformation matrix (components or whitening matrix)
  static final List<List<double>> transformMatrix = [
'''
        
        matrix = self.whitening_matrix_ if self.whitening_matrix_ is not None else self.components_
        
        # Add first few rows as example
        for i in range(min(3, len(matrix))):
            row_str = ', '.join([f'{x:.6f}' for x in matrix[i][:5]])
            if len(matrix[i]) > 5:
                row_str += f', /* ... {len(matrix[i]) - 5} more values */'
            dart_code += f'    [{row_str}],\n'
        
        if len(matrix) > 3:
            dart_code += f'    // ... {len(matrix) - 3} more rows\n'
        
        dart_code += '''  ];
  
  /// Apply PCA transformation to embedding
  static List<double> transform(List<double> embedding) {
    if (embedding.length != inputDim) {
      throw ArgumentError('Input embedding must have dimension $inputDim');
    }
    
    // Center the embedding
    List<double> centered = [];
    for (int i = 0; i < inputDim; i++) {
      centered.add(embedding[i] - mean[i]);
    }
    
    // Apply transformation
    List<double> result = List.filled(outputDim, 0.0);
    for (int i = 0; i < outputDim; i++) {
      double sum = 0.0;
      for (int j = 0; j < inputDim; j++) {
        sum += transformMatrix[i][j] * centered[j];
      }
      result[i] = sum;
    }
    
    // L2 normalize the result
    double norm = 0.0;
    for (double val in result) {
      norm += val * val;
    }
    norm = sqrt(norm);
    
    if (norm > 0) {
      for (int i = 0; i < result.length; i++) {
        result[i] /= norm;
      }
    }
    
    return result;
  }
}
'''
        return dart_code


class PCAWhiteningLayer(nn.Module):
    """PyTorch layer for PCA whitening (for inference)."""
    
    def __init__(self, pca_params_dir: str):
        super().__init__()
        
        # Load PCA parameters
        pca_params_dir = Path(pca_params_dir)
        mean = np.load(pca_params_dir / 'pca_mean.npy')
        
        if (pca_params_dir / 'pca_whitening_matrix.npy').exists():
            transform_matrix = np.load(pca_params_dir / 'pca_whitening_matrix.npy')
        else:
            transform_matrix = np.load(pca_params_dir / 'pca_components.npy')
        
        # Convert to PyTorch tensors and register as buffers
        self.register_buffer('mean', torch.from_numpy(mean).float())
        self.register_buffer('transform_matrix', torch.from_numpy(transform_matrix).float())
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply PCA transformation.
        
        Args:
            x: Input embeddings of shape (B, D)
        Returns:
            Transformed embeddings of shape (B, n_components)
        """
        # Center
        centered = x - self.mean
        
        # Transform
        transformed = torch.matmul(centered, self.transform_matrix.T)
        
        # L2 normalize
        transformed = torch.nn.functional.normalize(transformed, p=2, dim=1)
        
        return transformed


def fit_pca_on_embeddings(embeddings_path: str, save_dir: str,
                          n_components: int = 128, whiten: bool = True):
    """
    Fit PCA on a set of embeddings and save the parameters.
    
    Args:
        embeddings_path: Path to numpy file containing embeddings
        save_dir: Directory to save PCA parameters
        n_components: Number of PCA components
        whiten: Whether to apply whitening
    """
    # Load embeddings
    print(f"Loading embeddings from {embeddings_path}")
    embeddings = np.load(embeddings_path)
    print(f"Embeddings shape: {embeddings.shape}")
    
    # Provide helpful info about component limits
    n_samples, n_features = embeddings.shape
    max_components = min(n_samples, n_features)
    if n_components > max_components:
        print(f"ℹ️  Note: Will automatically reduce components from {n_components} to {max_components} based on data size")
    
    # Fit PCA
    pca = PCAWhitening(n_components=n_components, whiten=whiten)
    pca.fit(embeddings)
    
    # Save parameters
    pca.save(save_dir)
    
    # Export for TFLite
    pca.export_for_tflite(Path(save_dir) / 'pca_tflite.json')
    
    # Generate Dart code
    dart_code = pca.to_dart_code()
    with open(Path(save_dir) / 'pca_transform.dart', 'w') as f:
        f.write(dart_code)
    print(f"Dart code saved to {Path(save_dir) / 'pca_transform.dart'}")
    
    # Test transformation
    print("\nTesting transformation...")
    transformed = pca.transform(embeddings[:10])
    print(f"Transformed shape: {transformed.shape}")
    print(f"Transformed L2 norms: {np.linalg.norm(transformed, axis=1)[:5]}")


def main():
    """Main function for PCA fitting."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fit PCA on embeddings')
    parser.add_argument('--embeddings_path', type=str, required=True,
                       help='Path to numpy file containing embeddings')
    parser.add_argument('--save_dir', type=str, default='./pca_params',
                       help='Directory to save PCA parameters')
    parser.add_argument('--n_components', type=int, default=128,
                       help='Number of PCA components (will be limited by min(samples, features))')
    parser.add_argument('--no_whiten', action='store_true',
                       help='Disable whitening')
    
    args = parser.parse_args()
    
    fit_pca_on_embeddings(
        embeddings_path=args.embeddings_path,
        save_dir=args.save_dir,
        n_components=args.n_components,
        whiten=not args.no_whiten
    )


if __name__ == '__main__':
    main()