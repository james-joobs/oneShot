import 'package:flutter/foundation.dart';
import 'package:photo_manager/photo_manager.dart';
import '../models/photo_cluster.dart';
import '../services/asset_photo_service.dart';
import '../services/gallery_photo_service.dart';
import '../services/tflite_service.dart';
import '../services/mock_tflite_service.dart';
import '../engine/face_models.dart';
import '../engine/grouping.dart';
import '../engine/ranking.dart';
import '../engine/tflite_embedding_runner.dart';
import '../engine/embedding_runner.dart';

class PhotoProcessingProvider extends ChangeNotifier {
  final TFLiteService _tfliteService = TFLiteService();
  // Removed unused legacy processing service in favor of new engine pipeline
  // late final AssetPhotoProcessingService _assetProcessingService;
  late final AssetPhotoService _assetPhotoService;
  late DuplicateGrouper _grouper;
  late final Ranker _ranker;
  late EmbeddingRunner _embeddingRunner;

  AssetProcessingResult? _result;
  bool _isProcessing = false;
  bool _isInitialized = false;
  double _progress = 0.0;
  String _statusMessage = '';
  String? _errorMessage;

  AssetProcessingResult? get result => _result;
  bool get isProcessing => _isProcessing;
  bool get isInitialized => _isInitialized;
  double get progress => _progress;
  String get statusMessage => _statusMessage;
  String? get errorMessage => _errorMessage;
  bool get hasResult => _result != null;
  
  // 새로운 통계 속성들
  int get processedPhotos => _result?.totalPhotos ?? 0;
  int get savedSpaceMB => (_result?.duplicateCount ?? 0) * 2; // 가정: 사진당 평균 2MB
  int get createdAlbums => _result?.clusters.length ?? 0;

