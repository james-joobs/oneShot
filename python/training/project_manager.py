#!/usr/bin/env python3
"""
🎯 DINOv2 Project Manager
Unified interface for managing the entire project lifecycle.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
import json

# Import our pipeline components
from .pipeline import ColorfulLogger, create_quick_pipeline, create_full_pipeline
from .utils import (
    ProjectPaths, ConfigManager, DatasetValidator, 
    ModelMetadata, PerformanceProfiler, setup_project_structure
)


class ProjectManager:
    """Central manager for the DINOv2 project."""
    
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.paths = setup_project_structure(project_dir)
        self.config_manager = ConfigManager(self.paths.configs_dir)
        self.profiler = PerformanceProfiler()
        
        ColorfulLogger.header("🎯 DINOv2 Project Manager")
        ColorfulLogger.info(f"Project directory: {self.project_dir.absolute()}")
    
    def validate_dataset(self, image_dir: str) -> bool:
        """Validate dataset and show recommendations."""
        ColorfulLogger.step(1, 1, "Dataset Validation")
        
        image_path = Path(image_dir)
        validation = DatasetValidator.validate_image_directory(image_path)
        
        if not validation["valid"]:
            ColorfulLogger.error(f"Dataset validation failed: {validation['error']}")
            return False
        
        # Show validation results
        ColorfulLogger.success("Dataset validation passed!")
        ColorfulLogger.result("Images found", str(validation["num_images"]))
        ColorfulLogger.result("Total size", f"{validation['total_size_mb']:.1f} MB")
        ColorfulLogger.result("Average size", f"{validation['avg_size_mb']:.2f} MB")
        ColorfulLogger.result("Extensions", ", ".join(validation["extensions"]))
        
        # Show recommendations
        if validation["recommendations"]:
            ColorfulLogger.warning("Recommendations:")
            for rec in validation["recommendations"]:
                ColorfulLogger.info(f"  • {rec}")
        
        # Show time estimates
        for mode in ["quick", "full"]:
            estimates = DatasetValidator.estimate_processing_time(
                validation["num_images"], mode
            )
            ColorfulLogger.result(
                f"Estimated time ({mode})", 
                f"~{estimates['estimated_total_minutes']:.1f} minutes"
            )
        
        return True
    
    def create_project(self, name: str, image_dir: str, mode: str = "quick") -> bool:
        """Create a new project with specified configuration."""
        ColorfulLogger.header(f"📁 Creating Project: {name}")
        
        # Validate dataset first
        if not self.validate_dataset(image_dir):
            return False
        
        # Create project configuration
        project_config = {
            "name": name,
            "image_dir": image_dir,
            "mode": mode,
            "created_at": self.profiler.timings.get("start", "unknown")
        }
        
        # Save configuration
        config_path = self.config_manager.save_config(f"project_{name}", project_config)
        ColorfulLogger.file_created(str(config_path))
        
        # Create project metadata
        metadata = ModelMetadata(name)
        metadata.add_step("project_creation", project_config)
        metadata.save(self.paths.configs_dir / f"{name}_metadata.json")
        
        ColorfulLogger.success(f"Project '{name}' created successfully!")
        ColorfulLogger.info(f"Run: uv run project-manager --run {name}")
        
        return True
    
    def run_project(self, name: str, non_interactive: bool = False) -> bool:
        """Run an existing project."""
        # Load project configuration
        project_config = self.config_manager.load_config(f"project_{name}")
        
        if not project_config:
            ColorfulLogger.error(f"Project '{name}' not found!")
            ColorfulLogger.info("Available projects:")
            for config_name in self.config_manager.list_configs():
                if config_name.startswith("project_"):
                    proj_name = config_name.replace("project_", "")
                    ColorfulLogger.info(f"  • {proj_name}")
            return False
        
        ColorfulLogger.header(f"🚀 Running Project: {name}")
        ColorfulLogger.info(f"Mode: {project_config['mode']}")
        ColorfulLogger.info(f"Images: {project_config['image_dir']}")
        
        # Create output directory for this project
        project_output_dir = self.project_dir / "projects" / name
        
        # Create and run pipeline
        if project_config["mode"] == "quick":
            pipeline = create_quick_pipeline(
                project_config["image_dir"], 
                str(project_output_dir), 
                interactive=not non_interactive
            )
        else:
            pipeline = create_full_pipeline(
                project_config["image_dir"], 
                str(project_output_dir), 
                interactive=not non_interactive
            )
        
        # Run the pipeline
        success = pipeline.run()
        
        if success:
            # Update project metadata
            try:
                metadata_path = self.paths.configs_dir / f"{name}_metadata.json"
                if metadata_path.exists():
                    metadata = ModelMetadata.load(metadata_path)
                else:
                    metadata = ModelMetadata(name)
                
                metadata.add_step("pipeline_execution", {
                    "mode": project_config["mode"],
                    "interactive": not non_interactive,
                    "output_dir": str(project_output_dir)
                })
                metadata.save(metadata_path)
            except Exception as e:
                ColorfulLogger.warning(f"Could not update metadata: {e}")
        
        return success
    
    def list_projects(self):
        """List all available projects."""
        ColorfulLogger.header("📋 Available Projects")
        
        project_configs = []
        for config_name in self.config_manager.list_configs():
            if config_name.startswith("project_"):
                config = self.config_manager.load_config(config_name)
                if config:
                    project_name = config_name.replace("project_", "")
                    project_configs.append((project_name, config))
        
        if not project_configs:
            ColorfulLogger.info("No projects found.")
            ColorfulLogger.info("Create one with: uv run project-manager --create <name> --image_dir <path>")
            return
        
        for name, config in project_configs:
            ColorfulLogger.result("Project", name)
            ColorfulLogger.info(f"  Mode: {config.get('mode', 'unknown')}")
            ColorfulLogger.info(f"  Images: {config.get('image_dir', 'unknown')}")
            ColorfulLogger.info(f"  Created: {config.get('created_at', 'unknown')}")
            print()
    
    def status(self, name: Optional[str] = None):
        """Show project status."""
        if name:
            # Show specific project status
            self._show_project_status(name)
        else:
            # Show overall project status
            self._show_overall_status()
    
    def _show_project_status(self, name: str):
        """Show status for a specific project."""
        ColorfulLogger.header(f"📊 Project Status: {name}")
        
        # Load metadata
        metadata_path = self.paths.configs_dir / f"{name}_metadata.json"
        if metadata_path.exists():
            metadata = ModelMetadata.load(metadata_path)
            
            ColorfulLogger.result("Steps completed", str(len(metadata.metadata["steps"])))
            ColorfulLogger.result("Files created", str(len(metadata.metadata["files"])))
            
            if metadata.metadata["performance"]:
                ColorfulLogger.info("Performance metrics:")
                for metric, data in metadata.metadata["performance"].items():
                    ColorfulLogger.info(f"  • {metric}: {data['value']} {data['unit']}")
            
            # Check for output files
            project_dir = self.project_dir / "projects" / name
            if project_dir.exists():
                ColorfulLogger.result("Output directory", str(project_dir))
                
                # Check for key files
                key_files = [
                    "embeddings/embeddings.npy",
                    "pca_params/pca_transform.dart", 
                    "tflite_models/model_int8.tflite",
                    "checkpoints/best_model.pth"
                ]
                
                ColorfulLogger.info("Generated files:")
                for file_path in key_files:
                    full_path = project_dir / file_path
                    status = "✅" if full_path.exists() else "❌"
                    ColorfulLogger.info(f"  {status} {file_path}")
        else:
            ColorfulLogger.warning("No metadata found for this project")
    
    def _show_overall_status(self):
        """Show overall project status."""
        ColorfulLogger.header("📊 Project Overview")
        
        # Count projects
        project_count = len([c for c in self.config_manager.list_configs() 
                           if c.startswith("project_")])
        ColorfulLogger.result("Total projects", str(project_count))
        
        # Check disk usage
        if self.project_dir.exists():
            total_size = sum(f.stat().st_size for f in self.project_dir.rglob('*') if f.is_file())
            ColorfulLogger.result("Total disk usage", f"{total_size / (1024**3):.2f} GB")
        
        # Check for dependencies
        ColorfulLogger.info("Checking dependencies...")
        try:
            import torch
            import tensorflow
            import cv2
            ColorfulLogger.success("All dependencies available")
        except ImportError as e:
            ColorfulLogger.error(f"Missing dependency: {e}")
    
    def cleanup(self, days: int = 7):
        """Clean up old temporary files."""
        ColorfulLogger.header("🧹 Project Cleanup")
        
        from .utils import cleanup_old_files
        
        ColorfulLogger.progress(f"Cleaning up files older than {days} days...")
        cleanup_old_files(self.project_dir, days)
        ColorfulLogger.success("Cleanup completed!")
    
    def export_project(self, name: str, output_path: str):
        """Export project for sharing or backup."""
        ColorfulLogger.header(f"📦 Exporting Project: {name}")
        
        import shutil
        
        project_dir = self.project_dir / "projects" / name
        config = self.config_manager.load_config(f"project_{name}")
        
        if not project_dir.exists() or not config:
            ColorfulLogger.error("Project not found or incomplete")
            return False
        
        # Create export package
        export_dir = Path(output_path) / f"{name}_export"
        export_dir.mkdir(exist_ok=True, parents=True)
        
        # Copy project files
        if project_dir.exists():
            shutil.copytree(project_dir, export_dir / "output", dirs_exist_ok=True)
        
        # Copy configuration
        config_src = self.paths.configs_dir / f"project_{name}.json"
        if config_src.exists():
            shutil.copy2(config_src, export_dir / "project_config.json")
        
        # Copy metadata
        metadata_src = self.paths.configs_dir / f"{name}_metadata.json"
        if metadata_src.exists():
            shutil.copy2(metadata_src, export_dir / "metadata.json")
        
        # Create README
        readme_content = f"""# DINOv2 Project Export: {name}

