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

    # Create a dummy image (ImageNet normalized) 1x224x224x3
    h, w = (in_det['shape'][1], in_det['shape'][2]) if len(in_det['shape']) == 4 else (224, 224)
    x = np.random.rand(1, h, w, 3).astype(np.float32)
    # If your graph expects ImageNet normalization applied upstream, adapt here.
    interpreter.set_tensor(in_det['index'], x)
    interpreter.invoke()
    y = interpreter.get_tensor(out_det['index'])
    print("Embedding shape:", y.shape)


if __name__ == "__main__":
    main()

