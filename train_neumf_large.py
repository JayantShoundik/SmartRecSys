import os
import random
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from generate_large_scale_interactions import generate_large_scale_dataset

# ==========================================
# Reproducibility & Device Configuration
# ==========================================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

if torch.cuda.is_available():
    device = torch.device("cuda")
    print("🚀 NVIDIA GPU detected! Accelerating via CUDA.")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
    print("🚀 Apple Silicon GPU detected! Accelerating via Metal Performance Shaders (MPS).")
else:
    device = torch.device("cpu")
    print("💻 Training on CPU.")

# ==========================================
# 1. Dataset & Negative Sampling Engine
# ==========================================

class LargeScaleInteractionDataset(Dataset):
    def __init__(self, user_item_pairs, labels):
        self.users = torch.tensor([u for u, _ in user_item_pairs], dtype=torch.long)
        self.items = torch.tensor([i for _, i in user_item_pairs], dtype=torch.long)
        self.labels = torch.tensor(labels, dtype=torch.float32)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.users[idx], self.items[idx], self.labels[idx]

def prepare_data_and_splits(interactions_df, num_items, num_negatives=4):
    """
    Implements Leave-One-Out (LOO) protocol:
      - 1 positive interaction per user is reserved for testing.
      - Remaining positive interactions + 4:1 negative samples are used for training.
      - For evaluation, each test positive item is ranked against 99 unseen negative items.
    """
    print("\nPreparing Leave-One-Out (LOO) training and testing splits...")
    user_to_items = {}
    for _, row in interactions_df.iterrows():
        u = int(row['user_id'])
        i = int(row['course_index'])
        if u not in user_to_items:
            user_to_items[u] = []
        user_to_items[u].append(i)

    train_pairs = []
    train_labels = []
    test_data = {}  # user_id -> (pos_item, [99 neg_items])

    for user_id, items in user_to_items.items():
        if len(items) < 2:
            continue
        # Reserve last positive interaction for test
        pos_test_item = items[-1]
        train_pos_items = items[:-1]

        # Add training positive samples
        for item in train_pos_items:
            train_pairs.append((user_id, item))
            train_labels.append(1.0)

            # Sample negatives for training
            for _ in range(num_negatives):
                neg_item = np.random.randint(0, num_items)
                while neg_item in user_to_items[user_id]:
                    neg_item = np.random.randint(0, num_items)
                train_pairs.append((user_id, neg_item))
                train_labels.append(0.0)

        # Sample 99 negatives for test evaluation
        user_negatives = []
        while len(user_negatives) < 99:
            neg_item = np.random.randint(0, num_items)
            if neg_item not in user_to_items[user_id] and neg_item not in user_negatives:
                user_negatives.append(neg_item)

        test_data[user_id] = (pos_test_item, user_negatives)

    train_dataset = LargeScaleInteractionDataset(train_pairs, train_labels)
    print(f"✅ Training samples: {len(train_dataset):,} (Positives + 4x Negatives)")
    print(f"✅ Evaluated test users: {len(test_data):,} (1 positive vs 99 negatives per student)")
    return train_dataset, test_data

# ==========================================
# 2. Neural Matrix Factorization (NeuMF) Architecture
# ==========================================

