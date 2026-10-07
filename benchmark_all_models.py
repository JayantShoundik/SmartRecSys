import os
import random
import time
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from sentence_transformers import SentenceTransformer

# ----------------------------------------------------
# 1. Reproducibility & Device Setup
# ----------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

device = torch.device("mps") if torch.backends.mps.is_available() else (
    torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
)
print(f"🚀 Benchmarking Device: {device}")

# ----------------------------------------------------
# 2. NeuMF Model Definition (PyTorch)
# ----------------------------------------------------
class NeuMFNet(nn.Module):
    def __init__(self, num_users, num_items, latent_dim_gmf=16, latent_dim_mlp=16, mlp_hidden_dims=[32, 16, 8]):
        super().__init__()
        # GMF Branch
        self.user_embed_gmf = nn.Embedding(num_users, latent_dim_gmf)
        self.item_embed_gmf = nn.Embedding(num_items, latent_dim_gmf)

        # MLP Branch
        self.user_embed_mlp = nn.Embedding(num_users, latent_dim_mlp)
        self.item_embed_mlp = nn.Embedding(num_items, latent_dim_mlp)

        mlp_layers = []
        input_dim = latent_dim_mlp * 2
        for hidden in mlp_hidden_dims:
            mlp_layers.append(nn.Linear(input_dim, hidden))
            mlp_layers.append(nn.ReLU())
            mlp_layers.append(nn.Dropout(0.1))
            input_dim = hidden
        self.mlp = nn.Sequential(*mlp_layers)

        # Final NeuMF prediction layer
        final_input_dim = latent_dim_gmf + mlp_hidden_dims[-1]
        self.out_layer = nn.Linear(final_input_dim, 1)

    def forward(self, user_indices, item_indices):
        u_gmf = self.user_embed_gmf(user_indices)
        i_gmf = self.item_embed_gmf(item_indices)
        gmf_vector = u_gmf * i_gmf

        u_mlp = self.user_embed_mlp(user_indices)
        i_mlp = self.item_embed_mlp(item_indices)
        mlp_vector = self.mlp(torch.cat([u_mlp, i_mlp], dim=-1))

        combined = torch.cat([gmf_vector, mlp_vector], dim=-1)
        return torch.sigmoid(self.out_layer(combined)).squeeze(-1)

