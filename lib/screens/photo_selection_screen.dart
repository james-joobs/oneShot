import 'package:flutter/material.dart';
import 'package:photo_manager/photo_manager.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/photo_processing_provider.dart';
import '../services/asset_photo_service.dart';

class PhotoSelectionScreen extends StatefulWidget {
  const PhotoSelectionScreen({super.key});

  @override
  State<PhotoSelectionScreen> createState() => _PhotoSelectionScreenState();
}

class _PhotoSelectionScreenState extends State<PhotoSelectionScreen>
    with TickerProviderStateMixin {
  List<AssetPathEntity> _albums = [];
  List<AssetEntity> _selectedPhotos = [];
  List<AssetEntity> _currentPhotos = [];
  AssetPathEntity? _currentAlbum;
  bool _isLoading = true;
  bool _isSelectionMode = false;
  
  late AnimationController _selectionAnimationController;
  late AnimationController _fabAnimationController;

  @override
  void initState() {
    super.initState();
    _selectionAnimationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _fabAnimationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _requestPermissionAndLoadPhotos();
  }

  @override
  void dispose() {
    _selectionAnimationController.dispose();
    _fabAnimationController.dispose();
    super.dispose();
  }

  Future<void> _requestPermissionAndLoadPhotos() async {
    try {
      final PermissionState ps = await PhotoManager.requestPermissionExtend();
      if (ps.isAuth) {
        await _loadAlbums();
      } else if (ps.hasAccess) {
        // 제한적 접근 권한이라도 있으면 로드
        await _loadAlbums();
      } else {
        // 권한이 없을 때만 다이얼로그 표시
        if (mounted) {
          _showPermissionDialog();
        }
      }
    } catch (e) {
      debugPrint('Error requesting permission: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _loadAlbums() async {
    setState(() => _isLoading = true);
    
    final List<AssetPathEntity> albums = await PhotoManager.getAssetPathList(
      type: RequestType.image,
      onlyAll: false,
    );
    
    setState(() {
      _albums = albums;
      _isLoading = false;
    });
    
    if (albums.isNotEmpty) {
      await _loadPhotosFromAlbum(albums.first);
    }
  }

  Future<void> _loadPhotosFromAlbum(AssetPathEntity album) async {
    setState(() => _isLoading = true);
    
    final List<AssetEntity> photos = await album.getAssetListRange(
      start: 0,
      end: 1000, // 최대 1000장
    );
    
    setState(() {
      _currentAlbum = album;
      _currentPhotos = photos;
      _isLoading = false;
    });
  }

  void _toggleSelectionMode() {
    setState(() {
      _isSelectionMode = !_isSelectionMode;
      if (!_isSelectionMode) {
        _selectedPhotos.clear();
        _fabAnimationController.reverse();
      } else {
        _fabAnimationController.forward();
      }
    });
    _selectionAnimationController.forward().then((_) {
      _selectionAnimationController.reverse();
    });
    HapticFeedback.lightImpact();
  }

  void _togglePhotoSelection(AssetEntity photo) {
    setState(() {
      if (_selectedPhotos.contains(photo)) {
        _selectedPhotos.remove(photo);
      } else {
        _selectedPhotos.add(photo);
      }
    });
    HapticFeedback.lightImpact();
  }

  void _selectAll() {
    setState(() {
      _selectedPhotos = List.from(_currentPhotos);
    });
    HapticFeedback.mediumImpact();
  }

  void _clearSelection() {
    setState(() {
      _selectedPhotos.clear();
    });
    HapticFeedback.lightImpact();
  }

  void _showPermissionDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('사진 접근 권한 필요'),
        content: const Text('앱에서 사진을 분석하기 위해 갤러리 접근 권한이 필요합니다.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('취소'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(context).pop();
              await openAppSettings();
            },
            child: const Text('설정으로 이동'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildAlbumSelector(),
            Expanded(child: _buildPhotoGrid()),
          ],
        ),
      ),
      floatingActionButton: _buildFloatingActionButton(),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF4CAF50), Color(0xFF45A049)],
                  ),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.photo_library_rounded,
                  color: Colors.white,
                  size: 20,
                ),
              ),
              const SizedBox(width: 16),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '사진 선택',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF2D2D2D),
                      ),
                    ),
                    Text(
                      'AI로 분석할 사진들을 선택하세요',
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey,
                      ),
                    ),
                  ],
                ),
              ),
              if (_isSelectionMode) ...[
                _buildActionButton(
                  icon: Icons.select_all_rounded,
                  onTap: _selectAll,
                  color: const Color(0xFF4CAF50),
                ),
                const SizedBox(width: 8),
                _buildActionButton(
                  icon: Icons.clear_all_rounded,
                  onTap: _clearSelection,
                  color: const Color(0xFFFF6B6B),
                ),
                const SizedBox(width: 8),
              ],
              _buildActionButton(
                icon: _isSelectionMode ? Icons.close : Icons.check_circle_rounded,
                onTap: _toggleSelectionMode,
                color: _isSelectionMode ? const Color(0xFFFF6B6B) : const Color(0xFF6C63FF),
              ),
            ],
          ),
          if (_selectedPhotos.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF6C63FF).withAlpha(40),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                '${_selectedPhotos.length}장 선택됨',
                style: const TextStyle(
                  color: Color(0xFF6C63FF),
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required VoidCallback onTap,
    required Color color,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: _selectionAnimationController,
        builder: (context, child) {
          return Transform.scale(
            scale: 1.0 + (_selectionAnimationController.value * 0.1),
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withAlpha(40),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: color.withAlpha(100),
                  width: 1,
                ),
              ),
              child: Icon(icon, size: 20, color: color),
            ),
          );
        },
      ),
    );
  }

  Widget _buildAlbumSelector() {
    if (_albums.isEmpty) return const SizedBox();
    
    return Container(
      height: 60,
      margin: const EdgeInsets.symmetric(horizontal: 24),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _albums.length,
        itemBuilder: (context, index) {
          final album = _albums[index];
          final isSelected = _currentAlbum?.id == album.id;
          
          return GestureDetector(
            onTap: () => _loadPhotosFromAlbum(album),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(right: 12),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: isSelected ? const Color(0xFF6C63FF) : Colors.white,
                borderRadius: BorderRadius.circular(30),
                border: Border.all(
                  color: isSelected ? const Color(0xFF6C63FF) : Colors.grey.shade300,
                ),
                boxShadow: isSelected ? [
                  BoxShadow(
                    color: const Color(0xFF6C63FF).withAlpha(60),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ] : null,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.photo_album_rounded,
                    size: 16,
                    color: isSelected ? Colors.white : Colors.grey[600],
                  ),
                  const SizedBox(width: 8),
                  Text(
                    album.name,
                    style: TextStyle(
                      color: isSelected ? Colors.white : Colors.grey[700],
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildPhotoGrid() {
    if (_isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('사진을 불러오는 중...'),
          ],
        ),
      );
    }
    
    if (_currentPhotos.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.photo_library_outlined, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('사진이 없습니다', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.all(24),
      child: GridView.builder(
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 3,
          crossAxisSpacing: 8,
          mainAxisSpacing: 8,
          childAspectRatio: 1,
        ),
        itemCount: _currentPhotos.length,
        itemBuilder: (context, index) {
          final photo = _currentPhotos[index];
          final isSelected = _selectedPhotos.contains(photo);
          
          return GestureDetector(
            onTap: () {
              if (_isSelectionMode) {
                _togglePhotoSelection(photo);
              } else {
                // 사진 상세 보기 (구현 예정)
              }
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isSelected ? const Color(0xFF6C63FF) : Colors.transparent,
                  width: 3,
                ),
              ),
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: AssetEntityImage(
                      photo,
                      width: double.infinity,
                      height: double.infinity,
                      fit: BoxFit.cover,
                    ),
                  ),
                  if (_isSelectionMode)
                    Positioned(
                      top: 8,
                      right: 8,
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          color: isSelected ? const Color(0xFF6C63FF) : Colors.white.withAlpha(200),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isSelected ? const Color(0xFF6C63FF) : Colors.grey,
                            width: 2,
                          ),
                        ),
                        child: isSelected
                            ? const Icon(
                                Icons.check,
                                size: 16,
                                color: Colors.white,
                              )
                            : null,
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildFloatingActionButton() {
    if (_selectedPhotos.isEmpty) return const SizedBox();
    
    return AnimatedBuilder(
      animation: _fabAnimationController,
      builder: (context, child) {
        return Transform.scale(
          scale: _fabAnimationController.value,
          child: FloatingActionButton.extended(
            onPressed: () async {
              // 큐레이션 시작
              final provider = Provider.of<PhotoProcessingProvider>(context, listen: false);
              
              // 선택한 사진들로 큐레이션 시작
              await provider.processGallerySelectedPhotos(_selectedPhotos);
              
              if (context.mounted) {
                // 큐레이션 화면으로 이동
                Navigator.pushNamed(context, '/curation');
                
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('${_selectedPhotos.length}장의 사진 큐레이션 시작!'),
                    behavior: SnackBarBehavior.floating,
                    backgroundColor: const Color(0xFF6C63FF),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                );
                
                // 선택 모드 종료
                setState(() {
                  _isSelectionMode = false;
                  _selectedPhotos.clear();
                  _fabAnimationController.reverse();
                });
              }
            },
            backgroundColor: const Color(0xFF6C63FF),
            foregroundColor: Colors.white,
            icon: const Icon(Icons.auto_awesome_rounded),
            label: Text('${_selectedPhotos.length}장 큐레이션'),
          ),
        );
      },
    );
  }
}

class AssetEntityImage extends StatelessWidget {
  final AssetEntity asset;
  final double? width;
  final double? height;
  final BoxFit fit;

  const AssetEntityImage(
    this.asset, {
    super.key,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
  });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uint8List?>(
      future: asset.thumbnailDataWithSize(const ThumbnailSize(200, 200)),
      builder: (context, snapshot) {
        if (snapshot.hasData && snapshot.data != null) {
          return Image.memory(
            snapshot.data!,
            width: width,
            height: height,
            fit: fit,
          );
        }
        return Container(
          width: width,
          height: height,
          color: Colors.grey[300],
          child: const Center(
            child: CircularProgressIndicator(),
          ),
        );
      },
    );
  }
}