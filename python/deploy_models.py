#!/usr/bin/env python3
"""
🚀 Flutter Model Deployment Script

Helps select and deploy TFLite models to Flutter app assets.
Provides interactive model selection with size and performance info.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

def get_available_models() -> Dict[str, Dict]:
    """Find all available TFLite models in the project."""
    models = {}
    
    # Check python/mobile_models (newly trained models)
    mobile_models_dir = Path("mobile_models")
    if mobile_models_dir.exists():
        for model_file in mobile_models_dir.glob("*.tflite"):
            size_mb = model_file.stat().st_size / (1024 * 1024)
            models[f"new_{model_file.stem}"] = {
                "name": f"New {model_file.stem.replace('model_', '').title()} Model",
                "path": str(model_file),
                "size_mb": size_mb,
                "type": "newly_trained",
                "description": f"Recently trained model with {model_file.stem.split('_')[-1]} precision"
            }
    
    # Check python/tflite_models (legacy models)  
    tflite_models_dir = Path("tflite_models")
    if tflite_models_dir.exists():
        for model_file in tflite_models_dir.glob("*.tflite"):
            size_mb = model_file.stat().st_size / (1024 * 1024)
            models[f"legacy_{model_file.stem}"] = {
                "name": f"Legacy {model_file.stem.replace('_', ' ').title()}",
                "path": str(model_file),
                "size_mb": size_mb,
                "type": "legacy",
                "description": f"Pre-trained model: {model_file.stem}"
            }
    
    # Check existing assets (currently deployed)
    assets_dir = Path("../assets/models")
    if assets_dir.exists():
        for model_file in assets_dir.glob("*.tflite"):
            size_mb = model_file.stat().st_size / (1024 * 1024)
            models[f"current_{model_file.stem}"] = {
                "name": f"Current {model_file.stem.replace('_', ' ').title()}",
                "path": str(model_file),
                "size_mb": size_mb,
                "type": "current",
                "description": f"Currently deployed: {model_file.stem}"
            }
    
    return models

def display_models(models: Dict[str, Dict]):
    """Display available models in a formatted table."""
    print("\n" + "="*80)
    print("📱 AVAILABLE TFLITE MODELS FOR FLUTTER DEPLOYMENT")
    print("="*80)
    
    if not models:
        print("❌ No TFLite models found!")
        print("💡 Run 'uv run export-tflite' to generate models first.")
        return
    
    # Group by type
    types = {"newly_trained": [], "legacy": [], "current": []}
    for key, model in models.items():
        types[model["type"]].append((key, model))
    
    for type_name, model_list in types.items():
        if not model_list:
            continue
            
        type_display = {
            "newly_trained": "🆕 NEWLY TRAINED MODELS",
            "legacy": "🏛️  LEGACY MODELS", 
            "current": "✅ CURRENTLY DEPLOYED"
        }
        
        print(f"\n{type_display[type_name]}")
        print("-" * 50)
        
        for i, (key, model) in enumerate(model_list, 1):
            print(f"{i:2d}. {model['name']:<30} ({model['size_mb']:.1f} MB)")
            print(f"    📄 {model['description']}")
            print(f"    📁 {model['path']}")
            print()

def select_model(models: Dict[str, Dict]) -> Optional[str]:
    """Interactive model selection."""
    model_keys = list(models.keys())
    
    while True:
        try:
            print("🤔 Select a model to deploy:")
            print("0. Cancel deployment")
            
            for i, key in enumerate(model_keys, 1):
                model = models[key]
                print(f"{i:2d}. {model['name']} ({model['size_mb']:.1f} MB)")
            
            choice = input(f"\nEnter your choice (0-{len(model_keys)}): ").strip()
            
            if choice == "0":
                print("❌ Deployment cancelled.")
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(model_keys):
                selected_key = model_keys[choice_num - 1]
                selected_model = models[selected_key]
                
                print(f"\n✅ Selected: {selected_model['name']}")
                print(f"📁 Path: {selected_model['path']}")
                print(f"💾 Size: {selected_model['size_mb']:.1f} MB")
                
                confirm = input(f"\n🚀 Deploy this model to Flutter app? (y/n): ").lower().strip()
                if confirm in ['y', 'yes']:
                    return selected_key
                else:
                    continue
            else:
                print("❌ Invalid choice. Please try again.")
                
        except ValueError:
            print("❌ Please enter a valid number.")
        except KeyboardInterrupt:
            print("\n❌ Deployment cancelled.")
            return None

def deploy_model(model_key: str, models: Dict[str, Dict]) -> bool:
    """Deploy selected model to Flutter assets."""
    model = models[model_key]
    source_path = Path(model["path"])
    
    # Target directory in Flutter app
    target_dir = Path("../assets/models")
    target_dir.mkdir(exist_ok=True, parents=True)
    
    # Generate target filename
    model_name = source_path.stem
    if model_name.startswith("model_"):
        # Use descriptive name for new models
        precision = model_name.split("_")[-1]
        target_name = f"dinov2_trained_{precision}.tflite"
    else:
        target_name = source_path.name
    
    target_path = target_dir / target_name
    
    try:
        # Copy model file
        print(f"📋 Copying model...")
        print(f"   From: {source_path}")
        print(f"   To:   {target_path}")
        
        shutil.copy2(source_path, target_path)
        
        # Copy metadata if available
        metadata_source = source_path.parent / "export_metadata.json"
        if metadata_source.exists():
            metadata_target = target_dir / f"{target_name}.metadata.json"
            shutil.copy2(metadata_source, metadata_target)
            print(f"📊 Copied metadata: {metadata_target}")
        
        # Update deployment info
        deployment_info = {
            "deployed_at": datetime.now().isoformat(),
            "source_model": model,
            "target_file": str(target_path),
            "deployment_script": "deploy_models.py"
        }
        
        with open(target_dir / "deployment_info.json", 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"✅ Successfully deployed model!")
        print(f"📱 Flutter app will now use: {target_name}")
        print(f"💡 Update TFLiteService._modelPath to: 'assets/models/{target_name}'")
        
        return True
        
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False

def update_flutter_service(target_name: str):
    """Suggest Flutter service update."""
    print(f"\n🔧 TO COMPLETE DEPLOYMENT:")
    print(f"1. Update lib/services/tflite_service.dart:")
    print(f"   Change: static const String _modelPath = 'assets/models/{target_name}';")
    print(f"2. Run: flutter clean && flutter pub get")
    print(f"3. Rebuild the app: flutter build apk")

def main():
    """Main deployment script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🚀 Flutter Model Deployment Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive selection
  python deploy_models.py
  
  # Auto-deploy latest float32 model
  python deploy_models.py --auto new_float32
  
  # List available models only
  python deploy_models.py --list
        """
    )
    
    parser.add_argument('--auto', type=str, metavar='MODEL_TYPE',
                       help='Auto-deploy specific model (e.g., new_float32, legacy_dynamic)')
    parser.add_argument('--list', action='store_true',
                       help='List available models and exit')
    
    args = parser.parse_args()
    
    print("🚀 Flutter Model Deployment Tool")
    
    # Check if we're in the python directory
    if not Path("training").exists():
        print("❌ Please run this script from the python/ directory")
        sys.exit(1)
    
    # Find available models
    models = get_available_models()
    
    # Display models
    display_models(models)
    
    if not models:
        sys.exit(1)
    
    if args.list:
        print("✅ Model list displayed above.")
        return
    
    # Select model
    if args.auto:
        # Auto-deploy specific model
        matching_models = [k for k in models.keys() if args.auto.lower() in k.lower()]
        if not matching_models:
            print(f"❌ No model found matching '{args.auto}'")
            print("💡 Available models:", list(models.keys()))
            sys.exit(1)
        
        selected_key = matching_models[0]  # Take first match
        print(f"\n🤖 Auto-deploying: {models[selected_key]['name']}")
    else:
        # Interactive selection
        try:
            selected_key = select_model(models)
            if not selected_key:
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Interactive mode not available. Use --auto or --list flags.")
            sys.exit(1)
    
    # Deploy model
    if deploy_model(selected_key, models):
        target_name = Path(models[selected_key]["path"]).stem
        if target_name.startswith("model_"):
            precision = target_name.split("_")[-1]
            target_name = f"dinov2_trained_{precision}.tflite"
        else:
            target_name = Path(models[selected_key]["path"]).name
        
        update_flutter_service(target_name)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()