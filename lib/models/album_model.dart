import 'package:flutter/material.dart';
import '../services/asset_photo_service.dart';

/// 앨범 데이터 모델
class AlbumModel {
  final String id;
  final String title;
  final String? description;
  final List<AssetPhoto> photos;
  final DateTime createdAt;
  final DateTime? modifiedAt;
  final Color themeColor;
  final String? coverPhotoId;
  final Map<String, dynamic>? metadata;

  AlbumModel({
    required this.id,
    required this.title,
    this.description,
    required this.photos,
    required this.createdAt,
    this.modifiedAt,
    required this.themeColor,
    this.coverPhotoId,
    this.metadata,
  });

  /// 커버 사진 가져오기
  AssetPhoto? get coverPhoto {
    if (coverPhotoId != null) {
      try {
        return photos.firstWhere((photo) => photo.id == coverPhotoId);
      } catch (_) {
        // 커버 사진 ID가 잘못된 경우 첫 번째 사진 반환
      }
    }
    return photos.isNotEmpty ? photos.first : null;
  }

  /// 앨범 사진 개수
  int get photoCount => photos.length;

  /// 앨범 크기 (MB)
  Future<double> get totalSizeInMB async {
    double totalSize = 0;
    for (final photo in photos) {
      final bytes = await photo.originBytes;
      totalSize += bytes.length / (1024 * 1024);
    }
    return totalSize;
  }

  /// 복사본 생성
  AlbumModel copyWith({
    String? id,
    String? title,
    String? description,
    List<AssetPhoto>? photos,
    DateTime? createdAt,
    DateTime? modifiedAt,
    Color? themeColor,
    String? coverPhotoId,
    Map<String, dynamic>? metadata,
  }) {
    return AlbumModel(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      photos: photos ?? this.photos,
      createdAt: createdAt ?? this.createdAt,
      modifiedAt: modifiedAt ?? this.modifiedAt,
      themeColor: themeColor ?? this.themeColor,
      coverPhotoId: coverPhotoId ?? this.coverPhotoId,
      metadata: metadata ?? this.metadata,
    );
  }

  /// JSON 변환 (저장용)
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'photoIds': photos.map((p) => p.id).toList(),
      'createdAt': createdAt.toIso8601String(),
      'modifiedAt': modifiedAt?.toIso8601String(),
      'themeColor': themeColor.value,
      'coverPhotoId': coverPhotoId,
      'metadata': metadata,
    };
  }

  /// JSON에서 생성 (복원용)
  factory AlbumModel.fromJson(Map<String, dynamic> json, List<AssetPhoto> allPhotos) {
    final photoIds = List<String>.from(json['photoIds'] ?? []);
    final albumPhotos = photoIds
        .map((id) => allPhotos.firstWhere(
              (photo) => photo.id == id,
              orElse: () => throw Exception('Photo not found: $id'),
            ))
        .toList();

    return AlbumModel(
      id: json['id'],
      title: json['title'],
      description: json['description'],
      photos: albumPhotos,
      createdAt: DateTime.parse(json['createdAt']),
      modifiedAt: json['modifiedAt'] != null 
          ? DateTime.parse(json['modifiedAt']) 
          : null,
      themeColor: Color(json['themeColor']),
      coverPhotoId: json['coverPhotoId'],
      metadata: json['metadata'],
    );
  }
}

/// 앨범 관리 서비스
class AlbumService extends ChangeNotifier {
  final List<AlbumModel> _albums = [];
  
  /// 모든 앨범
  List<AlbumModel> get albums => List.unmodifiable(_albums);
  
  /// 앨범 개수
  int get albumCount => _albums.length;
  
  /// 전체 사진 개수
  int get totalPhotoCount => _albums.fold(0, (sum, album) => sum + album.photoCount);

  /// 앨범 생성
  AlbumModel createAlbum({
    required String title,
    String? description,
    required List<AssetPhoto> photos,
    Color? themeColor,
    String? coverPhotoId,
  }) {
    final album = AlbumModel(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      title: title,
      description: description,
      photos: photos,
      createdAt: DateTime.now(),
      themeColor: themeColor ?? _generateThemeColor(title),
      coverPhotoId: coverPhotoId,
    );
    
    _albums.add(album);
    notifyListeners();
    
    return album;
  }

  /// 앨범 업데이트
  void updateAlbum(AlbumModel album) {
    final index = _albums.indexWhere((a) => a.id == album.id);
    if (index != -1) {
      _albums[index] = album.copyWith(
        modifiedAt: DateTime.now(),
      );
      notifyListeners();
    }
  }

  /// 앨범 삭제
  void deleteAlbum(String albumId) {
    _albums.removeWhere((album) => album.id == albumId);
    notifyListeners();
  }

  /// 앨범에 사진 추가
  void addPhotosToAlbum(String albumId, List<AssetPhoto> photos) {
    final album = _albums.firstWhere((a) => a.id == albumId);
    final updatedPhotos = [...album.photos, ...photos];
    
    updateAlbum(album.copyWith(
      photos: updatedPhotos,
      modifiedAt: DateTime.now(),
    ));
  }

  /// 앨범에서 사진 제거
  void removePhotosFromAlbum(String albumId, List<String> photoIds) {
    final album = _albums.firstWhere((a) => a.id == albumId);
    final updatedPhotos = album.photos
        .where((photo) => !photoIds.contains(photo.id))
        .toList();
    
    updateAlbum(album.copyWith(
      photos: updatedPhotos,
      modifiedAt: DateTime.now(),
    ));
  }

  /// ID로 앨범 찾기
  AlbumModel? findAlbumById(String id) {
    try {
      return _albums.firstWhere((album) => album.id == id);
    } catch (_) {
      return null;
    }
  }

  /// 최근 앨범 가져오기
  List<AlbumModel> getRecentAlbums({int limit = 5}) {
    final sorted = List<AlbumModel>.from(_albums)
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    
    return sorted.take(limit).toList();
  }

  /// 테마 색상 생성
  Color _generateThemeColor(String title) {
    final colors = [
      const Color(0xFF6C63FF),
      const Color(0xFF4CAF50),
      const Color(0xFF2196F3),
      const Color(0xFFFF6B6B),
      const Color(0xFF9C27B0),
      const Color(0xFFFF9800),
      const Color(0xFF00BCD4),
      const Color(0xFFE91E63),
    ];
    
    final index = title.hashCode % colors.length;
    return colors[index];
  }

  /// 큐레이션 결과로부터 앨범 생성
  AlbumModel createAlbumFromCuration({
    required String title,
    required List<AssetPhoto> recommendedPhotos,
    String? description,
  }) {
    return createAlbum(
      title: title,
      description: description ?? '${recommendedPhotos.length}장의 엄선된 사진',
      photos: recommendedPhotos,
      themeColor: const Color(0xFF6C63FF),
    );
  }
}