#!/usr/bin/env python3
"""
Fine-tuning script for DINOv2-S/14 with GeM pooling and MLP projection head
for duplicate photo detection using retrieval losses.
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import timm
from transformers import AutoImageProcessor, AutoModel
from tqdm import tqdm
import json
from sklearn.metrics import roc_auc_score, average_precision_score


class GeM(nn.Module):
    """Generalized Mean (GeM) pooling layer."""
    
    def __init__(self, p: float = 3.0, eps: float = 1e-6, learnable: bool = True):
        super().__init__()
        self.p = nn.Parameter(torch.ones(1) * p) if learnable else p
        self.eps = eps
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input tensor of shape (B, C, H, W)
        Returns:
            Pooled tensor of shape (B, C)
        """
        return x.clamp(min=self.eps).pow(self.p).mean(dim=(2, 3)).pow(1.0 / self.p)


class DINOv2RetrievalModel(nn.Module):
    """DINOv2 model with GeM pooling and MLP projection for retrieval."""
    
    def __init__(self, model_name: str = "facebook/dinov2-small",
                 embedding_dim: int = 128, hidden_dim: int = 512,
                 p_gem: float = 2.0, freeze_backbone: bool = False):
        super().__init__()
        
        # Load DINOv2 backbone
        self.backbone = AutoModel.from_pretrained(model_name)
        self.feature_dim = self.backbone.config.hidden_size
        
        # Freeze backbone if specified
        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False
        
        # GeM pooling
        self.gem = GeM(p=p_gem, learnable=True)
        
        # MLP projection head
        self.projection = nn.Sequential(
            nn.Linear(self.feature_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, embedding_dim)
        )
        
        # L2 normalization is applied in forward pass
    
    def forward(self, x: torch.Tensor, return_features: bool = False) -> torch.Tensor:
        """
        Args:
            x: Input images of shape (B, 3, H, W)
            return_features: If True, return intermediate features
        Returns:
            Normalized embeddings of shape (B, embedding_dim)
        """
        # Get patch embeddings from DINOv2
        outputs = self.backbone(x)
        
        # Get the patch tokens (excluding CLS token)
        patch_tokens = outputs.last_hidden_state[:, 1:, :]  # (B, N_patches, D)
        
        # Reshape to (B, D, H, W) for GeM pooling
        B, N, D = patch_tokens.shape
        H = W = int(np.sqrt(N))  # Assuming square patches
        patch_tokens = patch_tokens.transpose(1, 2).reshape(B, D, H, W)
        
        # Apply GeM pooling
        pooled = self.gem(patch_tokens)  # (B, D)
        
        # Project to embedding space
        embeddings = self.projection(pooled)
        
        # L2 normalize
        embeddings = F.normalize(embeddings, p=2, dim=1)
        
        if return_features:
            return embeddings, pooled
        return embeddings


class PhotoPairDataset(Dataset):
    """Dataset for photo pairs with labels."""
    
    def __init__(self, csv_path: str, transform=None, mode: str = 'train'):
        self.df = pd.read_csv(csv_path)
        self.transform = transform
        self.mode = mode
        
        # Map labels to numeric values
        self.label_map = {
            'positive': 1,
            'hard_negative': 0,
            'strong_negative': 0
        }
    
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # Load images
        img_a = Image.open(row['image_a']).convert('RGB')
        img_b = Image.open(row['image_b']).convert('RGB')
        
        # Apply transforms
        if self.transform:
            img_a = self.transform(img_a)
            img_b = self.transform(img_b)
        
        # Get label
        label = self.label_map[row['label']]
        is_hard = 1 if row['label'] == 'hard_negative' else 0
        
        return {
            'image_a': img_a,
            'image_b': img_b,
            'label': label,
            'is_hard': is_hard
        }


class InfoNCELoss(nn.Module):
    """InfoNCE contrastive loss for retrieval."""
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(self, embeddings_a: torch.Tensor, embeddings_b: torch.Tensor,
                labels: torch.Tensor) -> torch.Tensor:
        """
        Args:
            embeddings_a: Embeddings of first images (B, D)
            embeddings_b: Embeddings of second images (B, D)
            labels: Binary labels (B,) where 1 = positive pair
        """
        batch_size = embeddings_a.shape[0]
        
        # Compute similarity matrix
        sim_matrix = torch.matmul(embeddings_a, embeddings_b.T) / self.temperature
        
        # Create mask for positive pairs
        pos_mask = labels.unsqueeze(0) * labels.unsqueeze(1)
        pos_mask.fill_diagonal_(0)  # Exclude self-similarity
        
        # Compute loss
        exp_sim = torch.exp(sim_matrix)
        pos_sim = torch.sum(exp_sim * pos_mask, dim=1)
        all_sim = torch.sum(exp_sim, dim=1) - torch.diag(exp_sim)
        
        loss = -torch.log(pos_sim / (all_sim + 1e-8) + 1e-8)
        return loss.mean()


