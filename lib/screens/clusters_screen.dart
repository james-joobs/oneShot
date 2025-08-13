import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/photo_processing_provider.dart';
import '../widgets/cluster_view.dart';

class ClustersScreen extends StatelessWidget {
  const ClustersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<PhotoProcessingProvider>(
      builder: (context, provider, child) {
        if (!provider.hasResult) {
          return const Center(
            child: Text(
              '먼저 사진 분석을 진행해주세요',
              style: TextStyle(fontSize: 16, color: Colors.grey),
            ),
          );
        }

        final clusters = provider.result!.clusters
            .where((cluster) => cluster.photos.length > 1)
            .toList();

        if (clusters.isEmpty) {
          return const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.check_circle, size: 64, color: Colors.green),
                SizedBox(height: 16),
                Text(
                  '중복된 사진이 없습니다!',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                SizedBox(height: 8),
                Text(
                  '모든 사진이 고유합니다',
                  style: TextStyle(fontSize: 14, color: Colors.grey),
                ),
              ],
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: clusters.length,
          itemBuilder: (context, index) {
            return ClusterView(
              cluster: clusters[index],
              index: index + 1,
            );
          },
        );
      },
    );
  }
}