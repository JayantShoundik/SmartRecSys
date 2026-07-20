import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from recommender import SmartCampusRecommender

def calculate_precision_recall_at_k(actual_category, recommended_df, k):
    rec_k = recommended_df.head(k)
    hits = sum(rec_k['subject'] == actual_category)
    precision = hits / k if k > 0 else 0
    recall = hits / k
    return precision, recall

def run_evaluation():
    print("Initializing SmartCampusRecommender...")
    rec = SmartCampusRecommender()
    df = rec.df
    
    num_folds = 6
    k_values = [3, 5]
    
    results = {
        'Content-Based': {f'P@{k}': [] for k in k_values} | {f'R@{k}': [] for k in k_values},
        'Collaborative': {f'P@{k}': [] for k in k_values} | {f'R@{k}': [] for k in k_values},
        'Hybrid': {f'P@{k}': [] for k in k_values} | {f'R@{k}': [] for k in k_values}
    }
    
    print("Starting 6-fold cross-validation on test queries...")
    
    for fold in range(num_folds):
        print(f"--- Fold {fold + 1}/{num_folds} ---")
        
        sample_courses = df.sample(n=100, random_state=100 + fold)
        
        for _, query_row in sample_courses.iterrows():
            cid = query_row['course_id']
            subj = query_row['subject']
            
            c_recs = rec.get_content_recommendations(cid, top_n=5)
            cf_recs = rec.get_collaborative_recommendations(cid, top_n=5)
            h_recs = rec.get_hybrid_recommendations(cid, alpha=0.5, top_n=5)
            
            for k in k_values:
                p_c, r_c = calculate_precision_recall_at_k(subj, c_recs, k)
                p_cf, r_cf = calculate_precision_recall_at_k(subj, cf_recs, k)
                p_h, r_h = calculate_precision_recall_at_k(subj, h_recs, k)
                
                results['Content-Based'][f'P@{k}'].append(p_c)
                results['Content-Based'][f'R@{k}'].append(r_c)
                results['Collaborative'][f'P@{k}'].append(p_cf)
                results['Collaborative'][f'R@{k}'].append(r_cf)
                results['Hybrid'][f'P@{k}'].append(p_h)
                results['Hybrid'][f'R@{k}'].append(r_h)

    print("\n" + "="*50)
    print("EVALUATION SUMMARY (Average over 6 Folds)")
    print("="*50)
    
    summary_metrics = {}
    for model in results:
        print(f"\nModel: {model}")
        summary_metrics[model] = {}
        for metric in results[model]:
            avg_val = np.mean(results[model][metric])
            summary_metrics[model][metric] = avg_val
            print(f"  {metric}: {avg_val:.4f}")

    os.makedirs("plots", exist_ok=True)
    
    models = list(summary_metrics.keys())
    p3_scores = [summary_metrics[m]['P@3'] for m in models]
    p5_scores = [summary_metrics[m]['P@5'] for m in models]
    
    x = np.arange(len(models))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width/2, p3_scores, width, label='Precision@3', color='#2b5c8f')
    ax.bar(x + width/2, p5_scores, width, label='Precision@5', color='#4682b4')
    
    ax.set_ylabel('Precision Score (Domain Consistency)')
    ax.set_title('Recommender Model Performance (Precision@K)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.1)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig("plots/evaluation_comparison.png")
    print("\nSaved evaluation comparison plot to 'plots/evaluation_comparison.png'")

if __name__ == "__main__":
    run_evaluation()