class TripletLoss(nn.Module):
    """Triplet margin loss with online hard negative mining."""
    
    def __init__(self, margin: float = 0.3):
        super().__init__()
        self.margin = margin
    
    def forward(self, embeddings_a: torch.Tensor, embeddings_b: torch.Tensor,
                labels: torch.Tensor, is_hard: torch.Tensor) -> torch.Tensor:
        """
        Args:
            embeddings_a: Embeddings of first images (B, D)
            embeddings_b: Embeddings of second images (B, D)
            labels: Binary labels (B,) where 1 = positive pair
            is_hard: Binary mask (B,) where 1 = hard negative
        """
        batch_size = embeddings_a.shape[0]
        
        # Compute pairwise distances
        distances = 1 - F.cosine_similarity(embeddings_a, embeddings_b)
        
        # Separate positive and negative distances
        pos_mask = labels.bool()
        neg_mask = ~pos_mask
        
        if pos_mask.sum() == 0 or neg_mask.sum() == 0:
            return torch.tensor(0.0, device=embeddings_a.device)
        
        pos_distances = distances[pos_mask]
        neg_distances = distances[neg_mask]
        
        # Online hard negative mining
        hard_neg_mask = is_hard[neg_mask].bool()
        if hard_neg_mask.sum() > 0:
            # Prioritize hard negatives
            hard_neg_distances = neg_distances[hard_neg_mask]
            hardest_negative = hard_neg_distances.min()
        else:
            hardest_negative = neg_distances.min()
        
        # Compute triplet loss for each positive
        losses = []
        for pos_dist in pos_distances:
            loss = torch.clamp(pos_dist - hardest_negative + self.margin, min=0)
            losses.append(loss)
        
        return torch.stack(losses).mean() if losses else torch.tensor(0.0)


class CombinedLoss(nn.Module):
    """Combined InfoNCE and Triplet loss."""
    
    def __init__(self, temperature: float = 0.07, margin: float = 0.3,
                 alpha: float = 0.5):
        super().__init__()
        self.infonce = InfoNCELoss(temperature)
        self.triplet = TripletLoss(margin)
        self.alpha = alpha
    
    def forward(self, embeddings_a: torch.Tensor, embeddings_b: torch.Tensor,
                labels: torch.Tensor, is_hard: torch.Tensor) -> Dict[str, torch.Tensor]:
        infonce_loss = self.infonce(embeddings_a, embeddings_b, labels)
        triplet_loss = self.triplet(embeddings_a, embeddings_b, labels, is_hard)
        
        total_loss = self.alpha * infonce_loss + (1 - self.alpha) * triplet_loss
        
        return {
            'loss': total_loss,
            'infonce_loss': infonce_loss,
            'triplet_loss': triplet_loss
        }


