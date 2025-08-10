# oneShot: Flutter 기반 온디바이스 여행 사진 큐레이션 앱

여행 사진 중복을 자동으로 묶고(클러스터링), 각 그룹에서 가장 좋은 사진을 추천하는 온디바이스 AI 앱입니다. 본 저장소는 Flutter 앱을 리포지터리 루트에서 직접 빌드/실행할 수 있도록 구성되어 있습니다.

## 최근 작업 요약 (Android 중심)

- 실서비스 파이프라인 전환: 모의 임베딩 → 실제 TFLite 추론으로 전환
  - `lib/engine/tflite_embedding_runner.dart` 추가 (실제 TFLite 임베딩 러너)
  - `lib/providers/photo_processing_provider.dart`에서 `TFLiteService` + `TFLiteEmbeddingRunner` 사용
- 중복 그룹핑 및 랭킹 엔진 통합 유지
  - 그룹핑: `lib/engine/grouping.dart` (배경/얼굴 시그니처 융합 점수)
  - 랭킹: `lib/engine/ranking.dart` + `lib/engine/quality_metrics.dart`
- Android 빌드 체인 정비
  - 디버그/릴리스 APK 모두 빌드 완료
  - 릴리스 축소(난독화/리소스 축소) 재활성화 및 안전 규칙 추가
    - ProGuard: `android/app/proguard-rules.pro` (TFLite/Flutter/Play Core 보존 규칙)
    - Gradle: `android/app/build.gradle.kts` 릴리스 빌드에 축소 설정 적용

빌드 결과
- 디버그 APK: `build/app/outputs/flutter-apk/app-debug.apk`
- 릴리스 APK(축소 ON): `build/app/outputs/flutter-apk/app-release.apk`

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
- 앱에 번들된 예제 이미지: `data/` (pubspec 등록)
- TFLite 모델: `assets/models/similarity_model_dynamic.tflite`

## 동작 흐름

1) `HomeScreen`에서 “사진 분석 시작” 클릭 → `PhotoProcessingProvider.processGalleryPhotos()` 호출
2) `AssetPhotoService`가 `data/` 폴더의 이미지를 `AssetManifest.json` 또는 폴백 목록으로 로드
3) `DuplicateGrouper`가 `TFLiteEmbeddingRunner` 임베딩 + `FaceEngineMock` 시그니처로 유사도 융합 점수 계산 후 클러스터링
4) `Ranker`가 각 클러스터에서 품질 지표(샤프니스/노출 등)로 대표 사진 선정
5) 결과는 탭 UI에 반영
   - Home: 처리 통계/진행률/요약
   - Clusters: 중복 그룹 뷰
   - Recommended: 추천 그리드 및 상세 보기

## Android 빌드/실행

의존성 설치
```bash
flutter pub get
```

디버그 빌드
```bash
flutter build apk --debug
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

릴리스 빌드(축소 활성화)
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

## 주의/팁

- 데이터 폴더는 앱에 번들됩니다. 실제 배포 시 용량 절감을 위해 `data/`를 비우거나 샘플 최소화 권장
- 실제 기기 성능 최적화를 위해 NNAPI/GPU Delegate 적용 가능 (`tflite_flutter` 옵션 조정)
- 패키지명/아이콘/스플래시는 `android/app/src/main` 및 `pubspec.yaml`에서 브랜드에 맞게 조정하세요

## 추가 자료

- Flutter/Dart 린트: `analysis_options.yaml`
- 환경 셋업: `FLUTTER_SETUP.md`, `SETUP.md`, `setup_flutter.sh`

## 향후 개선 아이디어

- NNAPI/GPU Delegate 자동 선택 및 성능 벤치마크
- 리얼 얼굴 품질/눈뜨기 검출 모델 연동(현재는 프록시/상수)
- 기기 갤러리 접근(`photo_manager`) 기반 실사진 처리 모드 추가(현재는 번들 에셋)
- APK 사이즈 최적화(리소스/폰트/모델 분리 및 압축)
