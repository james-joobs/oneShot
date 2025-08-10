oneShot Python(uv 프로젝트)
================================

이 폴더는 DINOv2(ViT-S/14)를 TFLite로 내보내고 로컬에서 검증하는 uv 기반 Python 프로젝트(pyproject.toml)입니다.

사전 준비물
-----------
- Python 3.10+
- uv 설치: https://docs.astral.sh/uv/

환경 설정(의존성 설치)
----------------------
- 기본 설치:
```
cd python
uv sync
```

- onnxsim 포함 설치(권장): CMake 정책/버전 이슈를 피하기 위해 extra와 CMAKE_ARGS를 함께 사용합니다.
```
cd python
CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" \
  uv sync --extra onnxsim
```
설명
- `--extra onnxsim`: onnx 단순화를 위한 onnxsim, cmake(<3.30) 등을 함께 설치합니다.
- `CMAKE_ARGS=…`: 일부 환경에서 onnx 하위모듈이 요구하는 CMake 정책 최소버전을 명시해 빌드 경고/오류를 방지합니다.

DINOv2 → TFLite 내보내기
------------------------
가장 간단한 내보내기(224 입력 해상도, float32 + dynamic-range TFLite 생성):
```
uv run dinov2-export --img-size 224
```

동일 동작을 스크립트 파일로 실행하고 싶다면:
```
uv run python dinov2_export.py --img-size 224
```

Flutter 에셋으로 자동 복사하려면:
```
uv run dinov2-export --img-size 224 --copy-to-assets
```

산출물(기본 경로)
-----------------
- `tflite_models/dinov2_vits14_embed.tflite`        : float32(정밀도 우선)
- `tflite_models/dinov2_vits14_embed_dynamic.tflite`: dynamic-range 양자화(용량/속도 우선)

TFLite 로컬 검증
----------------
생성한 모델이 정상 로드/실행되는지 빠르게 확인합니다.
```
uv run verify-tflite --model tflite_models/dinov2_vits14_embed.tflite
```

또는 빌드 산출물 경로를 직접 지정할 수도 있습니다.
```
uv run python verify_tflite.py \
  --model build_dinov2/saved_model/dinov2_vits14_simpl_float16.tflite
```

자주 쓰는 명령 모음
-------------------
```
# 1) onnxsim 포함 설치(정책 버전 설정 포함)
CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" uv sync --extra onnxsim

# 2) DINOv2 내보내기(입력 224)
uv run dinov2-export --img-size 224
#   (동등) uv run python dinov2_export.py --img-size 224

# 3) 생성된 TFLite 검증(기본 산출물 사용)
uv run verify-tflite --model tflite_models/dinov2_vits14_embed.tflite
#   (또는) uv run python verify_tflite.py --model build_dinov2/saved_model/dinov2_vits14_simpl_float16.tflite
```

Flutter 연동 가이드
-------------------
1) 내보낸 `.tflite`를 `assets/models/`에 배치합니다(`--copy-to-assets` 사용 시 자동 복사).
2) Flutter 측 전처리는 ImageNet 정규화(mean/std)를 사용하고, 입력은 NHWC 4D 텐서로 제공합니다.
3) Android 종속성(Transformer/Select TF Ops) 추가 권장:
   - `android/app/build.gradle.kts` 예시:
     ```
     dependencies {
         implementation("org.tensorflow:tensorflow-lite:2.16.1")
         implementation("org.tensorflow:tensorflow-lite-select-tf-ops:2.16.1")
     }
     ```
4) ProGuard 규칙은 저장소에 포함되어 있으며, TF/Flutter 관련 클래스를 보존합니다.

트러블슈팅
---------
- CMake 정책/버전 오류
  - `CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" uv sync --extra onnxsim` 형태로 설치하세요.
  - 본 프로젝트는 `onnxsim` extra 사용 시 `cmake<3.30`을 자동으로 설치하지만, 일부 환경에서는 정책 지정이 추가로 도움됩니다.
- onnxsim 미사용 시
  - 내보내기는 가능하나, ONNX 단순화가 제한되어 변환 성능/호환성이 떨어질 수 있습니다(대신 shape inference로 보완).
- TensorFlow/Keras 호환성
  - 변환 단계에서 `TF_USE_LEGACY_KERAS=1` 등을 통해 레거시 Keras 경로를 사용합니다(스크립트에 내장).
- 실행 성능
  - DINOv2는 경량 모델 대비 무겁습니다. 실제 성능은 ARM64 실기기에서 확인하세요.

---
