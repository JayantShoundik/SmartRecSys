import pandas as pd
from recommender import SmartCampusRecommender

def run_demo():
    print("=" * 60)
    print("SmartCampusRecommender Demo: Course Recommendation System")
    print("=" * 60)

    rec = SmartCampusRecommender()
    
    # Pick 4 diverse sample course IDs from different subjects
    test_course_ids = [
        rec.df[rec.df['subject'] == 'Web Development'].iloc[0]['course_id'],
        rec.df[rec.df['subject'] == 'Graphic Design'].iloc[0]['course_id'],
        rec.df[rec.df['subject'] == 'Business Finance'].iloc[0]['course_id'],
        rec.df[rec.df['subject'] == 'Musical Instruments'].iloc[0]['course_id']
    ]

    for cid in test_course_ids:
        query_row = rec.df[rec.df['course_id'] == cid].iloc[0]
        print("\n" + "-" * 60)
        print(f"Query Course: {query_row['course_title']}")
        print(f"Subject: {query_row['subject']} | Level: {query_row['level']}")
        print("-" * 60)

        # 1. Content-Based
        cb_recs = rec.get_content_recommendations(cid, top_n=3)
        print("\n[1] Content-Based Recommendations (TF-IDF + Title Similarity):")
        for idx, (_, row) in enumerate(cb_recs.iterrows(), 1):
            print(f"  {idx}. {row['course_title']} | Sub: {row['subject']} | Lvl: {row['level']}")

        # 2. Collaborative
        cf_recs = rec.get_collaborative_recommendations(cid, top_n=3)
        print("\n[2] Collaborative Filtering Recommendations (Simulated Co-Enrollment):")
        for idx, (_, row) in enumerate(cf_recs.iterrows(), 1):
            print(f"  {idx}. {row['course_title']} | Sub: {row['subject']} | Lvl: {row['level']}")

        # 3. Hybrid
        h_recs = rec.get_hybrid_recommendations(cid, alpha=0.5, top_n=3)
        print("\n[3] Hybrid Recommendations (Fused Content + Collaborative, alpha=0.5):")
        for idx, (_, row) in enumerate(h_recs.iterrows(), 1):
            print(f"  {idx}. {row['course_title']} | Score: {row['hybrid_score']:.4f} | Sub: {row['subject']} | Lvl: {row['level']}")

    print("\n" + "=" * 60)
    print("Demo completed successfully.")
    print("=" * 60)

if __name__ == "__main__":
    run_demo()