# ----------------------------------------------------
# 3. Benchmark Execution Pipeline
# ----------------------------------------------------
def run_comprehensive_benchmark():
    dataset_path = "dataset/comprehensive_campus_courses.csv"
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"{dataset_path} not found! Run build_multi_domain_dataset.py first.")

    df = pd.read_csv(dataset_path)
    num_courses = len(df)
    print(f"Loaded {num_courses} courses across {df['faculty'].nunique()} faculties.")

    # A. Precompute or Load SBERT Embeddings
    os.makedirs("models", exist_ok=True)
    sbert_emb_path = "models/sbert_course_embeddings.npy"

    texts = (df['course_title'] + " " + df['domain'] + " " + df['faculty'] + " " + df['level'] + " " + df['description'].fillna('')).tolist()

    if os.path.exists(sbert_emb_path):
        print(f"Loading cached Sentence-BERT embeddings from {sbert_emb_path}...")
        sbert_course_embeddings = np.load(sbert_emb_path)
    else:
        print("Computing 384-dim Sentence-BERT (all-MiniLM-L6-v2) embeddings...")
        sbert_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
        sbert_course_embeddings = sbert_model.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True)
        np.save(sbert_emb_path, sbert_course_embeddings)
        print(f"Saved SBERT embeddings to {sbert_emb_path}")

    # B. Compute TF-IDF Matrix (Legacy Baseline)
    print("Computing TF-IDF vector matrix...")
    tfidf_vec = TfidfVectorizer(max_features=5000, stop_words='english')
    tfidf_matrix = tfidf_vec.fit_transform(texts)

    # C. Generate Realistic Multi-Disciplinary Student Interaction Cohort
    print("Synthesizing multi-disciplinary student enrollment cohorts (MBA, M.Sc, B.Tech, Humanities)...")
    num_students = 1200
    user_course_matrix = np.zeros((num_students, num_courses), dtype=np.float32)

    domains = df['domain'].unique()
    domain_to_indices = {d: df[df['domain'] == d].index.tolist() for d in domains}

    student_metadata = []
    cohort_types = [
        {"degree": "B.Tech", "dept": "Computer Science", "primary_domains": ["Artificial Intelligence & Data Science", "Software Engineering & Computer Science", "Cybersecurity & Cloud Systems", "Web Development & Software Eng"]},
        {"degree": "MBA", "dept": "School of Business", "primary_domains": ["Strategic Management & MBA", "Corporate Finance & Investment"]},
        {"degree": "M.Sc", "dept": "Natural Sciences", "primary_domains": ["Pure & Applied Physics", "Biotechnology & Health Sciences", "Applied Mathematics & Statistics"]},
        {"degree": "BA / Design", "dept": "Design & Social Sciences", "primary_domains": ["UI/UX & Graphic Design", "Psychology & Behavioral Sciences", "Audio Arts & Music Performance"]}
    ]

    for uid in range(num_students):
        cohort = cohort_types[uid % len(cohort_types)]
        n_courses = np.random.randint(5, 12)
        target_domains = cohort['primary_domains']
        
        # Pool candidate indices
        candidate_pool = []
        for td in target_domains:
            candidate_pool.extend(domain_to_indices.get(td, []))

        # Add serendipitous electives (15% chance)
        if np.random.rand() < 0.15:
            candidate_pool.extend(np.random.choice(num_courses, size=10, replace=False))

        enrolled = np.random.choice(candidate_pool, size=min(n_courses, len(candidate_pool)), replace=False)
        user_course_matrix[uid, enrolled] = 1.0

        student_metadata.append({
            "uid": uid,
            "degree": cohort["degree"],
            "dept": cohort["dept"],
            "primary_domain": np.random.choice(target_domains),
            "enrolled": list(enrolled)
        })

    # D. Strict Train / Test Matrix Separation (Zero Data Leakage)
    print("Preparing strict Train Interaction Matrix (masking 1 held-out course per test student)...")
    train_user_course_matrix = user_course_matrix.copy()
    for s in student_metadata:
        if len(s["enrolled"]) >= 2:
            test_item = s["enrolled"][-1]
            train_user_course_matrix[s["uid"], test_item] = 0.0

    print("Fitting Truncated SVD Matrix Factorization on Train Matrix (k=16)...")
    svd = TruncatedSVD(n_components=16, random_state=SEED)
    svd_user_factors = svd.fit_transform(train_user_course_matrix)
    svd_reconstructed = svd.inverse_transform(svd_user_factors)

    print("Fitting Item-Item Collaborative Similarity on Train Matrix...")
    collab_sim = cosine_similarity(train_user_course_matrix.T)

    # Train NeuMF Model on Train Interactions
    print("Training PyTorch NeuMF Neural Recommender...")
    neumf = NeuMFNet(num_users=num_students, num_items=num_courses).to(device)
    optimizer = optim.Adam(neumf.parameters(), lr=0.005, weight_decay=1e-4)
    criterion = nn.BCELoss()

    train_u, train_i, train_y = [], [], []
    for s in student_metadata:
        enr = s["enrolled"]
        if len(enr) < 2:
            continue
        # Use strictly training items
        for item in enr[:-1]:
            train_u.append(s["uid"])
            train_i.append(item)
            train_y.append(1.0)
            # Sample 4 negative items for better contrastive learning
            for _ in range(4):
                neg = np.random.randint(num_courses)
                if train_user_course_matrix[s["uid"], neg] == 0:
                    train_u.append(s["uid"])
                    train_i.append(neg)
                    train_y.append(0.0)

    train_u_t = torch.tensor(train_u, dtype=torch.long, device=device)
    train_i_t = torch.tensor(train_i, dtype=torch.long, device=device)
    train_y_t = torch.tensor(train_y, dtype=torch.float32, device=device)

    dataset_size = len(train_u)
    batch_size = 512
    neumf.train()
    for epoch in range(8):
        perm = torch.randperm(dataset_size)
        epoch_loss = 0.0
        for b in range(0, dataset_size, batch_size):
            indices = perm[b:b+batch_size]
            u_b = train_u_t[indices]
            i_b = train_i_t[indices]
            y_b = train_y_t[indices]

            optimizer.zero_grad()
            preds = neumf(u_b, i_b)
            loss = criterion(preds, y_b)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        print(f"  NeuMF Epoch {epoch+1}/8 - Loss: {epoch_loss / (dataset_size / batch_size):.4f}")

    neumf.eval()
    torch.save(neumf.state_dict(), "models/neumf_multi_domain.pth")
    print("Saved NeuMF model to models/neumf_multi_domain.pth")

    # ----------------------------------------------------
    # 4. Rigorous Leave-One-Out (LOO) Benchmark Evaluation
    # ----------------------------------------------------
    print("\nRunning Leave-One-Out (LOO) Evaluation across all models...")
    models_to_evaluate = [
        "Content-Based (TF-IDF)",
        "Collaborative Filtering (Item-Item)",
        "Matrix Factorization (Truncated SVD)",
        "Deep Semantic (Sentence-BERT)",
        "Neural Collaborative Filtering (NeuMF)",
        "SmartRecSys (Proposed Context Deep Hybrid)"
    ]

    metrics = {m: {"HR@3": [], "HR@5": [], "HR@10": [], "NDCG@5": [], "NDCG@10": [], "MRR": [], "P@5": [], "R@5": []} for m in models_to_evaluate}

    eval_students = [s for s in student_metadata if len(s["enrolled"]) >= 3][:300]

    all_course_indices = np.arange(num_courses)

    for idx, s in enumerate(eval_students):
        uid = s["uid"]
        enrolled = s["enrolled"]
        test_item = enrolled[-1]
        train_enrolled = set(enrolled[:-1])

        # Sample 99 un-enrolled items + 1 test item = 100 candidate ranking set
        unseen = [i for i in range(num_courses) if i not in train_enrolled and i != test_item]
        negative_samples = np.random.choice(unseen, size=99, replace=False).tolist()
        candidates = [test_item] + negative_samples
        np.random.shuffle(candidates)
        ground_truth_pos = candidates.index(test_item)

        # 1. Model A: TF-IDF
        train_list = list(train_enrolled)
        tfidf_user_prof = tfidf_matrix[train_list].mean(axis=0)
        tfidf_user_prof_arr = np.asarray(tfidf_user_prof)
        scores_tfidf = cosine_similarity(tfidf_user_prof_arr, tfidf_matrix[candidates])[0]

        # 2. Model B: Collaborative Filtering (Item-Item)
        scores_collab = collab_sim[train_list][:, candidates].mean(axis=0)

        # 3. Model C: Truncated SVD
        scores_svd = svd_reconstructed[uid, candidates]

        # 4. Model D: Sentence-BERT
        sbert_user_prof = sbert_course_embeddings[train_list].mean(axis=0, keepdims=True)
        scores_sbert = cosine_similarity(sbert_user_prof, sbert_course_embeddings[candidates])[0]

        # 5. Model E: NeuMF
        u_tensor = torch.full((len(candidates),), uid, dtype=torch.long, device=device)
        i_tensor = torch.tensor(candidates, dtype=torch.long, device=device)
        with torch.no_grad():
            scores_neumf = neumf(u_tensor, i_tensor).cpu().numpy()

        # 6. Model F: Proposed Context-Aware Deep Hybrid
        # Normalized scores
        def min_max(a):
            rng = a.max() - a.min()
            return (a - a.min()) / (rng + 1e-8)

        n_sbert = min_max(scores_sbert)
        n_neumf = min_max(scores_neumf)
        n_svd = min_max(scores_svd)
        
        # Contextual Academic Gating bonus
        context_bonus = np.zeros(len(candidates))
        candidate_faculties = df.iloc[candidates]['faculty'].values
        candidate_domains = df.iloc[candidates]['domain'].values
        student_domain = s["primary_domain"]
        for c_idx in range(len(candidates)):
            if candidate_domains[c_idx] == student_domain:
                context_bonus[c_idx] += 0.35
            elif s["degree"] in str(df.iloc[candidates[c_idx]]['suitability']):
                context_bonus[c_idx] += 0.15

        scores_hybrid = (0.40 * n_sbert) + (0.30 * n_neumf) + (0.10 * n_svd) + (0.20 * context_bonus)

        all_model_scores = {
            "Content-Based (TF-IDF)": scores_tfidf,
            "Collaborative Filtering (Item-Item)": scores_collab,
            "Matrix Factorization (Truncated SVD)": scores_svd,
            "Deep Semantic (Sentence-BERT)": scores_sbert,
            "Neural Collaborative Filtering (NeuMF)": scores_neumf,
            "SmartRecSys (Proposed Context Deep Hybrid)": scores_hybrid
        }

        # Calculate Ranking Metrics
        for model_name, scr in all_model_scores.items():
            ranking = np.argsort(scr)[::-1]
            rank_of_test = np.where(ranking == ground_truth_pos)[0][0] + 1  # 1-indexed

            hr_3 = 1.0 if rank_of_test <= 3 else 0.0
            hr_5 = 1.0 if rank_of_test <= 5 else 0.0
            hr_10 = 1.0 if rank_of_test <= 10 else 0.0

            ndcg_5 = 1.0 / np.log2(rank_of_test + 1) if rank_of_test <= 5 else 0.0
            ndcg_10 = 1.0 / np.log2(rank_of_test + 1) if rank_of_test <= 10 else 0.0
            mrr = 1.0 / rank_of_test
            p_5 = hr_5 / 5.0
            r_5 = hr_5

            metrics[model_name]["HR@3"].append(hr_3)
            metrics[model_name]["HR@5"].append(hr_5)
            metrics[model_name]["HR@10"].append(hr_10)
            metrics[model_name]["NDCG@5"].append(ndcg_5)
            metrics[model_name]["NDCG@10"].append(ndcg_10)
            metrics[model_name]["MRR"].append(mrr)
            metrics[model_name]["P@5"].append(p_5)
            metrics[model_name]["R@5"].append(r_5)

    # ----------------------------------------------------
    # 5. Summarize Results & Print Publication Table
    # ----------------------------------------------------
    summary = []
    for m in models_to_evaluate:
        summary.append({
            "Model": m,
            "HR@3": np.mean(metrics[m]["HR@3"]),
            "HR@5": np.mean(metrics[m]["HR@5"]),
            "HR@10": np.mean(metrics[m]["HR@10"]),
            "NDCG@5": np.mean(metrics[m]["NDCG@5"]),
            "NDCG@10": np.mean(metrics[m]["NDCG@10"]),
            "MRR": np.mean(metrics[m]["MRR"]),
            "Precision@5": np.mean(metrics[m]["P@5"]),
            "Recall@5": np.mean(metrics[m]["R@5"])
        })

    summary_df = pd.DataFrame(summary)
    print("\n" + "=" * 90)
    print("🏆 COMPREHENSIVE MULTI-MODEL RECOMMENDATION BENCHMARK RESULTS")
    print("=" * 90)
    print(summary_df.to_string(index=False, formatters={
        "HR@3": "{:.4f}".format,
        "HR@5": "{:.4f}".format,
        "HR@10": "{:.4f}".format,
        "NDCG@5": "{:.4f}".format,
        "NDCG@10": "{:.4f}".format,
        "MRR": "{:.4f}".format,
        "Precision@5": "{:.4f}".format,
        "Recall@5": "{:.4f}".format
    }))
    print("=" * 90)

    # Save to JSON
    with open("benchmark_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Saved benchmark results to benchmark_results.json")

    # ----------------------------------------------------
    # 6. Generate Publication-Quality Visualizations
    # ----------------------------------------------------
    os.makedirs("plots", exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    colors = ['#95a5a6', '#7f8c8d', '#3498db', '#e67e22', '#9b59b6', '#2ecc71']

    # Subplot 1: Hit Rates
    x = np.arange(len(models_to_evaluate))
    width = 0.25

    axes[0].bar(x - width, summary_df['HR@3'], width, label='HR@3', color='#3498db', alpha=0.9)
    axes[0].bar(x, summary_df['HR@5'], width, label='HR@5', color='#2ecc71', alpha=0.9)
    axes[0].bar(x + width, summary_df['HR@10'], width, label='HR@10', color='#9b59b6', alpha=0.9)
    axes[0].set_ylabel('Hit Rate (HR@K)', fontsize=12, fontweight='bold')
    axes[0].set_title('Top-K Hit Rate Comparison Across Models', fontsize=14, fontweight='bold')
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([m.split(' (')[0] for m in models_to_evaluate], rotation=25, ha='right', fontsize=9)
    axes[0].legend(frameon=True, facecolor='white')
    axes[0].grid(axis='y', linestyle='--', alpha=0.5)

    # Subplot 2: NDCG and MRR
    axes[1].bar(x - width/2, summary_df['NDCG@10'], width, label='NDCG@10', color='#e67e22', alpha=0.9)
    axes[1].bar(x + width/2, summary_df['MRR'], width, label='MRR', color='#1abc9c', alpha=0.9)
    axes[1].set_ylabel('Score Metric', fontsize=12, fontweight='bold')
    axes[1].set_title('NDCG@10 and Mean Reciprocal Rank (MRR)', fontsize=14, fontweight='bold')
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([m.split(' (')[0] for m in models_to_evaluate], rotation=25, ha='right', fontsize=9)
    axes[1].legend(frameon=True, facecolor='white')
    axes[1].grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plot_path = "plots/comprehensive_model_benchmark.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"✅ Generated high-resolution benchmark visualization at: {plot_path}")

if __name__ == "__main__":
    run_comprehensive_benchmark()
