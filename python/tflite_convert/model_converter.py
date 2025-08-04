import tensorflow as tf
import numpy as np
import os
from typing import List, Tuple
from models.mobilenet_similarity import MobileNetSimilarityModel
from preprocessing.image_processor import ImageProcessor
import glob

class TFLiteConverter:
    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.processor = ImageProcessor()
        
    def create_representative_dataset(self, data_folder: str, num_samples: int = 100):
        print("Creating representative dataset for quantization...")
        
        image_paths = glob.glob(os.path.join(data_folder, "*.jpeg"))[:num_samples]
        
        def representative_data_gen():
            for path in image_paths:
                img = self.processor.load_and_preprocess_image(path)
                if img is not None:
                    yield [img.astype(np.float32)]
        
        return representative_data_gen
    
    def convert_to_tflite(self, 
                         saved_model_path: str,
                         output_path: str,
                         data_folder: str,
                         quantization_type: str = "dynamic") -> Tuple[str, dict]:
        
        print(f"Converting model to TFLite with {quantization_type} quantization...")
        
        converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_path)
        
        if quantization_type == "dynamic":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            
        elif quantization_type == "int8":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.representative_dataset = self.create_representative_dataset(data_folder)
            # Use more compatible configuration for int8
            converter.target_spec.supported_ops = [
                tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
                tf.lite.OpsSet.TFLITE_BUILTINS  # Fallback for unsupported ops
            ]
            # Keep input/output as float32 for better compatibility
            # converter.inference_input_type = tf.uint8
            # converter.inference_output_type = tf.uint8
            
        elif quantization_type == "float16":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]
            
        converter.allow_custom_ops = True
        
        try:
            tflite_model = converter.convert()
            
            with open(output_path, 'wb') as f:
                f.write(tflite_model)
            
            model_size_mb = len(tflite_model) / (1024 * 1024)
            
            print(f"Model converted successfully!")
            print(f"Output: {output_path}")
            print(f"Size: {model_size_mb:.2f} MB")
            
            stats = {
                "quantization_type": quantization_type,
                "model_size_bytes": len(tflite_model),
                "model_size_mb": model_size_mb,
                "output_path": output_path
            }
            
            return output_path, stats
            
        except Exception as e:
            print(f"Conversion failed: {e}")
            return None, {"error": str(e)}
    
    def verify_tflite_model(self, tflite_path: str, test_image_path: str) -> dict:
        print(f"Verifying TFLite model: {tflite_path}")
        
        try:
            # Try with different interpreter configurations for compatibility
            interpreter = None
            for use_xnnpack in [True, False]:
                try:
                    if use_xnnpack:
                        interpreter = tf.lite.Interpreter(model_path=tflite_path)
                    else:
                        interpreter = tf.lite.Interpreter(
                            model_path=tflite_path,
                            experimental_delegates=[]
                        )
                    interpreter.allocate_tensors()
                    break
                except Exception as e:
                    if not use_xnnpack:  # If CPU-only also fails, give up
                        raise e
                    continue
            
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()
            
            print(f"Input shape: {input_details[0]['shape']}")
            print(f"Output shape: {output_details[0]['shape']}")
            
            test_img = self.processor.load_and_preprocess_image(test_image_path)
            if test_img is None:
                return {"error": "Could not load test image"}
            
            input_data = test_img.astype(input_details[0]['dtype'])
            
            interpreter.set_tensor(input_details[0]['index'], input_data)
            interpreter.invoke()
            
            output_data = interpreter.get_tensor(output_details[0]['index'])
            
            embedding_norm = np.linalg.norm(output_data[0])
            
            verification_stats = {
                "input_shape": input_details[0]['shape'].tolist(),
                "output_shape": output_details[0]['shape'].tolist(),
                "input_dtype": str(input_details[0]['dtype']),
                "output_dtype": str(output_details[0]['dtype']),
                "embedding_norm": float(embedding_norm),
                "model_working": True
            }
            
            print(f"Model verification successful!")
            print(f"Embedding norm: {embedding_norm:.3f}")
            
            return verification_stats
            
        except Exception as e:
            print(f"Verification failed: {e}")
            return {"error": str(e), "model_working": False}
    
    def benchmark_model(self, tflite_path: str, test_images: List[str], num_runs: int = 10) -> dict:
        print(f"Benchmarking TFLite model...")
        
        # Try different interpreter configurations for compatibility
        interpreter = None
        for use_xnnpack in [True, False]:
            try:
                if use_xnnpack:
                    interpreter = tf.lite.Interpreter(model_path=tflite_path)
                    print("  Trying with XNNPACK delegate...")
                else:
                    # Disable XNNPACK delegate for problematic models (like int8)
                    interpreter = tf.lite.Interpreter(
                        model_path=tflite_path,
                        experimental_delegates=[]
                    )
                    print("  Trying without XNNPACK delegate...")
                
                interpreter.allocate_tensors()
                print("  ✅ Interpreter initialized successfully")
                break
                
            except Exception as e:
                print(f"  ❌ Failed with {'XNNPACK' if use_xnnpack else 'CPU-only'}: {e}")
                interpreter = None
                continue
        
        if interpreter is None:
            return {"error": "Failed to initialize interpreter with any configuration"}
        
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        times = []
        
        for i, image_path in enumerate(test_images[:num_runs]):
            test_img = self.processor.load_and_preprocess_image(image_path)
            if test_img is None:
                continue
                
            input_data = test_img.astype(input_details[0]['dtype'])
            
            import time
            start_time = time.time()
            
            interpreter.set_tensor(input_details[0]['index'], input_data)
            interpreter.invoke()
            
            end_time = time.time()
            times.append((end_time - start_time) * 1000)
        
        if times:
            avg_time = np.mean(times)
            min_time = np.min(times)
            max_time = np.max(times)
            
            benchmark_stats = {
                "average_inference_time_ms": float(avg_time),
                "min_inference_time_ms": float(min_time),
                "max_inference_time_ms": float(max_time),
                "num_runs": len(times),
                "all_times_ms": times
            }
            
            print(f"Benchmark completed:")
            print(f"  Average inference time: {avg_time:.1f} ms")
            print(f"  Min: {min_time:.1f} ms, Max: {max_time:.1f} ms")
            
            return benchmark_stats
        else:
            return {"error": "No valid test images for benchmarking"}
    
    def convert_and_evaluate(self, data_folder: str, output_folder: str = "tflite_models"):
        os.makedirs(output_folder, exist_ok=True)
        
        print("Step 1: Creating and saving Keras model...")
        model = MobileNetSimilarityModel()
        saved_model_path = os.path.join(output_folder, "similarity_model")
        model.save_for_tflite(saved_model_path)
        
        quantization_types = ["dynamic", "float16", "int8"]
        results = {}
        
        test_images = glob.glob(os.path.join(data_folder, "*.jpeg"))[:10]
        
        for quant_type in quantization_types:
            print(f"\nStep 2: Converting to TFLite ({quant_type})...")
            
            output_path = os.path.join(output_folder, f"similarity_model_{quant_type}.tflite")
            
            tflite_path, conversion_stats = self.convert_to_tflite(
                saved_model_path, output_path, data_folder, quant_type
            )
            
            if tflite_path:
                print(f"\nStep 3: Verifying {quant_type} model...")
                verification_stats = self.verify_tflite_model(tflite_path, test_images[0])
                
                print(f"\nStep 4: Benchmarking {quant_type} model...")
                benchmark_stats = self.benchmark_model(tflite_path, test_images)
                
                results[quant_type] = {
                    "conversion": conversion_stats,
                    "verification": verification_stats,
                    "benchmark": benchmark_stats
                }
            else:
                results[quant_type] = {"error": conversion_stats.get("error", "Unknown error")}
        
        return results