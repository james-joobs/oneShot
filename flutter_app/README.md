# Photo Curator Flutter App

## Prerequisites

1. **Install Flutter SDK**:
   ```bash
   # macOS (using homebrew)
   brew install flutter
   
   # Or download from: https://flutter.dev/docs/get-started/install
   ```

2. **Verify Flutter installation**:
   ```bash
   flutter doctor
   ```

## Setup & Run

1. **Install dependencies**:
   ```bash
   cd flutter_app
   flutter pub get
   ```

2. **Run the app**:
   ```bash
   # For iOS Simulator
   flutter run -d ios
   
   # For Android Emulator  
   flutter run -d android
   
   # For Chrome (web testing)
   flutter run -d chrome
   ```

3. **Build for release**:
   ```bash
   # Android APK
   flutter build apk --release
   
   # iOS App
   flutter build ios --release
   ```

## App Architecture

### 📁 Directory Structure
```
lib/
├── main.dart                    # App entry point & permissions
├── providers/                   # State management
│   └── photo_curation_provider.dart
├── services/                    # Core logic
│   └── tflite_service.dart     # AI model integration
├── models/                      # Data models
│   └── photo_cluster.dart
├── screens/                     # UI screens
│   ├── home_screen.dart        # Main interface
│   └── cluster_detail_screen.dart
├── widgets/                     # Reusable components
│   ├── photo_grid.dart
│   └── stats_card.dart
└── utils/                       # Utilities
    └── similarity_calculator.dart
```

### 🔧 Key Features

1. **Permission Management**: Auto-requests photo library access on first launch
2. **Real-time Processing**: Shows progress during AI analysis
3. **Visual Clustering**: Groups similar photos with similarity scores
4. **Smart Recommendations**: Selects best photo from each cluster
5. **Space Statistics**: Shows storage savings and duplicate counts

### 🤖 AI Integration

- **Model**: MobileNetV3-based similarity detection (3.6MB)
- **Processing**: On-device TensorFlow Lite inference
- **Performance**: ~6.4ms per image on modern devices
- **Privacy**: No cloud processing, all data stays on device

### 📱 UI Components

1. **Home Tab**: 
   - Processing controls and progress
   - Statistics cards (total, duplicates, recommended, space saved)
   - Quick action buttons

2. **Clusters Tab**:
   - List of photo clusters with duplicate counts
   - Tap to see detailed cluster view
   - Visual indicators for cluster size

3. **Recommended Tab**:
   - Grid of curated photos (duplicates removed)
   - One representative from each cluster
   - Final optimized photo collection

## Dependencies

```yaml
# Core Flutter
flutter: sdk: flutter
provider: ^6.0.5          # State management

# Photo access
photo_manager: ^3.0.0     # Gallery access
permission_handler: ^11.0.1  # Permissions

# AI & Image processing  
tflite_flutter: ^0.9.0    # TensorFlow Lite
image: ^4.0.17            # Image manipulation

# Utilities
path_provider: ^2.1.1     # File paths
path: ^1.8.3             # Path utilities
```

## Troubleshooting

### Common Issues:

1. **"No photos found"**: 
   - Grant photo library permission in device settings
   - Check if photos exist in gallery

2. **"Model loading failed"**:
   - Ensure `assets/models/similarity_model_dynamic.tflite` exists
   - Check file permissions and app bundle

3. **Slow processing**:
   - Normal for first run (model loading)
   - Performance improves after initial load
   - Large photo collections (>1000) may take time

### Performance Tips:

- **Memory**: App processes photos sequentially to minimize RAM usage
- **Battery**: Uses device-optimized TFLite delegates (NNAPI, GPU)
- **Storage**: Temporary files are cleaned up automatically

## Development

### Testing:
```bash
# Run unit tests
flutter test

# Run integration tests  
flutter test integration_test/
```

### Debugging:
```bash
# Debug mode with hot reload
flutter run --debug

# Profile mode for performance testing
flutter run --profile
```

## Model Information

The app uses a pre-trained MobileNetV3 model optimized for mobile deployment:

- **Input**: 224x224 RGB images  
- **Output**: 512-dimensional embeddings
- **Quantization**: Dynamic quantization for size/speed balance
- **Compatibility**: Works with NNAPI, GPU delegates on supported devices

Model file: `assets/models/similarity_model_dynamic.tflite` (3.6MB)