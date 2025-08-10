#!/usr/bin/env python3
"""
Test script to verify all dependencies are correctly installed.
"""

import sys
import importlib
from typing import List, Tuple

def test_imports() -> List[Tuple[str, bool, str]]:
    """Test importing all required packages."""
    
    packages = [
        # Core ML frameworks
        ("torch", "PyTorch"),
        ("torchvision", "PyTorch Vision"),
        ("tensorflow", "TensorFlow"),
        ("transformers", "HuggingFace Transformers"),
        
        # Model libraries
        ("timm", "PyTorch Image Models"),
        
        # ONNX tools
        ("onnx", "ONNX"),
        ("onnxruntime", "ONNX Runtime"),
        
        # Image processing
        ("PIL", "Pillow"),
        ("cv2", "OpenCV"),
        
        # Data processing
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("sklearn", "Scikit-learn"),
        
        # Visualization
        ("matplotlib", "Matplotlib"),
        
        # Utilities
        ("tqdm", "tqdm"),
        
        # Photo metadata
        ("exifread", "ExifRead"),
        ("geopy", "GeoPy"),
        
        # Face recognition
        ("face_recognition", "Face Recognition"),
    ]
    
    results = []
    
    for module_name, description in packages:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, '__version__', 'unknown')
            results.append((description, True, version))
        except ImportError as e:
            results.append((description, False, str(e)))
    
    return results


def test_training_modules():
    """Test that our training modules can be imported."""
    
    modules = [
        "training.auto_labeler",
        "training.dinov2_finetune", 
        "training.pca_whitening",
        "training.tflite_export",
        "training.face_aware_scoring",
        "training.reranking_module",
        "training.final_selection",
    ]
    
    results = []
    
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            results.append((module_name, True, "OK"))
        except ImportError as e:
            results.append((module_name, False, str(e)))
    
    return results


def main():
    """Run all tests and print results."""
    
    print("🔍 Testing package imports...")
    print("=" * 60)
    
    import_results = test_imports()
    
    success_count = 0
    for desc, success, info in import_results:
        status = "✅" if success else "❌"
        version_info = f" (v{info})" if success else f" - {info}"
        print(f"{status} {desc:<25}{version_info}")
        if success:
            success_count += 1
    
    print(f"\n📊 Package imports: {success_count}/{len(import_results)} successful")
    
    print("\n🔍 Testing training modules...")
    print("=" * 60)
    
    module_results = test_training_modules()
    
    module_success = 0
    for module, success, info in module_results:
        status = "✅" if success else "❌"
        error_info = f" - {info}" if not success else ""
        print(f"{status} {module:<30}{error_info}")
        if success:
            module_success += 1
    
    print(f"\n📊 Training modules: {module_success}/{len(module_results)} successful")
    
    # Overall result
    total_tests = len(import_results) + len(module_results)
    total_success = success_count + module_success
    
    print(f"\n🎯 Overall: {total_success}/{total_tests} tests passed")
    
    if total_success == total_tests:
        print("🎉 All tests passed! Installation is complete.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())