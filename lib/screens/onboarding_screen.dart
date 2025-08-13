import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'main_navigation.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  PageController _pageController = PageController();
  int _currentPage = 0;
  
  final List<OnboardingPage> _pages = [
    OnboardingPage(
      title: '여행 사진을\n스마트하게 정리하세요',
      description: 'AI가 중복된 사진을 찾아서\n가장 좋은 순간만 남겨드려요',
      icon: Icons.photo_library_rounded,
      gradient: const [Color(0xFF6C63FF), Color(0xFF4CAF50)],
    ),
    OnboardingPage(
      title: '자동 클러스터링으로\n시간을 절약하세요',
      description: '비슷한 사진들을 자동으로 그룹화하고\n베스트 샷을 추천해드려요',
      icon: Icons.auto_awesome_rounded,
      gradient: const [Color(0xFF2196F3), Color(0xFF00BCD4)],
    ),
    OnboardingPage(
      title: '완벽한 여행 앨범을\n만들어보세요',
      description: '간편한 선택으로 완성하는\n나만의 특별한 여행 앨범',
      icon: Icons.collections_bookmark_rounded,
      gradient: const [Color(0xFFFF6B6B), Color(0xFFFF8E53)],
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Column(
        children: [
          // 상단 스킵 버튼
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _goToMain,
                    child: Text(
                      '건너뛰기',
                      style: TextStyle(
                        color: Colors.grey[600],
                        fontSize: 16,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // 페이지뷰
          Expanded(
            child: PageView.builder(
              controller: _pageController,
              itemCount: _pages.length,
              onPageChanged: (index) {
                setState(() {
                  _currentPage = index;
                });
              },
              itemBuilder: (context, index) {
                return _buildPage(_pages[index]);
              },
            ),
          ),

          // 인디케이터와 버튼
          Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              children: [
                // 페이지 인디케이터
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    _pages.length,
                    (index) => AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: _currentPage == index ? 24 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(4),
                        color: _currentPage == index
                            ? const Color(0xFF6C63FF)
                            : Colors.grey[300],
                      ),
                    ),
                  ),
                ),
                
                const SizedBox(height: 32),
                
                // 다음/시작하기 버튼
                SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: ElevatedButton(
                    onPressed: _currentPage == _pages.length - 1
                        ? _requestPermissionsAndStart
                        : _nextPage,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF6C63FF),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                      elevation: 0,
                    ),
                    child: Text(
                      _currentPage == _pages.length - 1 ? '시작하기' : '다음',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPage(OnboardingPage page) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // 아이콘
          Container(
            width: 140,
            height: 140,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: page.gradient,
              ),
              boxShadow: [
                BoxShadow(
                  color: page.gradient[0].withAlpha(100),
                  blurRadius: 20,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Icon(
              page.icon,
              size: 70,
              color: Colors.white,
            ),
          ),
          
          const SizedBox(height: 48),
          
          // 제목
          Text(
            page.title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Color(0xFF2D2D2D),
              height: 1.2,
            ),
          ),
          
          const SizedBox(height: 24),
          
          // 설명
          Text(
            page.description,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  void _nextPage() {
    _pageController.nextPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _goToMain() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (context) => const MainNavigation(),
      ),
    );
  }

  Future<void> _requestPermissionsAndStart() async {
    // Android/iOS 버전에 맞는 권한 요청
    PermissionStatus status;
    
    // Android 13 이상은 photos 권한, 그 이하는 storage 권한
    if (Theme.of(context).platform == TargetPlatform.android) {
      final info = await Permission.photos.status;
      if (!info.isGranted) {
        status = await Permission.photos.request();
        
        // photos 권한이 지원되지 않으면 storage 권한 시도
        if (status.isPermanentlyDenied || status.isDenied) {
          status = await Permission.storage.request();
        }
      } else {
        status = info;
      }
    } else {
      // iOS
      status = await Permission.photos.request();
    }
    
    if (status.isGranted || status.isLimited) {
      _goToMain();
    } else if (status.isDenied) {
      // 권한이 거부된 경우 다이얼로그 표시
      _showPermissionDialog();
    } else if (status.isPermanentlyDenied) {
      // 영구 거부된 경우 설정으로 안내
      _showPermissionDialog();
    } else {
      // 다른 경우에도 메인으로 이동 (나중에 권한 요청)
      _goToMain();
    }
  }

  void _showPermissionDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: const Text(
            '사진 접근 권한이 필요해요',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 18,
            ),
          ),
          content: const Text(
            '여행 사진을 분석하고 정리하기 위해서는\n사진 접근 권한이 필요합니다.',
            style: TextStyle(fontSize: 16, height: 1.4),
          ),
          actions: [
            TextButton(
              onPressed: _goToMain,
              child: const Text('나중에'),
            ),
            ElevatedButton(
              onPressed: () async {
                Navigator.of(context).pop();
                await openAppSettings();
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6C63FF),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
              child: const Text('설정으로 이동'),
            ),
          ],
        );
      },
    );
  }
}

class OnboardingPage {
  final String title;
  final String description;
  final IconData icon;
  final List<Color> gradient;

  OnboardingPage({
    required this.title,
    required this.description,
    required this.icon,
    required this.gradient,
  });
}