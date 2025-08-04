# OneShot - AI 기반 여행 사진 큐레이션 앱 실행 가이드

## 📱 프로젝트 소개

OneShot은 Flutter와 TensorFlow Lite를 활용한 온디바이스 AI 사진 큐레이션 앱입니다. 프로젝트 내 `data/` 폴더의 이미지들을 AI가 자동으로 분석하여 중복되거나 유사한 사진을 감지하고, 최적의 사진만을 추천합니다.

**⚠️ 중요**: 이 앱은 **로컬 에셋 이미지**를 사용합니다. 기기의 갤러리가 아닌 프로젝트의 `data/` 폴더에 있는 이미지들을 처리합니다.

### 주요 특징
- 🔒 **완전한 온디바이스 처리**: 인터넷 연결 없이 모든 처리가 기기에서 이루어집니다
- 🚀 **빠른 처리 속도**: MobileNetV3 기반 경량화 모델로 실시간 처리
- 📸 **스마트 클러스터링**: 유사한 사진을 그룹화하여 보여줍니다
- ⭐ **최적 사진 추천**: 각 그룹에서 가장 좋은 사진을 자동 선택
- 💾 **저장 공간 절약**: 중복 사진 제거로 최대 60% 공간 절약

## 🛠️ 기술 스택

- **Frontend**: Flutter 3.x
- **AI Engine**: TensorFlow Lite (MobileNetV3)
- **State Management**: Provider
- **Image Processing**: photo_manager, image
- **UI Components**: Material Design 3

## 📲 설치 및 실행 방법

### 사전 요구사항
- Flutter SDK 3.10.0 이상
- Android Studio 또는 Visual Studio Code
- Android 기기 또는 에뮬레이터 (API 21 이상)
- Android NDK 27.0.12077973

### 1단계: 프로젝트 클론
```bash
git clone <repository-url>
cd oneShot
```

### 2단계: Flutter 환경 설정
```bash
# Flutter 버전 확인
flutter --version

# Flutter Doctor 실행하여 환경 점검
flutter doctor
```

### 3단계: 의존성 설치
```bash
# 패키지 의존성 설치
flutter pub get

# Flutter 프로젝트 정리 (선택사항)
flutter clean
```

### 4단계: Android 설정

#### 4-1. NDK 버전 설정
`android/app/build.gradle.kts` 파일에 다음을 추가:

```kotlin
android {
    ndkVersion = "27.0.12077973"
    // ... 기타 설정
}
```

#### 4-2. 권한 설정 확인
`android/app/src/main/AndroidManifest.xml`에서 다음 권한이 설정되어 있는지 확인:

```xml
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
```

### 5단계: 앱 실행

#### 5-1. 연결된 기기 확인
```bash
flutter devices
```

#### 5-2. 디버그 모드로 실행
```bash
flutter run
```

#### 5-3. 릴리즈 APK 빌드 (배포용)
```bash
flutter build apk --release
```

APK 파일은 `build/app/outputs/flutter-apk/app-release.apk`에 생성됩니다.

## 🎯 사용 방법

### 1단계: 앱 실행
OneShot 앱을 실행합니다.

### 2단계: 이미지 확인
프로젝트의 `data/` 폴더에 이미지 파일들이 있는지 확인합니다. 현재 약 60개의 샘플 이미지가 포함되어 있습니다.

### 3단계: 분석 시작
홈 화면에서 **"사진 분석 시작"** 버튼을 누릅니다.

### 4단계: 결과 확인
- **홈 탭**: 전체 통계 및 분석 결과 요약
- **클러스터 탭**: 유사한 사진들의 그룹 확인
- **추천 탭**: AI가 선택한 최적의 사진들

## 🧪 테스트 방법

### 단위 테스트
```bash
flutter test
```

### 수동 테스트 시나리오
1. **권한 테스트**: 앱 최초 실행 시 갤러리 권한 요청 확인
2. **빈 갤러리 테스트**: 사진이 없는 기기에서 적절한 메시지 표시 확인
3. **대용량 처리 테스트**: 100장 이상의 사진으로 성능 테스트
4. **UI 반응성 테스트**: 처리 중 UI가 멈추지 않는지 확인

## 🐛 문제 해결

### 일반적인 문제들

#### 1. "TFLite 모델을 찾을 수 없음" 오류
- `assets/models/similarity_model_dynamic.tflite` 파일이 있는지 확인
- `pubspec.yaml`의 assets 섹션 확인:
  ```yaml
  flutter:
    assets:
      - assets/models/
  ```

#### 2. 갤러리 권한 오류
- 설정 > 앱 > OneShot > 권한에서 사진 접근 권한 확인
- Android 13 이상: READ_MEDIA_IMAGES 권한 필요

#### 3. 빌드 오류
```bash
flutter clean
flutter pub get
flutter run
```

#### 4. NDK 버전 오류
Android Studio에서:
1. SDK Manager 열기
2. SDK Tools 탭
3. NDK (Side by side) 설치
4. 버전 27.0.12077973 선택

#### 5. Gradle 빌드 오류
```bash
cd android
./gradlew clean
cd ..
flutter run
```

## 📊 성능 지표

- **모델 크기**: 3.6MB
- **추론 속도**: 평균 6.6ms/이미지
- **메모리 사용**: 최대 200MB (100장 처리 시)
- **배터리 소모**: 최소화 (온디바이스 처리)

## 🔍 디버깅 팁

### 1. 자세한 로그 보기
```bash
flutter run --verbose
```

### 2. 특정 기기에서 실행
```bash
flutter run -d <device-id>
```

### 3. 핫 리로드 사용
앱 실행 중 `r` 키를 눌러 핫 리로드 실행

### 4. 분석 도구 사용
```bash
flutter analyze
```

## 📱 지원 플랫폼

- **Android**: API 21 (Android 5.0) 이상
- **iOS**: iOS 11.0 이상 (향후 지원 예정)

## 🤝 기여하기

기여를 환영합니다! 다음 단계를 따라주세요:

1. 이 저장소를 포크합니다
2. 새 기능 브랜치를 만듭니다 (`git checkout -b feature/AmazingFeature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/AmazingFeature`)
5. Pull Request를 생성합니다

---

**Made with ❤️ using Flutter and TensorFlow Lite**