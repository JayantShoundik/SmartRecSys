import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from recommender import SmartCampusRecommender
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD

def run_evaluation():
    print("Initializing SmartCampusRecommender...")
    rec = SmartCampusRecommender()
    
    df = rec.df
    user_course = rec.user_course_matrix.values
    num_users, num_courses = user_course.shape
    
    # 6-Fold Cross-Validation Setup
    folds = 6
    np.random.seed(42)
    
    # Keep track of metrics for all models, including SVD (Machine Learning model)
    results = {
        'Content-Based': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []},
        'Collaborative': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []},
        'Hybrid': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []},
        'ML-MatrixFactorization (SVD)': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []}
    }
    
    print(f"Starting {folds}-fold evaluation on simulated users...")
    
    for fold in range(folds):
        print(f"--- Fold {fold+1}/{folds} ---")
        
        # Prepare training and testing matrices
        train_matrix = user_course.copy()
        test_links = []
        
        # For each user, mask one random enrollment for testing
        for user_idx in range(num_users):
            active_enrollments = np.where(user_course[user_idx] == 1)[0]
            if len(active_enrollments) > 1:
                masked_idx = np.random.choice(active_enrollments)
                train_matrix[user_idx, masked_idx] = 0
                test_links.append((user_idx, masked_idx))
                
        # 1. Fit ML Model: Singular Value Decomposition (SVD Matrix Factorization)
        # SVD learns a 12-dimensional latent representation of users and courses
        svd = TruncatedSVD(n_components=12, random_state=42)
        user_factors = svd.fit_transform(train_matrix)
        # Reconstruct the rating/enrollment scores
        svd_reconstructed = svd.inverse_transform(user_factors)
        
        # 2. Fit Collaborative Similarity on training data
        collab_similarity_train = cosine_similarity(train_matrix.T)
        
        # 3. Fit Content Similarity (constant item features)
        content_similarity = rec.content_similarity
        
        fold_metrics = {
            'Content-Based': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []},
            'Collaborative': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []},
            'Hybrid': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []},
            'ML-MatrixFactorization (SVD)': {'P@3': [], 'R@3': [], 'P@5': [], 'R@5': []}
        }
        
        # Evaluate for each test user
        for user_idx, masked_course_idx in test_links:
            # Get user's remaining training courses
            user_train_courses = np.where(train_matrix[user_idx] == 1)[0]
            if len(user_train_courses) == 0:
                continue
                
            # Content scores
            content_scores = content_similarity[user_train_courses].mean(axis=0)
            
            # Collaborative scores
            collab_scores = collab_similarity_train[user_train_courses].mean(axis=0)
            
            # Hybrid scores
            hybrid_scores = 0.5 * content_scores + 0.5 * collab_scores
            
            # SVD scores (predict from the trained matrix factorization model)
            svd_scores = svd_reconstructed[user_idx].copy()
            
            # Exclude courses already in the training set
            content_scores[user_train_courses] = -1
            collab_scores[user_train_courses] = -1
            hybrid_scores[user_train_courses] = -1
            svd_scores[user_train_courses] = -1
            
            def get_p_r_at_k(scores, masked_idx, k):
                top_k_indices = np.argsort(scores)[::-1][:k]
                hits = 1 if masked_idx in top_k_indices else 0
                precision = hits / k
                recall = hits / 1
                return precision, recall
                
            for k in [3, 5]:
                # Content
                p, r = get_p_r_at_k(content_scores, masked_course_idx, k)
                fold_metrics['Content-Based'][f'P@{k}'].append(p)
                fold_metrics['Content-Based'][f'R@{k}'].append(r)
                
                # Collaborative
                p, r = get_p_r_at_k(collab_scores, masked_course_idx, k)
                fold_metrics['Collaborative'][f'P@{k}'].append(p)
                fold_metrics['Collaborative'][f'R@{k}'].append(r)
                
                # Hybrid
                p, r = get_p_r_at_k(hybrid_scores, masked_course_idx, k)
                fold_metrics['Hybrid'][f'P@{k}'].append(p)
                fold_metrics['Hybrid'][f'R@{k}'].append(r)
                
                # SVD
                p, r = get_p_r_at_k(svd_scores, masked_course_idx, k)
                fold_metrics['ML-MatrixFactorization (SVD)'][f'P@{k}'].append(p)
                fold_metrics['ML-MatrixFactorization (SVD)'][f'R@{k}'].append(r)
                
        # Aggregate fold metrics
        for model in results:
            for metric in results[model]:
                mean_val = np.mean(fold_metrics[model][metric])
                results[model][metric].append(mean_val)
                
    # Compute overall average across folds
    summary_data = []
    print("\n" + "="*60)
    print("EVALUATION SUMMARY (Average over 6 Folds)")
    print("="*60)
    
    for model in results:
        print(f"\nModel: {model}")
        row = {'Model': model}
        for metric in ['P@3', 'R@3', 'P@5', 'R@5']:
            avg_val = np.mean(results[model][metric])
            row[metric] = avg_val
            print(f"  {metric}: {avg_val:.4f}")
        summary_data.append(row)
        
    summary_df = pd.DataFrame(summary_data)
    
    # Plot results
    plt.figure(figsize=(12, 6))
    melted_df = pd.melt(summary_df, id_vars=['Model'], value_vars=['P@3', 'R@3', 'P@5', 'R@5'],
                        var_name='Metric', value_name='Value')
    
    sns.barplot(data=melted_df, x='Metric', y='Value', hue='Model', palette='muted')
    plt.title("Performance Comparison: Precision@K and Recall@K (Including Trained ML SVD)", fontsize=14, fontweight='bold')
    plt.ylabel("Metric Value", fontsize=12)
    plt.xlabel("Evaluation Metric", fontsize=12)
    plt.ylim(0, 1.05)
    plt.legend(title="Model Type")
    plt.tight_layout()
    
    os.makedirs("plots", exist_ok=True)
    plt.savefig("plots/evaluation_comparison.png", dpi=150)
    plt.close()
    print("\nSaved plots/evaluation_comparison.png successfully.")
    
if __name__ == "__main__":
    run_evaluation()
