import numpy as np
from typing import List, Tuple

class SimilarityCalculator:
    def __init__(self, similarity_threshold=0.85):
        self.similarity_threshold = similarity_threshold
    
    def cosine_similarity(self, embedding1, embedding2):
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def compute_similarity_matrix(self, embeddings):
        n = len(embeddings)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    similarity_matrix[i][j] = 1.0
                else:
                    sim = self.cosine_similarity(embeddings[i], embeddings[j])
                    similarity_matrix[i][j] = sim
                    similarity_matrix[j][i] = sim
        
        return similarity_matrix
    
    def find_duplicate_pairs(self, embeddings, image_paths):
        similarity_matrix = self.compute_similarity_matrix(embeddings)
        duplicate_pairs = []
        
        n = len(embeddings)
        for i in range(n):
            for j in range(i + 1, n):
                if similarity_matrix[i][j] > self.similarity_threshold:
                    duplicate_pairs.append({
                        'image1': image_paths[i],
                        'image2': image_paths[j],
                        'similarity': similarity_matrix[i][j],
                        'index1': i,
                        'index2': j
                    })
        
        return duplicate_pairs, similarity_matrix
    
    def greedy_clustering(self, embeddings, image_paths):
        similarity_matrix = self.compute_similarity_matrix(embeddings)
        n = len(embeddings)
        visited = [False] * n
        clusters = []
        
        for i in range(n):
            if not visited[i]:
                cluster = [i]
                visited[i] = True
                
                for j in range(i + 1, n):
                    if not visited[j] and similarity_matrix[i][j] > self.similarity_threshold:
                        cluster.append(j)
                        visited[j] = True
                
                cluster_paths = [image_paths[idx] for idx in cluster]
                clusters.append({
                    'indices': cluster,
                    'paths': cluster_paths,
                    'representative': image_paths[cluster[0]]
                })
        
        return clusters