import 'package:photo_manager/photo_manager.dart';
import '../services/asset_photo_service.dart';

class PhotoCluster {
  final String id;
  final List<AssetEntity> photos;
  final AssetEntity representative;
  final double averageSimilarity;

  PhotoCluster({
    required this.id,
    required this.photos,
    required this.representative,
    required this.averageSimilarity,
  });

  int get photoCount => photos.length;

  int get savedCount => photos.length - 1;

  double get savedPercentage => savedCount / photos.length * 100;
}

class AssetPhotoCluster {
  final String id;
  final List<AssetPhoto> photos;
  final AssetPhoto representative;
  final double averageSimilarity;

  AssetPhotoCluster({
    required this.id,
    required this.photos,
    required this.representative,
    required this.averageSimilarity,
  });

  int get photoCount => photos.length;

  int get savedCount => photos.length - 1;

  double get savedPercentage => savedCount / photos.length * 100;
}

class ProcessingResult {
  final List<PhotoCluster> clusters;
  final List<AssetEntity> recommendedPhotos;
  final int totalPhotos;
  final int duplicateCount;
  final double processingTime;

  ProcessingResult({
    required this.clusters,
    required this.recommendedPhotos,
    required this.totalPhotos,
    required this.duplicateCount,
    required this.processingTime,
  });

  int get savedPhotos => totalPhotos - recommendedPhotos.length;
  
  double get savedPercentage => savedPhotos / totalPhotos * 100;
}

class AssetProcessingResult {
  final List<AssetPhotoCluster> clusters;
  final List<AssetPhoto> recommendedPhotos;
  final int totalPhotos;
  final int duplicateCount;
  final double processingTime;

  AssetProcessingResult({
    required this.clusters,
    required this.recommendedPhotos,
    required this.totalPhotos,
    required this.duplicateCount,
    required this.processingTime,
  });

  int get savedPhotos => totalPhotos - recommendedPhotos.length;
  
  double get savedPercentage => savedPhotos / totalPhotos * 100;
}