#!/usr/bin/env python3

import os
import json
from tflite_convert.model_converter import TFLiteConverter

def main():
    data_folder = "../data"
    output_folder = "tflite_models"
    
    print("=== TensorFlow Lite Model Conversion Pipeline ===")
    print(f"Data folder: {data_folder}")
    print(f"Output folder: {output_folder}")
    
    converter = TFLiteConverter()
    
    results = converter.convert_and_evaluate(data_folder, output_folder)
    
    print("\n" + "="*60)
    print("CONVERSION RESULTS SUMMARY")
    print("="*60)
    
    for quant_type, result in results.items():
        print(f"\n{quant_type.upper()} Quantization:")
        
        if "error" in result:
            print(f"  ❌ Failed: {result['error']}")
            continue
            
        conv_stats = result.get("conversion", {})
        verify_stats = result.get("verification", {})
        bench_stats = result.get("benchmark", {})
        
        print(f"  ✅ Conversion: {conv_stats.get('model_size_mb', 0):.2f} MB")
        
        if verify_stats.get("model_working", False):
            print(f"  ✅ Verification: Working (norm: {verify_stats.get('embedding_norm', 0):.3f})")
        else:
            print(f"  ❌ Verification: Failed")
            
        if "average_inference_time_ms" in bench_stats:
            avg_time = bench_stats["average_inference_time_ms"]
            print(f"  ⚡ Performance: {avg_time:.1f} ms average")
        else:
            print(f"  ❌ Benchmark: Failed")
    
    results_file = os.path.join(output_folder, "conversion_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    print("\nRecommendation for mobile deployment:")
    
    if "dynamic" in results and results["dynamic"].get("conversion", {}).get("model_size_mb", 0) < 50:
        print("  ✅ Use DYNAMIC quantization for best accuracy/size balance")
    elif "float16" in results and results["float16"].get("conversion", {}).get("model_size_mb", 0) < 30:
        print("  ✅ Use FLOAT16 quantization for smaller size with good accuracy")
    elif "int8" in results and results["int8"].get("conversion", {}).get("model_size_mb", 0) < 20:
        print("  ✅ Use INT8 quantization for maximum compression")
    else:
        print("  ⚠️  Model size may be too large for mobile deployment")
    
    print("="*60)

if __name__ == "__main__":
    main()