## Project Information
- **Mode**: {config.get('mode', 'unknown')}
- **Source Images**: {config.get('image_dir', 'unknown')}
- **Created**: {config.get('created_at', 'unknown')}
- **Exported**: {ColorfulLogger._colorize('Generated automatically', 'cyan')}

## Contents
- `output/` - Generated models and files
- `project_config.json` - Project configuration
- `metadata.json` - Project metadata and lineage

## Mobile Deployment
Key files for mobile integration:
- `output/tflite_models/*.tflite` - TensorFlow Lite models
- `output/pca_params/pca_transform.dart` - Dart transformation code
- `output/pca_params/pca_tflite.json` - TFLite configuration

## Usage
Import these files into your Flutter/Android project for photo duplicate detection.
"""
        
        with open(export_dir / "README.md", 'w') as f:
            f.write(readme_content)
        
        ColorfulLogger.success(f"Project exported to: {export_dir}")
        return True


def main():
    """Main project manager interface."""
    parser = argparse.ArgumentParser(
        description="🎯 DINOv2 Project Manager - Unified project management interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create new project
  uv run project-manager --create my_photos --image_dir ./photos --mode quick
  
  # Run existing project  
  uv run project-manager --run my_photos --non-interactive
  
  # List all projects
  uv run project-manager --list
  
  # Show project status
  uv run project-manager --status my_photos
  
  # Export project
  uv run project-manager --export my_photos --output ./exports
        """
    )
    
    # Main commands
    parser.add_argument('--create', type=str, metavar='NAME',
                       help='Create new project with given name')
    parser.add_argument('--run', type=str, metavar='NAME',
                       help='Run existing project')
    parser.add_argument('--list', action='store_true',
                       help='List all projects')
    parser.add_argument('--status', type=str, metavar='NAME', nargs='?', const='',
                       help='Show project status (or overall if no name)')
    parser.add_argument('--export', type=str, metavar='NAME',
                       help='Export project for sharing')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', nargs='?', const=7,
                       help='Clean up files older than N days (default: 7)')
    
    # Configuration options
    parser.add_argument('--image_dir', type=str,
                       help='Image directory (for --create)')
    parser.add_argument('--mode', type=str, choices=['quick', 'full'], default='quick',
                       help='Pipeline mode (for --create)')
    parser.add_argument('--output', type=str, default='./exports',
                       help='Output directory (for --export)')
    parser.add_argument('--non-interactive', action='store_true',
                       help='Run without user prompts')
    parser.add_argument('--project_dir', type=str, default='.',
                       help='Project root directory')
    
    args = parser.parse_args()
    
    # Initialize project manager
    manager = ProjectManager(args.project_dir)
    
    # Execute commands
    if args.create:
        if not args.image_dir:
            ColorfulLogger.error("--image_dir required for --create")
            sys.exit(1)
        success = manager.create_project(args.create, args.image_dir, args.mode)
        sys.exit(0 if success else 1)
    
    elif args.run:
        success = manager.run_project(args.run, args.non_interactive)
        sys.exit(0 if success else 1)
    
    elif args.list:
        manager.list_projects()
    
    elif args.status is not None:
        if args.status:
            manager.status(args.status)
        else:
            manager.status()
    
    elif args.export:
        success = manager.export_project(args.export, args.output)
        sys.exit(0 if success else 1)
    
    elif args.cleanup is not None:
        manager.cleanup(args.cleanup)
    
    else:
        # Show help if no command specified
        ColorfulLogger.info("Welcome to DINOv2 Project Manager!")
        ColorfulLogger.info("Use --help to see available commands")
        ColorfulLogger.info("")
        ColorfulLogger.info("Quick start:")
        ColorfulLogger.info("  1. uv run project-manager --create my_project --image_dir ./photos")
        ColorfulLogger.info("  2. uv run project-manager --run my_project")


if __name__ == '__main__':
    main()