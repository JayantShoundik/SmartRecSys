import os
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

# Set random seeds for reproducibility
random.seed(42)
np.random.seed(42)
torch.manual_seed(42)

# ==========================================
# GPU/MPS Acceleration Setup
# ==========================================
if torch.cuda.is_available():
    device = torch.device("cuda")
    print("🚀 NVIDIA GPU detected! Training will be accelerated via CUDA.")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
    print("🚀 Apple Silicon GPU detected! Training will be accelerated via Metal (MPS).")
else:
    device = torch.device("cpu")
    print("💻 No GPU detected. Training will run on the CPU.")

# ==========================================
# 1. Dataset & Synthetic Interaction Setup
# ==========================================

class CourseInteractionDataset(Dataset):
    def __init__(self, df, num_users=1000):
        self.df = df
        self.num_users = num_users
        self.num_items = len(df)
        self.interactions = []
        self.generate_synthetic_interactions()

    def generate_synthetic_interactions(self):
        subjects = self.df['subject'].unique()
        subject_to_indices = {sub: self.df[self.df['subject'] == sub].index.tolist() for sub in subjects}
        
        user_positive_items = {}
        
        for user_id in range(self.num_users):
            pref_subject = np.random.choice(subjects)
            pref_indices = subject_to_indices[pref_subject]
            
            num_enrollments = np.random.randint(3, 11)
            if len(pref_indices) >= num_enrollments:
                enrolled = np.random.choice(pref_indices, size=num_enrollments, replace=False)
            else:
                enrolled = pref_indices
                
            user_positive_items[user_id] = set(enrolled)
            
            # Positive samples (label = 1)
            for item_id in enrolled:
                self.interactions.append((user_id, item_id, 1.0))
                
            # Negative samples (ratio 4:1)
            num_negatives = len(enrolled) * 4
            negatives = []
            while len(negatives) < num_negatives:
                neg_item = np.random.randint(0, self.num_items)
                if neg_item not in user_positive_items[user_id]:
                    negatives.append(neg_item)
            
            for item_id in negatives:
                self.interactions.append((user_id, item_id, 0.0))

    def __len__(self):
        return len(self.interactions)

    def __getitem__(self, idx):
        user, item, label = self.interactions[idx]
        return torch.tensor(user, dtype=torch.long), torch.tensor(item, dtype=torch.long), torch.tensor(label, dtype=torch.float32)

# ==========================================
# 2. Neural Collaborative Filtering (NCF) Model
# ==========================================

class NeuralCollaborativeFiltering(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=16):
        super(NeuralCollaborativeFiltering, self).__init__()
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        
        # Multi-Layer Perceptron (MLP) layers
        self.mlp = nn.Sequential(
            nn.Linear(embedding_dim * 2, 64),  # Scaled up for GPU training
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )

    def forward(self, user_indices, item_indices):
        user_embed = self.user_embedding(user_indices)
        item_embed = self.item_embedding(item_indices)
        x = torch.cat([user_embed, item_embed], dim=-1)
        prediction = self.mlp(x).squeeze(-1)
        return prediction

# ==========================================
# 3. Model Training & Prediction Helper
# ==========================================

def train_ncf_model():
    dataset_path = "dataset/udemy_courses.csv"
    if not os.path.exists(dataset_path):
        print(f"Error: {dataset_path} not found. Please run download_dataset.py first!")
        return
        
    df = pd.read_csv(dataset_path)
    print(f"Loaded {len(df)} courses from dataset.")
    
    print("Generating simulated user-course interaction dataset...")
    num_users = 1000
    dataset = CourseInteractionDataset(df, num_users=num_users)
    dataloader = DataLoader(dataset, batch_size=512, shuffle=True)  # Larger batch size for GPU efficiency
    
    # Initialize Model and move to device (GPU/MPS/CPU)
    model = NeuralCollaborativeFiltering(num_users=num_users, num_items=dataset.num_items, embedding_dim=16)
    model = model.to(device)
    
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    epochs = 15  # Increased epochs for better training
    print(f"\nTraining Deep Learning NCF Model on {device} for {epochs} epochs...")
    
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for users, items, labels in dataloader:
            # Move batch data to the designated device
            users, items, labels = users.to(device), items.to(device), labels.to(device)
            
            optimizer.zero_grad()
            predictions = model(users, items)
            loss = criterion(predictions, labels)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * users.size(0)
            
        avg_loss = epoch_loss / len(dataset)
        print(f"Epoch {epoch+1:02d}/{epochs:02d} | Avg Loss: {avg_loss:.4f}")
        
    # Save Model Weights
    os.makedirs("models", exist_ok=True)
    torch.save(model.state_dict(), "models/ncf_recommender.pth")
    print("\nNCF Model trained and weights saved to 'models/ncf_recommender.pth'.")
    
    # Run Demo Recommendation
    recommend_for_sample_user(model, df, dataset)

def recommend_for_sample_user(model, df, dataset, user_id=42, top_k=5):
    model.eval()
    print(f"\nGenerating recommendations for Simulated User {user_id} using trained NCF Model:")
    
    num_items = dataset.num_items
    
    # Move inference tensors to device
    user_tensor = torch.tensor([user_id] * num_items, dtype=torch.long).to(device)
    item_tensor = torch.arange(num_items, dtype=torch.long).to(device)
    
    with torch.no_grad():
        # Retrieve scores back to CPU for pandas display
        scores = model(user_tensor, item_tensor).cpu().numpy()
        
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    print("-" * 75)
    print(f"{'Rank':<5} | {'Course Title':<45} | {'Subject':<18} | {'DL Probability':<12}")
    print("-" * 75)
    for i, idx in enumerate(top_indices, 1):
        row = df.iloc[idx]
        print(f"{i:<5} | {row['course_title'][:45]:<45} | {row['subject']:<18} | {scores[idx]:.4f}")
    print("-" * 75)

if __name__ == "__main__":
    train_ncf_model()