class Trainer:
    """Training loop for DINOv2 retrieval model."""
    
    def __init__(self, model: nn.Module, train_loader: DataLoader,
                 val_loader: Optional[DataLoader] = None,
                 lr: float = 1e-4, weight_decay: float = 1e-4,
                 device: str = 'cuda', checkpoint_dir: str = './checkpoints'):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True, parents=True)
        
        # Optimizer
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=lr, weight_decay=weight_decay
        )
        
        # Learning rate scheduler
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=len(train_loader) * 10  # 10 epochs
        )
        
        # Loss function
        self.criterion = CombinedLoss()
        
        # Metrics tracking
        self.train_metrics = []
        self.val_metrics = []
    
    def train_epoch(self, epoch: int) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        
        total_loss = 0
        total_infonce = 0
        total_triplet = 0
        
        pbar = tqdm(self.train_loader, desc=f'Epoch {epoch}')
        for batch in pbar:
            # Move to device
            img_a = batch['image_a'].to(self.device)
            img_b = batch['image_b'].to(self.device)
            labels = batch['label'].to(self.device)
            is_hard = batch['is_hard'].to(self.device)
            
            # Forward pass
            emb_a = self.model(img_a)
            emb_b = self.model(img_b)
            
            # Compute loss
            loss_dict = self.criterion(emb_a, emb_b, labels, is_hard)
            loss = loss_dict['loss']
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            self.scheduler.step()
            
            # Update metrics
            total_loss += loss.item()
            total_infonce += loss_dict['infonce_loss'].item()
            total_triplet += loss_dict['triplet_loss'].item()
            
            pbar.set_postfix({
                'loss': loss.item(),
                'lr': self.scheduler.get_last_lr()[0]
            })
        
        metrics = {
            'loss': total_loss / len(self.train_loader),
            'infonce_loss': total_infonce / len(self.train_loader),
            'triplet_loss': total_triplet / len(self.train_loader)
        }
        
        return metrics
    
    @torch.no_grad()
    def validate(self, epoch: int) -> Dict[str, float]:
        """Validate the model."""
        if self.val_loader is None:
            return {}
        
        self.model.eval()
        
        all_distances = []
        all_labels = []
        
        for batch in tqdm(self.val_loader, desc='Validation'):
            # Move to device
            img_a = batch['image_a'].to(self.device)
            img_b = batch['image_b'].to(self.device)
            labels = batch['label']
            
            # Forward pass
            emb_a = self.model(img_a)
            emb_b = self.model(img_b)
            
            # Compute distances
            distances = F.cosine_similarity(emb_a, emb_b).cpu().numpy()
            
            all_distances.extend(distances)
            all_labels.extend(labels.numpy())
        
        all_distances = np.array(all_distances)
        all_labels = np.array(all_labels)
        
        # Compute metrics
        auc = roc_auc_score(all_labels, all_distances)
        ap = average_precision_score(all_labels, all_distances)
        
        # Find optimal threshold
        thresholds = np.linspace(0, 1, 100)
        best_f1 = 0
        best_threshold = 0
        
        for threshold in thresholds:
            predictions = (all_distances > threshold).astype(int)
            tp = np.sum((predictions == 1) & (all_labels == 1))
            fp = np.sum((predictions == 1) & (all_labels == 0))
            fn = np.sum((predictions == 0) & (all_labels == 1))
            
            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + fn + 1e-8)
            f1 = 2 * precision * recall / (precision + recall + 1e-8)
            
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
        
        metrics = {
            'auc': auc,
            'ap': ap,
            'best_f1': best_f1,
            'best_threshold': best_threshold
        }
        
        return metrics
    
    def train(self, num_epochs: int):
        """Full training loop."""
        best_val_metric = 0
        
        for epoch in range(1, num_epochs + 1):
            print(f"\n{'='*50}")
            print(f"Epoch {epoch}/{num_epochs}")
            print(f"{'='*50}")
            
            # Train
            train_metrics = self.train_epoch(epoch)
            self.train_metrics.append(train_metrics)
            print(f"Train metrics: {train_metrics}")
            
            # Validate
            val_metrics = self.validate(epoch)
            if val_metrics:
                self.val_metrics.append(val_metrics)
                print(f"Val metrics: {val_metrics}")
                
                # Save best model
                if val_metrics['auc'] > best_val_metric:
                    best_val_metric = val_metrics['auc']
                    self.save_checkpoint(epoch, val_metrics, is_best=True)
            
            # Save regular checkpoint
            if epoch % 5 == 0:
                self.save_checkpoint(epoch, val_metrics)
        
        # Save training history
        history = {
            'train': self.train_metrics,
            'val': self.val_metrics
        }
        with open(self.checkpoint_dir / 'training_history.json', 'w') as f:
            json.dump(history, f, indent=2)
    
    def save_checkpoint(self, epoch: int, val_metrics: Dict, is_best: bool = False):
        """Save model checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'val_metrics': val_metrics
        }
        
        if is_best:
            path = self.checkpoint_dir / 'best_model.pth'
        else:
            path = self.checkpoint_dir / f'checkpoint_epoch_{epoch}.pth'
        
        torch.save(checkpoint, path)
        print(f"Saved checkpoint to {path}")


def create_data_transforms(image_size: int = 224, mode: str = 'train'):
    """Create data augmentation transforms."""
    from torchvision import transforms
    
    if mode == 'train':
        transform = transforms.Compose([
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1, hue=0.05),
            transforms.RandomGrayscale(p=0.1),
            transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 2.0)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
    else:
        transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
    
    return transform


def main():
    """Main training function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fine-tune DINOv2 for duplicate detection')
    parser.add_argument('--train_csv', type=str, required=True,
                       help='Path to training pairs CSV')
    parser.add_argument('--val_csv', type=str, default=None,
                       help='Path to validation pairs CSV')
    parser.add_argument('--model_name', type=str, default='facebook/dinov2-small',
                       help='DINOv2 model name')
    parser.add_argument('--embedding_dim', type=int, default=128,
                       help='Output embedding dimension')
    parser.add_argument('--batch_size', type=int, default=32,
                       help='Batch size')
    parser.add_argument('--num_epochs', type=int, default=20,
                       help='Number of training epochs')
    parser.add_argument('--lr', type=float, default=1e-4,
                       help='Learning rate')
    parser.add_argument('--freeze_backbone', action='store_true',
                       help='Freeze DINOv2 backbone')
    parser.add_argument('--checkpoint_dir', type=str, default='./checkpoints',
                       help='Directory to save checkpoints')
    parser.add_argument('--num_workers', type=int, default=4,
                       help='Number of data loader workers')
    
    args = parser.parse_args()
    
    # Set device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    # Create data loaders
    train_transform = create_data_transforms(mode='train')
    val_transform = create_data_transforms(mode='val')
    
    train_dataset = PhotoPairDataset(args.train_csv, transform=train_transform, mode='train')
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=True
    )
    
    val_loader = None
    if args.val_csv:
        val_dataset = PhotoPairDataset(args.val_csv, transform=val_transform, mode='val')
        val_loader = DataLoader(
            val_dataset, batch_size=args.batch_size, shuffle=False,
            num_workers=args.num_workers, pin_memory=True
        )
    
    # Create model
    model = DINOv2RetrievalModel(
        model_name=args.model_name,
        embedding_dim=args.embedding_dim,
        freeze_backbone=args.freeze_backbone
    )
    
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
    
    # Create trainer
    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        lr=args.lr,
        device=device,
        checkpoint_dir=args.checkpoint_dir
    )
    
    # Train
    trainer.train(args.num_epochs)


if __name__ == '__main__':
    main()