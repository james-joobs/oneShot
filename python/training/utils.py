#!/usr/bin/env python3
"""
Shared utilities for the DINOv2 training pipeline.
Common functions used across multiple components.
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import time
from datetime import datetime
import shutil


class ProjectPaths:
    """Centralized path management for the project."""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create all necessary directories."""
        directories = [
            self.embeddings_dir,
            self.pca_dir,
            self.checkpoints_dir,
            self.tflite_dir,
            self.configs_dir,
            self.logs_dir
        ]
        for directory in directories:
            directory.mkdir(exist_ok=True, parents=True)
    
    @property
    def embeddings_dir(self) -> Path:
        return self.base_dir / "embeddings"
    
    @property
    def pca_dir(self) -> Path:
        return self.base_dir / "pca_params"
    
    @property
    def checkpoints_dir(self) -> Path:
        return self.base_dir / "checkpoints"
    
    @property
    def tflite_dir(self) -> Path:
        return self.base_dir / "tflite_models"
    
    @property
    def configs_dir(self) -> Path:
        return self.base_dir / "configs"
    
    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"
    
    def get_timestamped_path(self, base_path: Path, suffix: str = "") -> Path:
        """Get path with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = base_path.stem
        extension = base_path.suffix
        return base_path.parent / f"{stem}_{timestamp}{suffix}{extension}"


class ConfigManager:
    """Manage configuration files across the project."""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_dir.mkdir(exist_ok=True, parents=True)
    
    def save_config(self, name: str, config: Dict[str, Any]) -> Path:
        """Save configuration to file."""
        config_path = self.config_dir / f"{name}.json"
        
        # Add metadata
        config_with_meta = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "component": name
            },
            "config": config
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_with_meta, f, indent=2)
        
        return config_path
    
    def load_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        config_path = self.config_dir / f"{name}.json"
        
        if not config_path.exists():
            return None
        
        with open(config_path, 'r') as f:
            config_with_meta = json.load(f)
        
        return config_with_meta.get("config", {})
    
    def list_configs(self) -> List[str]:
        """List all available configurations."""
        return [f.stem for f in self.config_dir.glob("*.json")]


class FileHasher:
    """File integrity checking utilities."""
    
    @staticmethod
    def compute_file_hash(filepath: Path, algorithm: str = "md5") -> str:
        """Compute hash of file contents."""
        hash_func = hashlib.new(algorithm)
        
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    @staticmethod
    def verify_file_integrity(filepath: Path, expected_hash: str, 
                            algorithm: str = "md5") -> bool:
        """Verify file hasn't been corrupted."""
        actual_hash = FileHasher.compute_file_hash(filepath, algorithm)
        return actual_hash == expected_hash
    
    @staticmethod
    def create_checksum_file(filepath: Path, algorithm: str = "md5") -> Path:
        """Create checksum file alongside the original."""
        checksum = FileHasher.compute_file_hash(filepath, algorithm)
        checksum_path = filepath.with_suffix(f"{filepath.suffix}.{algorithm}")
        
        with open(checksum_path, 'w') as f:
            f.write(f"{checksum}  {filepath.name}\n")
        
        return checksum_path