  PhotoProcessingProvider() {
    // _assetProcessingService = AssetPhotoProcessingService(_tfliteService);
    _assetPhotoService = AssetPhotoService();
    _embeddingRunner = TFLiteEmbeddingRunner(_tfliteService);
    _grouper = DuplicateGrouper(
      embeddingRunner: _embeddingRunner,
      faceEngine: FaceEngineMock(),
    );
    _ranker = const Ranker();
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      _statusMessage = 'AI 모델 초기화 중...';
      notifyListeners();

      try {
        await _embeddingRunner.initialize();
        _isInitialized = true;
        _statusMessage = '준비 완료';
      } catch (e) {
        // Fallback to mock engine when TFLite creation fails (e.g., op version mismatch)
        _statusMessage = '실제 모델 초기화 실패, 모의 엔진으로 전환 중...';
        notifyListeners();

        final mock = MockTFLiteService();
        _embeddingRunner = MockEmbeddingRunner(mock);
        _grouper = DuplicateGrouper(
          embeddingRunner: _embeddingRunner,
          faceEngine: FaceEngineMock(),
        );
        await _embeddingRunner.initialize();

        _isInitialized = true;
        _statusMessage = '모의 엔진으로 준비 완료';
      }
      notifyListeners();
    } catch (e) {
      _errorMessage = 'AI 모델 초기화 실패: $e';
      _isInitialized = false;
      notifyListeners();
    }
  }

  Future<void> processGalleryPhotos() async {
    if (_isProcessing) return;

    _isProcessing = true;
    _progress = 0.0;
    _errorMessage = null;
    notifyListeners();

    try {
      // Wait for initialization to complete if not already done
      if (!_isInitialized) {
        _statusMessage = 'AI 모델 초기화 중...';
        notifyListeners();

        try {
          await _embeddingRunner.initialize();
          _isInitialized = true;
        } catch (_) {
          // Already handled in _initialize; leave as is
        }
      }

      _statusMessage = '프로젝트 이미지 로딩 중...';
      notifyListeners();

      // Get asset photos from the data folder
      final photos = await _assetPhotoService.getAssetPhotos();

      if (photos.isEmpty) {
        throw Exception(
            'data 폴더에서 이미지를 찾을 수 없습니다.\n프로젝트의 data/ 폴더에 이미지 파일을 추가해주세요.');
      }

      _statusMessage = '${photos.length}개 사진 분석 중...';
      notifyListeners();

      // New engine: group with fused duplicate score then rank representative
      final start = DateTime.now();
      final clusters = await _grouper.group(
        photos,
        onProgress: (current, total) {
          _progress = current / total;
          _statusMessage = '$current/$total 임베딩/유사도 계산 중...';
          notifyListeners();
        },
      );

      // Pick representative per cluster and rebuild clusters with representative set
      final rebuiltClusters = <AssetPhotoCluster>[];
      final recommended = <AssetPhoto>[];
      for (final c in clusters) {
        final best = await _ranker.pickBest(c.photos);
        recommended.add(best.photo);
        rebuiltClusters.add(AssetPhotoCluster(
          id: c.id,
          photos: c.photos,
          representative: best.photo,
          averageSimilarity: c.averageSimilarity,
        ));
      }

      // Build result
      int duplicateCount = 0;
      for (final c in rebuiltClusters) {
        duplicateCount += c.photos.length - 1;
      }
      final elapsed = DateTime.now().difference(start).inMilliseconds / 1000.0;
      _result = AssetProcessingResult(
        clusters: rebuiltClusters,
        recommendedPhotos: recommended,
        totalPhotos: photos.length,
        duplicateCount: duplicateCount,
        processingTime: elapsed,
      );

      _statusMessage = '완료!';
      _progress = 1.0;
    } catch (e) {
      _errorMessage = e.toString();
      _statusMessage = '오류 발생';
    } finally {
      _isProcessing = false;
      notifyListeners();
    }
  }

  /// 갤러리에서 선택한 사진들을 처리
  Future<void> processGallerySelectedPhotos(List<AssetEntity> selectedPhotos) async {
    if (_isProcessing || selectedPhotos.isEmpty) return;

    _isProcessing = true;
    _progress = 0.0;
    _errorMessage = null;
    notifyListeners();

    try {
      // 초기화 확인
      if (!_isInitialized) {
        _statusMessage = 'AI 모델 초기화 중...';
        notifyListeners();
        await _initialize();
      }

      _statusMessage = '선택한 사진들을 변환 중...';
      notifyListeners();

      // AssetEntity를 AssetPhoto로 변환
      final photos = await GalleryPhotoService.convertMultiplePhotos(
        selectedPhotos,
        onProgress: (current, total) {
          _progress = current / total * 0.3; // 변환은 전체의 30%
          _statusMessage = '$current/$total 사진 변환 중...';
          notifyListeners();
        },
      );

      if (photos.isEmpty) {
        throw Exception('변환된 사진이 없습니다.');
      }

      _statusMessage = '${photos.length}개 사진 AI 분석 중...';
      _progress = 0.3;
      notifyListeners();

      // AI 엔진으로 클러스터링
      final start = DateTime.now();
      final clusters = await _grouper.group(
        photos,
        onProgress: (current, total) {
          _progress = 0.3 + (current / total * 0.6); // 분석은 60%
          _statusMessage = '$current/$total AI 분석 중...';
          notifyListeners();
        },
      );

      // 각 클러스터에서 대표 사진 선정
      _statusMessage = '베스트 샷 선정 중...';
      _progress = 0.9;
      notifyListeners();

      final rebuiltClusters = <AssetPhotoCluster>[];
      final recommended = <AssetPhoto>[];
      
      for (final c in clusters) {
        final best = await _ranker.pickBest(c.photos);
        recommended.add(best.photo);
        rebuiltClusters.add(AssetPhotoCluster(
          id: c.id,
          photos: c.photos,
          representative: best.photo,
          averageSimilarity: c.averageSimilarity,
        ));
      }

      // 결과 생성
      int duplicateCount = 0;
      for (final c in rebuiltClusters) {
        duplicateCount += c.photos.length - 1;
      }
      
      final elapsed = DateTime.now().difference(start).inMilliseconds / 1000.0;
      _result = AssetProcessingResult(
        clusters: rebuiltClusters,
        recommendedPhotos: recommended,
        totalPhotos: photos.length,
        duplicateCount: duplicateCount,
        processingTime: elapsed,
      );

      _statusMessage = '큐레이션 완료!';
      _progress = 1.0;
      
      debugPrint('큐레이션 완료: ${photos.length}장 → ${recommended.length}장 (${duplicateCount}장 중복 제거)');
    } catch (e) {
      _errorMessage = '처리 중 오류: $e';
      _statusMessage = '오류 발생';
      debugPrint('Error processing gallery photos: $e');
    } finally {
      _isProcessing = false;
      notifyListeners();
    }
  }

  void clearResult() {
    _result = null;
    _progress = 0.0;
    _statusMessage = '';
    _errorMessage = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _tfliteService.dispose();
    super.dispose();
  }
}
