import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from recommender import SmartCampusRecommender


def calculate_precision_recall_at_k(masked_course_id, recommended_df, k):
    rec_k = recommended_df.head(k)
    hit = int(masked_course_id in rec_k['course_id'].values)
    precision = hit / k
    recall = hit / 1  # ground truth is always 1 masked course
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
        'Hybrid':        {f'P@{k}': [] for k in k_values} | {f'R@{k}': [] for k in k_values}
    }

    # Build per-user enrollment lists from the synthetic interaction matrix
    # user_course_matrix columns are df integer indices
    user_course_matrix = rec.user_course_matrix  # shape (1000, num_courses)
    course_indices = list(user_course_matrix.columns)  # df integer indices

    # Map df integer index -> course_id
    idx_to_cid = df['course_id'].to_dict()

    # Build list of (user_id, list_of_enrolled_df_indices) for users with >= 2 enrollments
    user_enrollments = []
    for user_id in range(len(user_course_matrix)):
        row = user_course_matrix.iloc[user_id]
        enrolled_indices = [ci for ci in course_indices if row[ci] == 1]
        if len(enrolled_indices) >= 2:
            user_enrollments.append(enrolled_indices)

    np.random.seed(42)
    fold_size = len(user_enrollments) // num_folds

    print("Starting 6-fold cross-validation (mask-one-out per user)...")

    for fold in range(num_folds):
        print(f"--- Fold {fold + 1}/{num_folds} ---")

        fold_users = user_enrollments[fold * fold_size: (fold + 1) * fold_size]

        for enrolled_indices in fold_users:
            # Mask one random enrollment as ground truth
            mask_pos = np.random.randint(0, len(enrolled_indices))
            masked_idx = enrolled_indices[mask_pos]
            masked_cid = idx_to_cid[masked_idx]

            # Use remaining enrollments as the query — pick the first remaining course
            remaining = [i for i in enrolled_indices if i != masked_idx]
            query_cid = idx_to_cid[remaining[0]]

            c_recs  = rec.get_content_recommendations(query_cid, top_n=5)
            cf_recs = rec.get_collaborative_recommendations(query_cid, top_n=5)
            h_recs  = rec.get_hybrid_recommendations(query_cid, alpha=0.5, top_n=5)

            for k in k_values:
                p_c,  r_c  = calculate_precision_recall_at_k(masked_cid, c_recs,  k)
                p_cf, r_cf = calculate_precision_recall_at_k(masked_cid, cf_recs, k)
                p_h,  r_h  = calculate_precision_recall_at_k(masked_cid, h_recs,  k)

                results['Content-Based'][f'P@{k}'].append(p_c)
                results['Content-Based'][f'R@{k}'].append(r_c)
                results['Collaborative'][f'P@{k}'].append(p_cf)
                results['Collaborative'][f'R@{k}'].append(r_cf)
                results['Hybrid'][f'P@{k}'].append(p_h)
                results['Hybrid'][f'R@{k}'].append(r_h)

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY (Average over 6 Folds)")
    print("=" * 50)

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

    ax.set_ylabel('Precision Score')
    ax.set_title('Recommender Model Performance (Precision@K) — 6-Fold CV')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.1)
    ax.legend()

    plt.tight_layout()
    plt.savefig("plots/evaluation_comparison.png")
    print("\nSaved evaluation comparison plot to 'plots/evaluation_comparison.png'")


if __name__ == "__main__":
    run_evaluation()