class NeuralMatrixFactorization(nn.Module):
    """
    NeuMF: State-of-the-Art Neural Recommender Architecture
    Combines Generalized Matrix Factorization (GMF) + Deep Multi-Layer Perceptron (MLP)
    """
    def __init__(self, num_users, num_items, latent_dim_gmf=32, latent_dim_mlp=32):
        super(NeuralMatrixFactorization, self).__init__()

        # --- GMF Branch ---
        self.user_embed_gmf = nn.Embedding(num_users, latent_dim_gmf)
        self.item_embed_gmf = nn.Embedding(num_items, latent_dim_gmf)

        # --- MLP Branch ---
        self.user_embed_mlp = nn.Embedding(num_users, latent_dim_mlp)
        self.item_embed_mlp = nn.Embedding(num_items, latent_dim_mlp)

        self.mlp = nn.Sequential(
            nn.Linear(latent_dim_mlp * 2, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(64, 32),
            nn.ReLU(),

            nn.Linear(32, 16),
            nn.ReLU()
        )

        # --- Prediction Fusion Layer ---
        self.predict_layer = nn.Linear(latent_dim_gmf + 16, 1)
        self.sigmoid = nn.Sigmoid()

        self._init_weights()

    def _init_weights(self):
        # Xavier Normal initialization for embeddings and linear layers
        for m in self.modules():
            if isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, std=0.01)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, user_indices, item_indices):
        # 1. GMF Branch (Element-wise dot product)
        user_gmf = self.user_embed_gmf(user_indices)
        item_gmf = self.item_embed_gmf(item_indices)
        gmf_out = user_gmf * item_gmf

        # 2. MLP Branch (Concatenation + Non-linear Deep Layers)
        user_mlp = self.user_embed_mlp(user_indices)
        item_mlp = self.item_embed_mlp(item_indices)
        mlp_in = torch.cat([user_mlp, item_mlp], dim=-1)
        mlp_out = self.mlp(mlp_in)

        # 3. Fusion & Sigmoid probability output
        fusion = torch.cat([gmf_out, mlp_out], dim=-1)
        logits = self.predict_layer(fusion).squeeze(-1)
        return self.sigmoid(logits)

# ==========================================
# 3. Academic Evaluation Engine (HR@K, NDCG@K, MRR)
# ==========================================

def evaluate_model(model, test_data, sample_users=2000):
    """
    Evaluates Hit Ratio (HR@K), NDCG@K, and Mean Reciprocal Rank (MRR)
    across test users against 99 negative candidates.
    """
    model.eval()
    hr_5, hr_10, ndcg_5, ndcg_10, mrr = [], [], [], [], []

    eval_users = list(test_data.keys())
    if len(eval_users) > sample_users:
        eval_users = random.sample(eval_users, sample_users)

    with torch.no_grad():
        for u in eval_users:
            pos_item, neg_items = test_data[u]
            candidate_items = [pos_item] + neg_items  # 100 items total
            
            user_tensor = torch.full((len(candidate_items),), u, dtype=torch.long, device=device)
            item_tensor = torch.tensor(candidate_items, dtype=torch.long, device=device)

            scores = model(user_tensor, item_tensor).cpu().numpy()
            
            # Ground truth index is 0 (the first element)
            ranked_indices = np.argsort(scores)[::-1]
            rank_of_positive = np.where(ranked_indices == 0)[0][0] + 1  # 1-based rank

            # HR@K
            hr_5.append(1.0 if rank_of_positive <= 5 else 0.0)
            hr_10.append(1.0 if rank_of_positive <= 10 else 0.0)

            # NDCG@K
            ndcg_5.append(1.0 / np.log2(rank_of_positive + 1) if rank_of_positive <= 5 else 0.0)
            ndcg_10.append(1.0 / np.log2(rank_of_positive + 1) if rank_of_positive <= 10 else 0.0)

            # MRR
            mrr.append(1.0 / rank_of_positive)

    return {
        'HR@5': np.mean(hr_5),
        'HR@10': np.mean(hr_10),
        'NDCG@5': np.mean(ndcg_5),
        'NDCG@10': np.mean(ndcg_10),
        'MRR': np.mean(mrr)
    }

# ==========================================
# 4. Training Orchestrator
# ==========================================

