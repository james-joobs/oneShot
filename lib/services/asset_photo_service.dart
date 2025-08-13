import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';

class AssetPhoto {
  final String path;
  final String name;
  final String id;

  AssetPhoto({
    required this.path,
    required this.name,
    required this.id,
  });

  Future<Uint8List> get thumbnailData async {
    final ByteData data = await rootBundle.load(path);
    return data.buffer.asUint8List();
  }

  Future<Uint8List> get originBytes async {
    final ByteData data = await rootBundle.load(path);
    return data.buffer.asUint8List();
  }
}

class AssetPhotoService {
  static const List<String> _imageExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
  
  Future<List<AssetPhoto>> getAssetPhotos() async {
    final List<AssetPhoto> photos = [];
    
    try {
      // data 폴더의 모든 이미지 파일을 수동으로 나열
      // 실제 프로덕션에서는 AssetManifest를 통해 동적으로 가져올 수 있습니다
      final List<String> imagePaths = await _getImagePaths();
      
      for (int i = 0; i < imagePaths.length; i++) {
        final path = imagePaths[i];
        final name = path.split('/').last;
        
        photos.add(AssetPhoto(
          path: path,
          name: name,
          id: 'asset_$i',
        ));
      }
      
      debugPrint('Found ${photos.length} asset photos');
    } catch (e) {
      debugPrint('Error loading asset photos: $e');
    }
    
    return photos;
  }

  Future<List<String>> _getImagePaths() async {
    try {
      // AssetManifest에서 모든 assets 가져오기
      final Map<String, dynamic> manifestMap = 
          Map<String, dynamic>.from(
            await rootBundle.loadStructuredData(
              'AssetManifest.json', 
              (value) async => Map<String, dynamic>.from(
                jsonDecode(value)
              )
            )
          );
      
      final List<String> imagePaths = [];
      
      for (String key in manifestMap.keys) {
        if (key.startsWith('data/') && _isImageFile(key)) {
          imagePaths.add(key);
        }
      }
      
      return imagePaths;
    } catch (e) {
      debugPrint('Error reading AssetManifest: $e');
      // Fallback: 수동으로 알려진 이미지들 반환
      return _getFallbackImagePaths();
    }
  }

  List<String> _getFallbackImagePaths() {
    // data 폴더에 있는 이미지들을 수동으로 나열
    // 실제 파일명에 맞게 수정해주세요
    return [
      'data/KakaoTalk_Photo_2025-08-04-22-02-56 001.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-56 002.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-56 003.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-56 004.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-57 005.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-57 006.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-57 007.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-57 008.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-57 009.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-58 010.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-58 011.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-58 012.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-58 013.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-59 014.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-59 015.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-02-59 016.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-00 017.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-01 018.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-01 019.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-01 020.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 021.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 022.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 023.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 024.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 025.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 026.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-02 027.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-03 028.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-03 029.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-03-03 030.jpeg',
      // 두 번째 배치
      'data/KakaoTalk_Photo_2025-08-04-22-04-17 001.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-17 002.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-17 003.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-18 004.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-18 005.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-18 006.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-18 007.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-18 008.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-18 009.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-19 010.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-19 011.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-19 012.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-19 013.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-20 014.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-20 015.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-21 016.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-21 017.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-21 018.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-22 019.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-22 020.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-22 021.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-22 022.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-22 023.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-23 024.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-23 025.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-24 026.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-24 027.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-24 028.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-24 029.jpeg',
      'data/KakaoTalk_Photo_2025-08-04-22-04-24 030.jpeg',
    ];
  }
  
  bool _isImageFile(String path) {
    final String lowerPath = path.toLowerCase();
    return _imageExtensions.any((ext) => lowerPath.endsWith(ext));
  }
}