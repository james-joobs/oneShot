oneShot Python (uv project)
================================

This folder contains a uv-managed Python project (pyproject.toml) to export DINOv2 (ViT-S/14) to TFLite and verify the result locally.

Prerequisites
-------------
- Python 3.10+
- uv (https://docs.astral.sh/uv/) installed

Setup
-----
```
cd python
uv sync
```

Export DINOv2 → TFLite
----------------------
```
# Default: ViT-S/14 DINOv2
uv run dinov2-export

# Copy produced models directly into Flutter assets
uv run dinov2-export --copy-to-assets
```

Outputs:
- tflite_models/dinov2_vits14_embed.tflite (float32)
- tflite_models/dinov2_vits14_embed_dynamic.tflite (dynamic-range)

Verify TFLite locally
---------------------
```
uv run verify-tflite --model tflite_models/dinov2_vits14_embed.tflite
```

Integrating with Flutter
------------------------
1) Put the desired `.tflite` under `assets/models/` (use `--copy-to-assets` or copy manually).
2) Update Flutter TFLite service to ImageNet normalization (mean/std) and correct model path.
3) Add Android dependencies for transformer ops (Select TF Ops):
   - In `android/app/build.gradle.kts`:
     ```
     dependencies {
         implementation("org.tensorflow:tensorflow-lite:2.16.1")
         implementation("org.tensorflow:tensorflow-lite-select-tf-ops:2.16.1")
     }
     ```
4) Keep ProGuard rules (already present) to preserve TF/Flutter classes.

Notes
-----
- DINOv2 is heavier than MobileNetV3. Test on ARM64 physical devices for realistic performance.
- If you prefer pure TFLite ops without Select TF Ops, expect reduced graph fidelity or additional post-processing.

