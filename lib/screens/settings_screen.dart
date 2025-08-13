import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              _buildHeader(),
              _buildSettingsSection(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF9C27B0), Color(0xFFE91E63)],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.settings_rounded,
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
                  '설정',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2D2D2D),
                  ),
                ),
                Text(
                  '앱 설정 및 개인화 옵션',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSettingsSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          _buildSettingsGroup(
            title: 'AI 설정',
            items: [
              SettingsItem(
                icon: Icons.auto_awesome_rounded,
                title: '큐레이션 정확도',
                subtitle: '높음',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
              SettingsItem(
                icon: Icons.speed_rounded,
                title: '처리 속도',
                subtitle: 'NNAPI 가속 사용',
                trailing: Switch(
                  value: true,
                  onChanged: (value) {},
                  activeColor: const Color(0xFF6C63FF),
                ),
                onTap: () {},
              ),
            ],
          ),
          
          const SizedBox(height: 24),
          
          _buildSettingsGroup(
            title: '저장소',
            items: [
              SettingsItem(
                icon: Icons.storage_rounded,
                title: '캐시 정리',
                subtitle: '임시 파일 및 캐시 삭제',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
              SettingsItem(
                icon: Icons.cloud_upload_rounded,
                title: '백업 설정',
                subtitle: '자동 백업 사용 안함',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
            ],
          ),
          
          const SizedBox(height: 24),
          
          _buildSettingsGroup(
            title: '개인정보',
            items: [
              SettingsItem(
                icon: Icons.security_rounded,
                title: '권한 관리',
                subtitle: '앱 권한 설정',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
              SettingsItem(
                icon: Icons.privacy_tip_rounded,
                title: '개인정보 처리방침',
                subtitle: '',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
            ],
          ),
          
          const SizedBox(height: 24),
          
          _buildSettingsGroup(
            title: '정보',
            items: [
              SettingsItem(
                icon: Icons.info_rounded,
                title: '앱 정보',
                subtitle: 'oneShot v1.0.0',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {
                  _showAppInfo();
                },
              ),
              SettingsItem(
                icon: Icons.bug_report_rounded,
                title: '문제 신고',
                subtitle: '버그 리포트 및 피드백',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
              SettingsItem(
                icon: Icons.star_rounded,
                title: '앱 평가',
                subtitle: 'Play Store에서 평가하기',
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {},
              ),
            ],
          ),
          
          const SizedBox(height: 100), // 하단 여백
        ],
      ),
    );
  }

  Widget _buildSettingsGroup({
    required String title,
    required List<SettingsItem> items,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 12),
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2D2D2D),
            ),
          ),
        ),
        
        Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.grey.shade100),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withAlpha(12),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            children: [
              for (int i = 0; i < items.length; i++) ...[
                _buildSettingsItem(items[i]),
                if (i < items.length - 1) const Divider(height: 1, indent: 60),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSettingsItem(SettingsItem item) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: const Color(0xFF6C63FF).withAlpha(40),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(
          item.icon,
          size: 20,
          color: const Color(0xFF6C63FF),
        ),
      ),
      title: Text(
        item.title,
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w500,
          color: Color(0xFF2D2D2D),
        ),
      ),
      subtitle: item.subtitle.isNotEmpty
          ? Text(
              item.subtitle,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[600],
              ),
            )
          : null,
      trailing: item.trailing,
      onTap: () {
        HapticFeedback.lightImpact();
        item.onTap();
      },
    );
  }

  void _showAppInfo() {
    // 앱 정보 다이얼로그 표시 (구현 예정)
  }
}

class SettingsItem {
  final IconData icon;
  final String title;
  final String subtitle;
  final Widget? trailing;
  final VoidCallback onTap;

  SettingsItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.trailing,
    required this.onTap,
  });
}