class PerformanceProfiler:
    """Simple performance profiling utilities."""
    
    def __init__(self):
        self.timings = {}
        self.start_times = {}
    
    def start(self, operation: str):
        """Start timing an operation."""
        self.start_times[operation] = time.time()
    
    def end(self, operation: str) -> float:
        """End timing and return duration."""
        if operation not in self.start_times:
            raise ValueError(f"No start time recorded for operation: {operation}")
        
        duration = time.time() - self.start_times[operation]
        self.timings[operation] = duration
        del self.start_times[operation]
        
        return duration
    
    def get_summary(self) -> Dict[str, float]:
        """Get summary of all timings."""
        return self.timings.copy()
    
    def save_profile(self, filepath: Path):
        """Save profiling results to file."""
        profile_data = {
            "timings": self.timings,
            "total_time": sum(self.timings.values()),
            "created_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(profile_data, f, indent=2)


class ModelMetadata:
    """Track model metadata and lineage."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.metadata = {
            "model_name": model_name,
            "created_at": datetime.now().isoformat(),
            "steps": [],
            "files": {},
            "performance": {}
        }
    
    def add_step(self, step_name: str, parameters: Dict[str, Any], 
                 input_files: List[str] = None, output_files: List[str] = None):
        """Add a processing step to the lineage."""
        step = {
            "step_name": step_name,
            "timestamp": datetime.now().isoformat(),
            "parameters": parameters,
            "input_files": input_files or [],
            "output_files": output_files or []
        }
        self.metadata["steps"].append(step)
    
    def add_file(self, file_type: str, filepath: str, hash_value: str = None):
        """Add file to metadata."""
        if hash_value is None and Path(filepath).exists():
            hash_value = FileHasher.compute_file_hash(Path(filepath))
        
        self.metadata["files"][file_type] = {
            "path": filepath,
            "hash": hash_value,
            "size_bytes": Path(filepath).stat().st_size if Path(filepath).exists() else 0,
            "created_at": datetime.now().isoformat()
        }
    
    def add_performance(self, metric_name: str, value: float, unit: str = ""):
        """Add performance metric."""
        self.metadata["performance"][metric_name] = {
            "value": value,
            "unit": unit,
            "measured_at": datetime.now().isoformat()
        }
    
    def save(self, filepath: Path):
        """Save metadata to file."""
        with open(filepath, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    @classmethod
    def load(cls, filepath: Path) -> 'ModelMetadata':
        """Load metadata from file."""
        with open(filepath, 'r') as f:
            metadata = json.load(f)
        
        instance = cls(metadata["model_name"])
        instance.metadata = metadata
        return instance


class DatasetValidator:
    """Validate datasets and provide recommendations."""
    
    @staticmethod
    def validate_image_directory(image_dir: Path) -> Dict[str, Any]:
        """Validate image directory structure and contents."""
        if not image_dir.exists():
            return {"valid": False, "error": "Directory does not exist"}
        
        # Find images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(image_dir.glob(f'**/*{ext}'))
            image_files.extend(image_dir.glob(f'**/*{ext.upper()}'))
        
        if not image_files:
            return {"valid": False, "error": "No images found"}
        
        # Check file sizes
        total_size = sum(f.stat().st_size for f in image_files)
        avg_size = total_size / len(image_files)
        
        # Basic validation
        validation = {
            "valid": True,
            "num_images": len(image_files),
            "total_size_mb": total_size / (1024 * 1024),
            "avg_size_mb": avg_size / (1024 * 1024),
            "extensions": list(set(f.suffix.lower() for f in image_files))
        }
        
        # Add recommendations
        recommendations = []
        
        if len(image_files) < 10:
            recommendations.append("Very small dataset. Consider adding more images for better results.")
        elif len(image_files) < 100:
            recommendations.append("Small dataset. Quick mode recommended.")
        elif len(image_files) > 1000:
            recommendations.append("Large dataset. Consider using --max_images to limit processing time.")
        
        if avg_size > 10 * 1024 * 1024:  # > 10MB
            recommendations.append("Large image files detected. Consider resizing for faster processing.")
        
        validation["recommendations"] = recommendations
        
        return validation
    
    @staticmethod
    def estimate_processing_time(num_images: int, mode: str = "quick") -> Dict[str, float]:
        """Estimate processing time based on dataset size."""
        # Rough estimates based on typical performance
        if mode == "quick":
            embedding_time = num_images * 0.2  # 0.2s per image
            pca_time = max(3, num_images * 0.01)  # Minimum 3s
            total_time = embedding_time + pca_time
        else:  # full mode
            labeling_time = num_images * 0.5
            embedding_time = num_images * 0.2
            pca_time = max(3, num_images * 0.01)
            training_time = max(300, num_images * 2)  # Minimum 5 minutes
            export_time = 60
            total_time = labeling_time + embedding_time + pca_time + training_time + export_time
        
        return {
            "estimated_total_minutes": total_time / 60,
            "estimated_total_seconds": total_time,
            "mode": mode,
            "num_images": num_images
        }


def setup_project_structure(base_dir: str = ".") -> ProjectPaths:
    """Initialize project structure and return path manager."""
    paths = ProjectPaths(base_dir)
    
    # Create a project info file
    info = {
        "project_name": "DINOv2 Photo Duplicate Detection",
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "structure_version": "unified_v1"
    }
    
    with open(paths.base_dir / "project_info.json", 'w') as f:
        json.dump(info, f, indent=2)
    
    return paths


def cleanup_old_files(base_dir: Path, days_old: int = 7):
    """Clean up old temporary files."""
    cutoff_time = time.time() - (days_old * 24 * 60 * 60)
    
    patterns = ["*.tmp", "*.temp", "*_backup_*"]
    
    for pattern in patterns:
        for filepath in base_dir.glob(f"**/{pattern}"):
            if filepath.stat().st_mtime < cutoff_time:
                try:
                    if filepath.is_file():
                        filepath.unlink()
                    elif filepath.is_dir():
                        shutil.rmtree(filepath)
                except Exception as e:
                    print(f"Warning: Could not delete {filepath}: {e}")


def main():
    """Utility functions demo."""
    print("🛠️ DINOv2 Project Utilities")
    print("This module provides shared utilities for the training pipeline.")
    
    # Demo the validator
    import sys
    if len(sys.argv) > 1:
        image_dir = Path(sys.argv[1])
        validation = DatasetValidator.validate_image_directory(image_dir)
        
        print(f"\n📊 Dataset Validation Results:")
        for key, value in validation.items():
            print(f"  {key}: {value}")
        
        if validation["valid"]:
            estimates = DatasetValidator.estimate_processing_time(
                validation["num_images"], "quick"
            )
            print(f"\n⏱️ Estimated Processing Time (Quick Mode):")
            print(f"  ~{estimates['estimated_total_minutes']:.1f} minutes")


if __name__ == '__main__':
    main()