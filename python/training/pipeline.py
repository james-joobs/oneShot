#!/usr/bin/env python3
"""
🚀 DINOv2 Photo Duplicate Detection Training Pipeline
Automated pipeline with colorful logging and interactive confirmations.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import time
from datetime import datetime
import argparse


class ColorfulLogger:
    """Colorful terminal logging with emojis."""
    
    # ANSI color codes
    COLORS = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'bold': '\033[1m',
        'underline': '\033[4m',
        'reset': '\033[0m'
    }
    
    @classmethod
    def _colorize(cls, text: str, color: str) -> str:
        """Add color to text."""
        return f"{cls.COLORS.get(color, '')}{text}{cls.COLORS['reset']}"
    
    @classmethod
    def header(cls, text: str):
        """Print header with box."""
        border = "=" * (len(text) + 4)
        print(f"\n{cls._colorize(border, 'cyan')}")
        print(f"{cls._colorize(f'  {text}  ', 'cyan')}")
        print(f"{cls._colorize(border, 'cyan')}\n")
    
    @classmethod
    def step(cls, step_num: int, total_steps: int, title: str):
        """Print step header."""
        step_text = f"🔹 Step {step_num}/{total_steps}: {title}"
        print(f"\n{cls._colorize(step_text, 'blue')}")
        print(f"{cls._colorize('-' * len(step_text), 'blue')}")
    
    @classmethod
    def success(cls, message: str):
        """Print success message."""
        print(f"✅ {cls._colorize(message, 'green')}")
    
    @classmethod
    def warning(cls, message: str):
        """Print warning message."""
        print(f"⚠️  {cls._colorize(message, 'yellow')}")
    
    @classmethod
    def error(cls, message: str):
        """Print error message."""
        print(f"❌ {cls._colorize(message, 'red')}")
    
    @classmethod
    def info(cls, message: str):
        """Print info message."""
        print(f"ℹ️  {cls._colorize(message, 'cyan')}")
    
    @classmethod
    def progress(cls, message: str):
        """Print progress message."""
        print(f"🔄 {cls._colorize(message, 'magenta')}")
    
    @classmethod
    def result(cls, key: str, value: str):
        """Print key-value result."""
        print(f"📊 {cls._colorize(key + ':', 'bold')} {cls._colorize(value, 'white')}")
    
    @classmethod
    def file_created(cls, filepath: str):
        """Print file creation message."""
        print(f"📁 {cls._colorize('Created:', 'green')} {cls._colorize(filepath, 'white')}")
    
    @classmethod
    def command(cls, cmd: str):
        """Print command being executed."""
        print(f"⚡ {cls._colorize('Running:', 'yellow')} {cls._colorize(cmd, 'white')}")


class PipelineStep:
    """Individual pipeline step."""
    
    def __init__(self, name: str, description: str, command: List[str], 
                 required_files: List[str] = None, output_files: List[str] = None,
                 skip_confirmation: bool = False):
        self.name = name
        self.description = description
        self.command = command
        self.required_files = required_files or []
        self.output_files = output_files or []
        self.skip_confirmation = skip_confirmation
        self.start_time = None
        self.end_time = None
        self.success = False
    
    def check_prerequisites(self) -> bool:
        """Check if required files exist."""
        missing_files = []
        for filepath in self.required_files:
            if not Path(filepath).exists():
                missing_files.append(filepath)
        
        if missing_files:
            ColorfulLogger.error(f"Missing required files: {', '.join(missing_files)}")
            return False
        return True
    
    def execute(self) -> bool:
        """Execute the step command."""
        ColorfulLogger.command(' '.join(self.command))
        
        self.start_time = time.time()
        try:
            result = subprocess.run(
                self.command,
                check=True,
                capture_output=True,
                text=True
            )
            
            self.end_time = time.time()
            duration = self.end_time - self.start_time
            
            # Show output if there are warnings or important info
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if any(keyword in line.lower() for keyword in ['warning', 'error', 'failed', 'success', 'saved', 'exported']):
                        ColorfulLogger.info(line.strip())
            
            ColorfulLogger.success(f"Completed in {duration:.1f}s")
            self.success = True
            
            # Verify output files were created
            created_files = []
            for filepath in self.output_files:
                if Path(filepath).exists():
                    created_files.append(filepath)
                    ColorfulLogger.file_created(filepath)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.end_time = time.time()
            ColorfulLogger.error(f"Command failed with exit code {e.returncode}")
            if e.stderr:
                ColorfulLogger.error(f"Error: {e.stderr.strip()}")
            if e.stdout:
                ColorfulLogger.info(f"Output: {e.stdout.strip()}")
            return False
        except Exception as e:
            self.end_time = time.time()
            ColorfulLogger.error(f"Unexpected error: {str(e)}")
            return False


class TrainingPipeline:
    """Main training pipeline orchestrator."""
    
    def __init__(self, config: Dict[str, Any], interactive: bool = True):
        self.config = config
        self.steps = []
        self.results = {}
        self.start_time = None
        self.end_time = None
        self.interactive = interactive
        
    def add_step(self, step: PipelineStep):
        """Add a step to the pipeline."""
        self.steps.append(step)
    
    def confirm_step(self, step: PipelineStep) -> bool:
        """Ask user confirmation for a step."""
        if step.skip_confirmation or not self.interactive:
            if not self.interactive:
                ColorfulLogger.info(f"Auto-executing: {step.description}")
                ColorfulLogger.command(' '.join(step.command))
            return True
            
        ColorfulLogger.info(f"About to run: {step.description}")
        ColorfulLogger.command(' '.join(step.command))
        
        try:
            while True:
                response = input(f"\n🤔 Continue with this step? (y/n/skip/quit): ").lower().strip()
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no', 'skip']:
                    ColorfulLogger.warning("Skipping this step")
                    return False
                elif response in ['q', 'quit']:
                    ColorfulLogger.info("Pipeline stopped by user")
                    sys.exit(0)
                else:
                    print("Please enter 'y' (yes), 'n' (no/skip), or 'q' (quit)")
        except (EOFError, KeyboardInterrupt):
            ColorfulLogger.warning("\nNon-interactive mode detected, auto-continuing...")
            return True
    
    def run(self):
        """Execute the full pipeline."""
        ColorfulLogger.header("🚀 DINOv2 Training Pipeline Started")
        
        self.start_time = time.time()
        
        for i, step in enumerate(self.steps, 1):
            ColorfulLogger.step(i, len(self.steps), step.name)
            
            # Check prerequisites
            if not step.check_prerequisites():
                ColorfulLogger.error("Prerequisites not met. Stopping pipeline.")
                return False
            
            # Ask for confirmation
            if not self.confirm_step(step):
                continue
            
            # Execute step
            ColorfulLogger.progress(step.description)
            success = step.execute()
            
            if success:
                ColorfulLogger.success(f"✨ {step.name} completed successfully!")
            else:
                ColorfulLogger.error(f"💥 {step.name} failed!")
                
                retry = input("\n🔄 Retry this step? (y/n): ").lower().strip()
                if retry in ['y', 'yes']:
                    ColorfulLogger.progress("Retrying...")
                    success = step.execute()
                
                if not success:
                    should_continue = input("\n🚫 Continue with next steps despite failure? (y/n): ").lower().strip()
                    if should_continue not in ['y', 'yes']:
                        ColorfulLogger.error("Pipeline stopped due to failure")
                        return False
        
        self.end_time = time.time()
        self._show_final_summary()
        return True
    
    def _show_final_summary(self):
        """Show final pipeline summary."""
        total_time = self.end_time - self.start_time
        successful_steps = sum(1 for step in self.steps if step.success)
        
        ColorfulLogger.header("📋 Pipeline Summary")
        
        ColorfulLogger.result("Total Steps", str(len(self.steps)))
        ColorfulLogger.result("Successful", str(successful_steps))
        ColorfulLogger.result("Failed", str(len(self.steps) - successful_steps))
        ColorfulLogger.result("Total Time", f"{total_time:.1f}s")
        
        # Show step details
        print(f"\n{ColorfulLogger._colorize('Step Details:', 'bold')}")
        for i, step in enumerate(self.steps, 1):
            status = "✅" if step.success else "❌"
            duration = f"{step.end_time - step.start_time:.1f}s" if step.start_time and step.end_time else "N/A"
            print(f"  {status} Step {i}: {step.name} ({duration})")
        
        if successful_steps == len(self.steps):
            ColorfulLogger.success("🎉 All steps completed successfully!")
        else:
            ColorfulLogger.warning("⚠️ Some steps failed. Check the logs above.")


def create_full_pipeline(image_dir: str, base_output_dir: str = "./pipeline_output", interactive: bool = True) -> TrainingPipeline:
    """Create the complete training pipeline."""
    
    # Create output directories
    output_dir = Path(base_output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    embeddings_dir = output_dir / "embeddings"
    pca_dir = output_dir / "pca_params"
    checkpoints_dir = output_dir / "checkpoints"
    tflite_dir = output_dir / "tflite_models"
    
    config = {
        'image_dir': image_dir,
        'output_dir': str(output_dir),
        'embeddings_dir': str(embeddings_dir),
        'pca_dir': str(pca_dir),
        'checkpoints_dir': str(checkpoints_dir),
        'tflite_dir': str(tflite_dir)
    }
    
    pipeline = TrainingPipeline(config, interactive)
    
    # Step 1: Generate training pairs
    pipeline.add_step(PipelineStep(
        name="Auto-Label Training Pairs",
        description="Generate positive/negative pairs from photos using ORB+RANSAC",
        command=[
            "uv", "run", "auto-label",
            "--image_dir", image_dir,
            "--output_csv", str(output_dir / "training_pairs.csv"),
            "--min_inliers", "30",
            "--min_inlier_ratio", "0.25"
        ],
        required_files=[image_dir],
        output_files=[str(output_dir / "training_pairs.csv")]
    ))
    
    # Step 2: Extract embeddings
    pipeline.add_step(PipelineStep(
        name="Extract Embeddings",
        description="Extract DINOv2 embeddings from photos",
        command=[
            "uv", "run", "extract-embeddings",
            "--image_dir", image_dir,
            "--output_dir", str(embeddings_dir),
            "--max_images", "500"
        ],
        required_files=[image_dir],
        output_files=[str(embeddings_dir / "embeddings.npy")]
    ))
    
    # Step 3: Fit PCA
    pipeline.add_step(PipelineStep(
        name="Fit PCA Transformation",
        description="Apply PCA dimensionality reduction with whitening",
        command=[
            "uv", "run", "fit-pca",
            "--embeddings_path", str(embeddings_dir / "embeddings.npy"),
            "--save_dir", str(pca_dir),
            "--n_components", "128"
        ],
        required_files=[str(embeddings_dir / "embeddings.npy")],
        output_files=[
            str(pca_dir / "pca_mean.npy"),
            str(pca_dir / "pca_components.npy"),
            str(pca_dir / "pca_tflite.json"),
            str(pca_dir / "pca_transform.dart")
        ]
    ))
    
    # Step 4: Fine-tune model (optional)
    pipeline.add_step(PipelineStep(
        name="Fine-tune DINOv2 Model",
        description="Train DINOv2 with GeM pooling on labeled pairs (optional)",
        command=[
            "uv", "run", "train-dinov2",
            "--train_csv", str(output_dir / "training_pairs.csv"),
            "--checkpoint_dir", str(checkpoints_dir),
            "--num_epochs", "10",
            "--batch_size", "16",
            "--embedding_dim", "128"
        ],
        required_files=[str(output_dir / "training_pairs.csv")],
        output_files=[str(checkpoints_dir / "best_model.pth")]
    ))
    
    # Step 5: Export to TFLite
    pipeline.add_step(PipelineStep(
        name="Export TFLite Models",
        description="Convert model to mobile-friendly TFLite format",
        command=[
            "uv", "run", "export-tflite",
            "--checkpoint", str(checkpoints_dir / "best_model.pth"),
            "--output_dir", str(tflite_dir),
            "--representative_images", image_dir
        ],
        required_files=[str(checkpoints_dir / "best_model.pth")],
        output_files=[
            str(tflite_dir / "model_float32.tflite"),
            str(tflite_dir / "model_float16.tflite"),
            str(tflite_dir / "model_int8.tflite")
        ]
    ))
    
    return pipeline


def create_quick_pipeline(image_dir: str, base_output_dir: str = "./quick_output", interactive: bool = True) -> TrainingPipeline:
    """Create a quick pipeline for testing (no training)."""
    
    output_dir = Path(base_output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    embeddings_dir = output_dir / "embeddings"
    pca_dir = output_dir / "pca_params"
    
    config = {
        'image_dir': image_dir,
        'output_dir': str(output_dir),
        'embeddings_dir': str(embeddings_dir),
        'pca_dir': str(pca_dir)
    }
    
    pipeline = TrainingPipeline(config, interactive)
    
    # Quick Step 1: Extract embeddings with base DINOv2
    pipeline.add_step(PipelineStep(
        name="Extract Base Embeddings",
        description="Extract DINOv2 embeddings (no training required)",
        command=[
            "uv", "run", "extract-embeddings",
            "--image_dir", image_dir,
            "--output_dir", str(embeddings_dir),
            "--max_images", "100"
        ],
        required_files=[image_dir],
        output_files=[str(embeddings_dir / "embeddings.npy")]
    ))
    
    # Quick Step 2: Apply PCA
    pipeline.add_step(PipelineStep(
        name="Apply PCA",
        description="Reduce dimensions for mobile deployment",
        command=[
            "uv", "run", "fit-pca",
            "--embeddings_path", str(embeddings_dir / "embeddings.npy"),
            "--save_dir", str(pca_dir),
            "--n_components", "64"
        ],
        required_files=[str(embeddings_dir / "embeddings.npy")],
        output_files=[
            str(pca_dir / "pca_tflite.json"),
            str(pca_dir / "pca_transform.dart")
        ]
    ))
    
    return pipeline


def main():
    """Main pipeline runner."""
    parser = argparse.ArgumentParser(
        description='🚀 DINOv2 Training Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick pipeline (no training)
  uv run pipeline --image_dir ../data --mode quick
  
  # Full pipeline with training
  uv run pipeline --image_dir ../data --mode full
  
  # Custom output directory
  uv run pipeline --image_dir ../data --output_dir ./my_results
        """
    )
    
    parser.add_argument('--image_dir', type=str, required=True,
                       help='Directory containing photos')
    parser.add_argument('--mode', type=str, choices=['quick', 'full'], default='quick',
                       help='Pipeline mode: quick (base model) or full (with training)')
    parser.add_argument('--output_dir', type=str, default=None,
                       help='Output directory for results')
    parser.add_argument('--non-interactive', action='store_true',
                       help='Run pipeline without user confirmation prompts')
    
    args = parser.parse_args()
    
    # Set default output directory based on mode
    if args.output_dir is None:
        args.output_dir = f"./{args.mode}_pipeline_output"
    
    ColorfulLogger.header(f"🎯 Starting {args.mode.upper()} Pipeline")
    ColorfulLogger.info(f"Image Directory: {args.image_dir}")
    ColorfulLogger.info(f"Output Directory: {args.output_dir}")
    ColorfulLogger.info(f"Mode: {args.mode}")
    
    # Verify image directory exists
    if not Path(args.image_dir).exists():
        ColorfulLogger.error(f"Image directory does not exist: {args.image_dir}")
        sys.exit(1)
    
    # Create pipeline
    interactive = not args.non_interactive
    
    if args.mode == 'quick':
        pipeline = create_quick_pipeline(args.image_dir, args.output_dir, interactive)
    else:
        pipeline = create_full_pipeline(args.image_dir, args.output_dir, interactive)
    
    # Run pipeline
    success = pipeline.run()
    
    if success:
        ColorfulLogger.success("🎉 Pipeline completed successfully!")
        ColorfulLogger.info(f"📁 Results saved to: {args.output_dir}")
    else:
        ColorfulLogger.error("💥 Pipeline failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()