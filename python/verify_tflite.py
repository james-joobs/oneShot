#!/usr/bin/env python3
"""
Quickly verify a produced TFLite model loads and produces an embedding.

Usage:
  uv run verify-tflite --model ./tflite_models/dinov2_vits14_embed.tflite
"""
from __future__ import annotations

import argparse
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="path to .tflite model")
    args = parser.parse_args()

    import tensorflow as tf
    interpreter = tf.lite.Interpreter(model_path=args.model)
    interpreter.allocate_tensors()
    in_det = interpreter.get_input_details()[0]
    out_det = interpreter.get_output_details()[0]
    print("Input:", in_det)
    print("Output:", out_det)

    # Create a dummy image based on input shape
    input_shape = in_det['shape']
    print(f"Model expects input shape: {input_shape}")
    
    # Check if input is NCHW or NHWC format
    if len(input_shape) == 4:
        if input_shape[1] == 3:  # NCHW format [batch, channels, height, width]
            channels, h, w = input_shape[1], input_shape[2], input_shape[3]
            x = np.random.rand(1, channels, h, w).astype(np.float32)
            print(f"Generated NCHW input: {x.shape}")
        else:  # NHWC format [batch, height, width, channels]
            h, w, channels = input_shape[1], input_shape[2], input_shape[3]
            x = np.random.rand(1, h, w, channels).astype(np.float32)
            print(f"Generated NHWC input: {x.shape}")
    else:
        # Fallback for other shapes
        x = np.random.rand(*input_shape).astype(np.float32)
        print(f"Generated input with shape: {x.shape}")
    
    # Apply ImageNet normalization (mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    x = (x - 0.5) * 2.0  # Normalize to [-1, 1] range
    interpreter.set_tensor(in_det['index'], x)
    interpreter.invoke()
    y = interpreter.get_tensor(out_det['index'])
    print("Embedding shape:", y.shape)


if __name__ == "__main__":
    main()

