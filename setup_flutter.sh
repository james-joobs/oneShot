#!/bin/bash

echo "🚀 Setting up Flutter Photo Curator App"
echo "========================================"

# Check if Flutter is installed
if ! command -v flutter &> /dev/null; then
    echo "❌ Flutter is not installed or not in PATH"
    echo ""
    echo "Please install Flutter first:"
    echo "  macOS: brew install flutter"
    echo "  Or visit: https://flutter.dev/docs/get-started/install"
    echo ""
    exit 1
fi

echo "✅ Flutter found: $(flutter --version | head -1)"

# Navigate to Flutter app directory
cd flutter_app || {
    echo "❌ flutter_app directory not found"
    exit 1
}

echo ""
echo "📦 Installing Flutter dependencies..."
flutter pub get

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully!"
else
    echo "❌ Failed to install dependencies"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "  1. Check internet connection"
    echo "  2. Run 'flutter doctor' to check setup"
    echo "  3. Try 'flutter clean' then 'flutter pub get'"
    exit 1
fi

echo ""
echo "🔍 Checking Flutter setup..."
flutter doctor

echo ""
echo "✅ Setup complete! Next steps:"
echo ""
echo "  cd flutter_app"
echo "  flutter run                    # Run in debug mode"
echo "  flutter run --release          # Run optimized build"
echo "  flutter build apk --release    # Build Android APK"
echo ""
echo "📱 Make sure you have:"
echo "  - Android emulator running, or"
echo "  - iOS simulator running, or" 
echo "  - Physical device connected"
echo ""
echo "🤖 The app will automatically load the 3.6MB AI model"
echo "   and start processing your photos on-device!"