def train_large_scale_neumf(
    num_users=25000,
    epochs=12,
    batch_size=1024,
    lr=0.0015
):
    dataset_file = "dataset/large_campus_interactions.csv"
    if not os.path.exists(dataset_file):
        interactions_df = generate_large_scale_dataset(num_users=num_users)
    else:
        print(f"Loading existing interaction dataset from {dataset_file}...")
        interactions_df = pd.read_csv(dataset_file)

    courses_df = pd.read_csv("dataset/udemy_courses.csv")
    num_items = len(courses_df)
    actual_users = interactions_df['user_id'].nunique()

    train_dataset, test_data = prepare_data_and_splits(interactions_df, num_items)
    dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    model = NeuralMatrixFactorization(num_users=actual_users, num_items=num_items, latent_dim_gmf=32, latent_dim_mlp=32)
    model = model.to(device)

    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    print("\n" + "=" * 65)
    print(f"Training NeuMF Model on {actual_users:,} Students for {epochs} Epochs...")
    print(f"Device: {device} | Batch Size: {batch_size} | Latent Dims: 32 GMF + 32 MLP")
    print("=" * 65)

    history = {'epoch': [], 'loss': [], 'HR@10': [], 'NDCG@10': []}

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        
        for users_b, items_b, labels_b in dataloader:
            users_b = users_b.to(device)
            items_b = items_b.to(device)
            labels_b = labels_b.to(device)

            optimizer.zero_grad()
            predictions = model(users_b, items_b)
            loss = criterion(predictions, labels_b)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(labels_b)

        scheduler.step()
        avg_loss = total_loss / len(train_dataset)

        # Intermediate evaluation every 2 epochs
        if epoch % 2 == 0 or epoch == epochs:
            metrics = evaluate_model(model, test_data, sample_users=2000)
            print(f"Epoch {epoch:02d}/{epochs:02d} | Loss: {avg_loss:.4f} | HR@10: {metrics['HR@10']*100:.2f}% | NDCG@10: {metrics['NDCG@10']:.4f} | MRR: {metrics['MRR']:.4f}")
            history['epoch'].append(epoch)
            history['loss'].append(avg_loss)
            history['HR@10'].append(metrics['HR@10'])
            history['NDCG@10'].append(metrics['NDCG@10'])
        else:
            print(f"Epoch {epoch:02d}/{epochs:02d} | Loss: {avg_loss:.4f}")

    total_training_time = time.time() - start_time
    print(f"\n✨ Training Complete in {total_training_time:.2f} seconds ({total_training_time/60:.2f} mins)!")

    # Final Comprehensive Evaluation
    print("\n" + "=" * 65)
    print("FINAL BENCHMARK EVALUATION (Leave-One-Out against 99 Negatives)")
    print("=" * 65)
    final_metrics = evaluate_model(model, test_data, sample_users=len(test_data))
    for metric_name, val in final_metrics.items():
        if 'HR' in metric_name:
            print(f"  🎯 {metric_name:<10}: {val*100:.2f}%")
        else:
            print(f"  📊 {metric_name:<10}: {val:.4f}")

    # Save Model Weights
    os.makedirs("models", exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'num_users': actual_users,
        'num_items': num_items,
        'latent_dim_gmf': 32,
        'latent_dim_mlp': 32,
        'metrics': final_metrics
    }, "models/neumf_large.pth")
    print("\n💾 Model weights saved to 'models/neumf_large.pth'.")

    # Generate Visualization Plot
    plot_benchmark_results(final_metrics)

def plot_benchmark_results(metrics):
    os.makedirs("plots", exist_ok=True)
    plt.figure(figsize=(10, 6))

    labels = ['Hit Ratio@5', 'Hit Ratio@10', 'NDCG@5', 'NDCG@10', 'MRR']
    values = [metrics['HR@5'] * 100, metrics['HR@10'] * 100, metrics['NDCG@5'] * 100, metrics['NDCG@10'] * 100, metrics['MRR'] * 100]
    colors = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ec4899']

    bars = plt.bar(labels, values, color=colors, width=0.55, edgecolor='black', linewidth=1.2)
    plt.title("Large-Scale Smart Campus NeuMF Model Performance\n(25,000 Students, Leave-One-Out vs 99 Negatives)", fontsize=13, fontweight='bold', pad=15)
    plt.ylabel("Score (%)", fontsize=12)
    plt.ylim(0, 105)
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 1.5,
                 f'{height:.1f}%',
                 ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.tight_layout()
    output_plot = "plots/large_scale_evaluation.png"
    plt.savefig(output_plot, dpi=150)
    plt.close()
    print(f"📊 Benchmark evaluation plot saved to '{output_plot}'.")

if __name__ == "__main__":
    train_large_scale_neumf()
