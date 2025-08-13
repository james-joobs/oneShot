import 'dart:typed_data';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'asset_photo_service.dart';

class MockTFLiteService {
  static const double _similarityThreshold = 0.8;
  
  bool _isInitialized = false;

  Future<void> initialize() async {
    debugPrint('MockTFLite: Initializing mock service...');
    
    // Simulate initialization delay
    await Future.delayed(const Duration(seconds: 1));
    
    _isInitialized = true;
    debugPrint('MockTFLite: Mock service initialized successfully');
  }

  Future<Float32List> extractFeaturesFromAssetPhoto(AssetPhoto assetPhoto) async {
    if (!_isInitialized) {
      throw Exception('MockTFLite service not initialized');
    }

    debugPrint('MockTFLite: Processing ${assetPhoto.name}');
    
    // Simulate processing delay
    await Future.delayed(const Duration(milliseconds: 100));
    
    // Generate mock features (1280 dimensions like the real model)
    final features = Float32List(1280);
    
    // Create somewhat realistic features based on image name hash
    // This ensures same images get similar features for clustering
    final nameHash = assetPhoto.name.hashCode;
    final seed = nameHash.abs();
    final mockRandom = math.Random(seed);
    
    for (int i = 0; i < features.length; i++) {
      // Generate features that are somewhat similar for images with similar names
      // This will create clusters for images taken in sequence
      features[i] = mockRandom.nextDouble() * 2 - 1; // Range [-1, 1]
    }
    
    // Add some similarity for images in the same time sequence
    final timePattern = _extractTimePattern(assetPhoto.name);
    if (timePattern != null) {
      // Make features more similar for images from same time period
      for (int i = 0; i < 100; i++) {
        features[i] = features[i] * 0.3 + timePattern * 0.7;
      }
    }
    
    debugPrint('MockTFLite: Generated features for ${assetPhoto.name}');
    return features;
  }

  double? _extractTimePattern(String filename) {
    // Extract time pattern from filename like "KakaoTalk_Photo_2025-08-04-22-02-56"
    final regex = RegExp(r'(\d{2})-(\d{2})-(\d{2})');
    final match = regex.firstMatch(filename);
    
    if (match != null) {
      final hour = int.parse(match.group(1)!);
      final minute = int.parse(match.group(2)!);
      
      // Create similarity pattern based on time
      // Images taken within same hour will be more similar
      return (hour * 60 + minute) / 1440.0; // Normalize to [0, 1]
    }
    
    return null;
  }

  double calculateSimilarity(Float32List features1, Float32List features2) {
    // Cosine similarity
    double dotProduct = 0.0;
    double norm1 = 0.0;
    double norm2 = 0.0;

    for (int i = 0; i < features1.length; i++) {
      dotProduct += features1[i] * features2[i];
      norm1 += features1[i] * features1[i];
      norm2 += features2[i] * features2[i];
    }

    norm1 = math.sqrt(norm1);
    norm2 = math.sqrt(norm2);

    if (norm1 == 0.0 || norm2 == 0.0) return 0.0;
    
    return dotProduct / (norm1 * norm2);
  }

  bool areSimilar(Float32List features1, Float32List features2) {
    return calculateSimilarity(features1, features2) >= _similarityThreshold;
  }

  void dispose() {
    _isInitialized = false;
    debugPrint('MockTFLite: Service disposed');
  }
}