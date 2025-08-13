import 'dart:typed_data';

import 'package:photo_manager/photo_manager.dart';
import '../models/photo_cluster.dart';
import 'tflite_service.dart';

class PhotoProcessingService {
  final TFLiteService _tfliteService;
  
  PhotoProcessingService(this._tfliteService);

  Future<ProcessingResult> processPhotos(
    List<AssetEntity> photos, {
    Function(int current, int total)? onProgress,
  }) async {
    final startTime = DateTime.now();
    
    // Extract features for all photos
    final features = <AssetEntity, Float32List>{};
    
    for (int i = 0; i < photos.length; i++) {
      try {
        final feature = await _tfliteService.extractFeatures(photos[i]);
        features[photos[i]] = feature;
        
        onProgress?.call(i + 1, photos.length);
      } catch (e) {
        // Skip failed photos silently
      }
    }

    // Cluster similar photos
    final clusters = _greedyClustering(features);
    
    // Get recommended photos (one from each cluster)
    final recommendedPhotos = clusters.map((cluster) => cluster.representative).toList();
    
    // Calculate processing time
    final processingTime = DateTime.now().difference(startTime).inMilliseconds / 1000.0;
    
    // Count duplicates
    int duplicateCount = 0;
    for (final cluster in clusters) {
      duplicateCount += cluster.photos.length - 1;
    }

    return ProcessingResult(
      clusters: clusters,
      recommendedPhotos: recommendedPhotos,
      totalPhotos: photos.length,
      duplicateCount: duplicateCount,
      processingTime: processingTime,
    );
  }

  List<PhotoCluster> _greedyClustering(Map<AssetEntity, Float32List> features) {
    final clusters = <PhotoCluster>[];
    final processed = <AssetEntity>{};
    int clusterId = 0;

    for (final photo in features.keys) {
      if (processed.contains(photo)) continue;

      // Start new cluster
      final clusterPhotos = <AssetEntity>[photo];
      final photoFeature = features[photo]!;
      processed.add(photo);

      // Find all similar photos
      double totalSimilarity = 0.0;
      int similarityCount = 0;

      for (final otherPhoto in features.keys) {
        if (processed.contains(otherPhoto)) continue;

        final otherFeature = features[otherPhoto]!;
        final similarity = _tfliteService.calculateSimilarity(photoFeature, otherFeature);

        if (_tfliteService.areSimilar(photoFeature, otherFeature)) {
          clusterPhotos.add(otherPhoto);
          processed.add(otherPhoto);
          totalSimilarity += similarity;
          similarityCount++;
        }
      }

      // Select representative (for now, just the first one)
      // In future, could select based on quality metrics
      final representative = clusterPhotos.first;
      
      final averageSimilarity = similarityCount > 0 
          ? totalSimilarity / similarityCount 
          : 1.0;

      clusters.add(PhotoCluster(
        id: 'cluster_$clusterId',
        photos: clusterPhotos,
        representative: representative,
        averageSimilarity: averageSimilarity,
      ));

      clusterId++;
    }

    return clusters;
  }
}