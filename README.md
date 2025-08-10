# oneShot: Flutter 기반 온디바이스 여행 사진 큐레이션 앱

여행 사진 중복을 자동으로 묶고(클러스터링), 각 그룹에서 가장 좋은 사진을 추천하는 온디바이스 AI 앱입니다. 본 저장소는 Flutter 앱을 루트에서 바로 빌드/실행할 수 있도록 구성되어 있습니다.

## 현재 상황(2025-08)

- DINOv2 ViT-S/14 임베딩 TFLite 모델 연동 완료
  - 모델: `assets/models/dinov2_vits14_embed.tflite` (동적 버전도 포함)
  - 입력 텐서 4D(NHWC) 처리 및 동적 입력 크기 리사이즈 로직 반영
- 사진 분석 실행 시 발생하던 Conv2D 입력 차원 오류를 해결
  - 오류 메시지 예: `input->dims->size != 4 (1 != 4)` / `Node 0 (CONV_2D) failed to prepare`
  - 원인: 4D 입력이 아닌 1D 텐서로 전달되던 버그
  - 조치: `TFLiteService`에서 실제 4D NHWC 입력 생성 및 출력 Flatten 처리로 수정
- .gitignore 정리
  - 사용자 사진은 `data/**`를 통째로 무시하고, 디렉터리 유지를 위해 `data/.gitkeep`만 추적
  - 모델 바이너리는 기본적으로 `*.tflite` 무시하되, 앱이 사용하는 `assets/models/*.tflite`와
    도구용 `python/tflite_models/*.tflite`는 추적 유지
- 실패 시 모의 엔진으로 폴백
  - 실제 모델 초기화 실패 시 `MockTFLiteService` 기반 임베딩으로 폴백되어 UI 확인 가능

## 앱 아키텍처 개요

```
lib/
├── main.dart                        # 앱 엔트리/탭 네비게이션
├── providers/
│   └── photo_processing_provider.dart  # 상태/진행률/결과 관리
├── engine/
│   ├── embedding_runner.dart          # 임베딩 인터페이스(추상)
│   ├── tflite_embedding_runner.dart   # 실제 TFLite 임베딩 러너
│   ├── grouping.dart                  # 중복 점수 기반 클러스터링
│   ├── face_models.dart               # 간이 얼굴 세트 시그니처
│   ├── ranking.dart                   # 대표 사진 선별 로직
│   ├── quality_metrics.dart           # 샤프니스/노출 등 품질 지표
│   └── weights.dart                   # 가중치/임계값 설정
├── services/
│   ├── tflite_service.dart            # TFLite 인터프리터 로딩/추론
│   └── asset_photo_service.dart       # `data/` 에셋 이미지 로딩
├── models/
│   └── photo_cluster.dart             # 결과/클러스터 모델(Asset 기반)
├── screens/
│   ├── home_screen.dart               # 진행/통계/CTA
│   ├── clusters_screen.dart           # 클러스터 목록
│   └── recommended_screen.dart        # 추천 사진 그리드/상세
└── widgets/
    ├── stats_card.dart                # 통계 카드
    └── cluster_view.dart              # 클러스터 썸네일 리스트
```

에셋/모델
- 번들 예제 이미지: `data/` (대용량 개인 사진은 커밋하지 않음)
- TFLite 임베딩 모델:
  - `assets/models/dinov2_vits14_embed.tflite`
  - `assets/models/dinov2_vits14_embed_dynamic.tflite`
  - 참고용 유사도 모델(실험): `assets/models/similarity_model_dynamic.tflite`

## 동작 흐름

1) `HomeScreen`에서 “사진 분석 시작” 클릭 → `PhotoProcessingProvider.processGalleryPhotos()` 호출
2) `AssetPhotoService`가 `data/` 폴더의 이미지를 `AssetManifest.json` 또는 폴백 목록으로 로드
3) `DuplicateGrouper`가 `TFLiteEmbeddingRunner` 임베딩 + `FaceEngineMock` 시그니처로 유사도 융합 점수 계산 후 클러스터링
4) `Ranker`가 각 클러스터에서 품질 지표(샤프니스/노출 등)로 대표 사진 선정
5) 결과는 탭 UI에 반영
   - Home: 처리 통계/진행률/요약
   - Clusters: 중복 그룹 뷰
   - Recommended: 추천 그리드 및 상세 보기

## 실행 방법(Android 에뮬레이터 기준)

의존성 설치
```bash
flutter pub get
```

앱 실행
```bash
flutter run
```

릴리스 빌드(선택)
```bash
flutter build apk --release
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

ProGuard/축소 설정
- 규칙: `android/app/proguard-rules.pro`
- 주요 보존 대상
  - TFLite: `org.tensorflow.lite.**`, `org.tensorflow.lite.gpu.**`, `com.google.flatbuffers.**`
  - Flutter 임베딩/플러그인/지연 로딩: `io.flutter.**`, `io.flutter.plugins.**`, `io.flutter.embedding.engine.deferredcomponents.**`
  - Play Core (Flutter 지연 컴포넌트 참조): `com.google.android.play.core.**`

## 데이터/모델 관리

- `data/`는 저장소에 유지되지만 사용자 사진은 `.gitignore`로 제외됩니다. 필요 시 여기에 샘플 이미지를 넣으면 앱에서 자동 로드합니다.
- 앱이 사용하는 TFLite 모델은 `assets/models/`에 존재하며, `pubspec.yaml`에 등록되어 빌드에 포함됩니다.
- 파이프라인/실험용 모델은 `python/tflite_models/`에서 관리합니다.

## 문제 해결(트러블슈팅)

- Conv2D 오류: `input->dims->size != 4 (1 != 4)`
  - 조치: `flutter clean` → `flutter pub get` → 앱 삭제 후 `flutter run`
  - 현 버전 코드는 인터프리터의 입력 Shape를 읽고 동적으로 `[1,H,W,3]`로 리사이즈하여 4D 입력을 보장합니다.
- 모델 초기화 실패 시
  - 앱은 자동으로 모의 임베딩 엔진으로 폴백합니다. 실제 모델 성능 확인을 원하면 `assets/models/`에 모델이 존재하는지 확인하세요.
- 성능
  - 일부 기기에서 NNAPI가 더 빠를 수 있음. 현재 인터프리터 생성 시 기본/NNAPI 경로를 순차 시도합니다.

## 추가 자료

- Flutter/Dart 린트: `analysis_options.yaml`
- 환경 셋업: `FLUTTER_SETUP.md`, `SETUP.md`, `setup_flutter.sh`

## 향후 개선 아이디어

- NNAPI/GPU Delegate 자동 선택 및 성능 벤치마크
- 리얼 얼굴 품질/눈뜨기 검출 모델 연동(현재는 프록시/상수)
- 기기 갤러리 접근(`photo_manager`) 기반 실사진 처리 모드 추가(현재는 번들 에셋)
- APK 사이즈 최적화(리소스/폰트/모델 분리 및 압축)
