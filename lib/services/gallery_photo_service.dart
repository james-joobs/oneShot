import 'dart:typed_data';
import 'dart:io';
import 'package:photo_manager/photo_manager.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'asset_photo_service.dart';

/// 갤러리 사진을 AssetPhoto 형태로 변환하는 서비스
class GalleryPhotoService {
  /// photo_manager의 AssetEntity를 우리 앱의 AssetPhoto로 변환
  static Future<AssetPhoto> convertToAssetPhoto(AssetEntity entity) async {
    try {
      // 썸네일 데이터 가져오기
      final Uint8List? thumbnailData = await entity.thumbnailDataWithSize(
        const ThumbnailSize(400, 400),
        quality: 95,
      );
      
      if (thumbnailData == null) {
        throw Exception('Failed to load thumbnail for ${entity.id}');
      }

      // 원본 데이터 가져오기 (필요시)
      final Uint8List? originData = await entity.originBytes;
      
      return GalleryAssetPhoto(
        id: entity.id,
        name: entity.title ?? 'Photo_${entity.id}',
        thumbnailData: thumbnailData,
        originData: originData ?? thumbnailData,
        width: entity.width,
        height: entity.height,
        createDateTime: entity.createDateTime,
        modifiedDateTime: entity.modifiedDateTime,
        entity: entity,
      );
    } catch (e) {
      debugPrint('Error converting AssetEntity to AssetPhoto: $e');
      rethrow;
    }
  }

  /// 여러 AssetEntity를 AssetPhoto 리스트로 변환
  static Future<List<AssetPhoto>> convertMultiplePhotos(
    List<AssetEntity> entities, {
    Function(int current, int total)? onProgress,
  }) async {
    final List<AssetPhoto> photos = [];
    
    for (int i = 0; i < entities.length; i++) {
      try {
        final photo = await convertToAssetPhoto(entities[i]);
        photos.add(photo);
        
        if (onProgress != null) {
          onProgress(i + 1, entities.length);
        }
      } catch (e) {
        debugPrint('Skipping photo ${entities[i].id}: $e');
        // 실패한 사진은 건너뛰기
      }
    }
    
    return photos;
  }

  /// 임시 파일로 저장 (AI 처리를 위해)
  static Future<File> saveToTempFile(AssetEntity entity) async {
    final tempDir = await getTemporaryDirectory();
    final tempPath = '${tempDir.path}/temp_${entity.id}.jpg';
    final file = File(tempPath);
    
    final data = await entity.originBytes;
    if (data != null) {
      await file.writeAsBytes(data);
    }
    
    return file;
  }
}

/// 갤러리 사진을 위한 AssetPhoto 구현체
class GalleryAssetPhoto extends AssetPhoto {
  final Uint8List _thumbnailData;
  final Uint8List _originData;
  final int width;
  final int height;
  final DateTime? createDateTime;
  final DateTime? modifiedDateTime;
  final AssetEntity entity;

  GalleryAssetPhoto({
    required String id,
    required String name,
    required Uint8List thumbnailData,
    required Uint8List originData,
    required this.width,
    required this.height,
    this.createDateTime,
    this.modifiedDateTime,
    required this.entity,
  }) : _thumbnailData = thumbnailData,
       _originData = originData,
       super(
         path: 'gallery://${entity.id}',
         name: name,
         id: id,
       );

  @override
  Future<Uint8List> get thumbnailData async => _thumbnailData;

  @override
  Future<Uint8List> get originBytes async => _originData;

  @override
  String toString() => 'GalleryAssetPhoto($name)';
  
  /// 메타데이터 가져오기
  Map<String, dynamic> get metadata => {
    'width': width,
    'height': height,
    'created': createDateTime?.toIso8601String(),
    'modified': modifiedDateTime?.toIso8601String(),
    'size': _originData.length,
  };
  
  /// 파일 크기 (MB)
  double get sizeInMB => _originData.length / (1024 * 1024);
  
  /// 이미지 비율
  double get aspectRatio => width / height;
}