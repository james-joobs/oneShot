#!/usr/bin/env python3
"""
Export DINOv2 (ViT-S/14) from timm to ONNX, convert to TensorFlow SavedModel via onnx2tf,
and finally produce a TFLite model suitable for Flutter integration.

Requires packages declared in python/pyproject.toml. Use uv to install:

  cd python
  uv sync
  uv run dinov2-export --help

Outputs:
  - ./tflite_models/dinov2_vits14_embed.tflite (float32, high accuracy)
  - ./tflite_models/dinov2_vits14_embed_dynamic.tflite (dynamic range quantized)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
import timm


def build_model(model_name: str = "vit_small_patch14_dinov2", img_size: int | None = 224) -> torch.nn.Module:
    # Use timm to get DINOv2 small with embedding output
    # num_classes=0 => headless; forward returns embedding
    # If img_size is provided, override to avoid size assertions (DINOv2 defaults to 518)
    create_kwargs = dict(pretrained=True, num_classes=0)
    if img_size is not None:
        create_kwargs["img_size"] = img_size
    model = timm.create_model(model_name, **create_kwargs)
    model.eval()
    return model


@torch.no_grad()
def export_onnx(model: torch.nn.Module, onnx_path: Path, input_size=(1, 3, 224, 224), opset: int = 17) -> None:
    dummy = torch.randn(*input_size)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy,
        onnx_path.as_posix(),
        input_names=["input"],
        output_names=["embedding"],
        opset_version=opset,
        dynamic_axes=None,  # fixed batch=1 for mobile simplicity
    )
    print(f"[ONNX] exported: {onnx_path}")


def simplify_onnx(onnx_in: Path, onnx_out: Path) -> None:
    try:
        import onnx
        try:
            # Try full graph simplification first
            from onnxsim import simplify
            model = onnx.load(onnx_in.as_posix())
            model_simplified, check = simplify(model)
            if check:
                onnx.save(model_simplified, onnx_out.as_posix())
                print(f"[ONNX] simplified: {onnx_out}")
                return
            else:
                print("[ONNX] onnxsim check failed; falling back to shape inference")
        except Exception as e:
            print(f"[ONNX] onnxsim unavailable; using shape inference only ({e}).")

        # Fallback: run ONNX shape inference to concretize dims
        model = onnx.load(onnx_in.as_posix())
        inferred = onnx.shape_inference.infer_shapes(model)
        onnx.save(inferred, onnx_out.as_posix())
        print(f"[ONNX] shape-inferred: {onnx_out}")
    except Exception as e:
        print(f"[ONNX] simplification failed; copying original ({e}).")
        shutil.copy2(onnx_in, onnx_out)


def onnx_to_saved_model(onnx_path: Path, saved_model_dir: Path) -> None:
    # Use onnx2tf CLI to convert to SavedModel
    saved_model_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "onnx2tf",
        "-i",
        onnx_path.as_posix(),
        "-o",
        saved_model_dir.as_posix(),
        "-b", "1",
    ]
    print(f"[onnx2tf] converting to SavedModel: {' '.join(cmd)}")
    env = os.environ.copy()
    # Force legacy tf-keras to avoid Keras 3 symbolic tensor restrictions
    env.setdefault("TF_USE_LEGACY_KERAS", "1")
    env.setdefault("KERAS_BACKEND", "tensorflow")
    subprocess.run(cmd, check=True, env=env)
    print(f"[TF] SavedModel or TFLite outputs at: {saved_model_dir}")


def copy_generated_tflites(saved_model_dir: Path, tflite_f32: Path, tflite_dyn: Path) -> bool:
    """Copy TFLite files produced by onnx2tf into our output locations.

    Returns True if at least one file was copied, False otherwise.
    """
    produced = list(saved_model_dir.glob("*.tflite"))
    if not produced:
        return False
    # Prefer explicit float32/float16 filenames when present
    f32_src = None
    f16_src = None
    for p in produced:
        name = p.name.lower()
        if "float32" in name and f32_src is None:
            f32_src = p
        if "float16" in name and f16_src is None:
            f16_src = p
    # Fallbacks if names are generic
    if f32_src is None:
        for p in produced:
            if "float16" not in p.name.lower():
                f32_src = p
                break
    if f16_src is None:
        for p in produced:
            if "float16" in p.name.lower():
                f16_src = p
                break

    copied_any = False
    if f32_src is not None:
        tflite_f32.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f32_src, tflite_f32)
        print(f"[TFLite] copied float32: {f32_src.name} -> {tflite_f32}")
        copied_any = True
    if f16_src is not None:
        tflite_dyn.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f16_src, tflite_dyn)
        print(f"[TFLite] copied float16 (as 'dynamic'): {f16_src.name} -> {tflite_dyn}")
        copied_any = True
    return copied_any


def saved_model_to_tflite(saved_model_dir: Path, tflite_path: Path, dynamic_quant: bool = False) -> None:
    import tensorflow as tf

    converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir.as_posix())
    # Transformers often require SELECT_TF_OPS
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    if dynamic_quant:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]

    tflite_model = converter.convert()
    tflite_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tflite_path, "wb") as f:
        f.write(tflite_model)
    print(f"[TFLite] written: {tflite_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DINOv2 (ViT-S/14) to TFLite for Flutter")
    parser.add_argument("--model", default="vit_small_patch14_dinov2", help="timm model name")
    parser.add_argument("--img-size", type=int, default=224, help="model input resolution (e.g. 224 or 518)")
    parser.add_argument("--workdir", default="build_dinov2", help="working directory for intermediate files")
    parser.add_argument("--outdir", default="tflite_models", help="output directory for tflite models")
    parser.add_argument("--copy-to-assets", action="store_true", help="also copy .tflite to Flutter assets/models")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    work = (root / args.workdir)
    outdir = (root / args.outdir)
    onnx_raw = work / "dinov2_vits14.onnx"
    onnx_simpl = work / "dinov2_vits14_simpl.onnx"
    saved_model_dir = work / "saved_model"
    tflite_f32 = outdir / "dinov2_vits14_embed.tflite"
    tflite_dyn = outdir / "dinov2_vits14_embed_dynamic.tflite"

    print("[Build] Loading model…")
    model = build_model(args.model, img_size=args.img_size)

    print("[Build] Export ONNX…")
    # Determine input size from the model when possible; otherwise use --img-size
    c = 3
    h = w = int(args.img_size)
    try:
        pe = getattr(model, "patch_embed", None)
        if pe is not None and hasattr(pe, "img_size"):
            pe_size = pe.img_size
            if isinstance(pe_size, (tuple, list)):
                if len(pe_size) >= 2:
                    h, w = int(pe_size[0]), int(pe_size[1])
                elif len(pe_size) == 1:
                    h = w = int(pe_size[0])
            else:
                h = w = int(pe_size)
    except Exception:
        pass
    export_onnx(model, onnx_raw, input_size=(1, c, h, w))

    print("[Build] Simplify ONNX…")
    simplify_onnx(onnx_raw, onnx_simpl)

    print("[Build] ONNX -> SavedModel…")
    if saved_model_dir.exists():
        shutil.rmtree(saved_model_dir)
    onnx_to_saved_model(onnx_simpl, saved_model_dir)

    # If onnx2tf created a proper SavedModel, convert it via TFLiteConverter.
    # Otherwise, onnx2tf may have already emitted .tflite files; copy them.
    has_saved_model = (saved_model_dir / "saved_model.pb").exists() or (saved_model_dir / "saved_model.pbtxt").exists()
    if has_saved_model:
        print("[Build] SavedModel -> TFLite (float32)…")
        saved_model_to_tflite(saved_model_dir, tflite_f32, dynamic_quant=False)

        print("[Build] SavedModel -> TFLite (dynamic range quant)…")
        saved_model_to_tflite(saved_model_dir, tflite_dyn, dynamic_quant=True)
    else:
        print("[Build] No saved_model.pb found. Using TFLite files emitted by onnx2tf…")
        ok = copy_generated_tflites(saved_model_dir, tflite_f32, tflite_dyn)
        if not ok:
            raise FileNotFoundError(
                f"onnx2tf did not produce SavedModel or TFLite files in {saved_model_dir}"
            )

    if args.copy_to_assets:
        flutter_assets = (root.parent / "assets" / "models")
        flutter_assets.mkdir(parents=True, exist_ok=True)
        for src in (tflite_f32, tflite_dyn):
            dst = flutter_assets / src.name
            shutil.copy2(src, dst)
            print(f"[Copy] {src.name} -> {dst}")

    print("[Done] Export pipeline finished.")


if __name__ == "__main__":
    main()
