import os
import random
import numpy as np
import pandas as pd

def generate_large_scale_dataset(
    dataset_path="dataset/udemy_courses.csv",
    output_path="dataset/large_campus_interactions.csv",
    num_users=25000,
    random_seed=42
):
    """
    Generates a realistic large-scale Smart Campus interaction dataset.
    Simulates coherent curriculum pathways across major engineering and academic tracks:
      - Track 1: Full-Stack Web Development & Software
      - Track 2: Python, Data Science & Machine Learning
      - Track 3: Graphic Design, Multimedia & UI/UX
      - Track 4: Business, Finance & Quantitative Modeling
      - Track 5: Audio, Creative Arts & Musical Instruments
      - Track 6: Interdisciplinary Engineering (Cross-domain electives)
    """
    print("=" * 65)
    print(f"Generating Large-Scale Smart Campus Interactions ({num_users:,} Students)...")
    print("=" * 65)

    random.seed(random_seed)
    np.random.seed(random_seed)

    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Base catalog {dataset_path} not found!")

    df = pd.read_csv(dataset_path)
    num_courses = len(df)
    print(f"Loaded course catalog: {num_courses:,} courses across {df['subject'].nunique()} domains.")

    # 1. Index courses by subject and keywords for realistic academic tracks
    df['title_lower'] = df['course_title'].astype(str).str.lower()
    
    # Sub-domain indices
    web_indices = df[df['subject'] == 'Web Development'].index.tolist()
    finance_indices = df[df['subject'] == 'Business Finance'].index.tolist()
    design_indices = df[df['subject'] == 'Graphic Design'].index.tolist()
    music_indices = df[df['subject'] == 'Musical Instruments'].index.tolist()

    # Specialized keyword-based prerequisite paths
    python_indices = df[df['title_lower'].str.contains('python|data|pandas|machine learning|django|flask', regex=True)].index.tolist()
    js_frontend_indices = df[df['title_lower'].str.contains('javascript|react|vue|angular|html|css|bootstrap', regex=True)].index.tolist()
    backend_indices = df[df['title_lower'].str.contains('node|express|php|sql|database|api|backend', regex=True)].index.tolist()
    uiux_indices = df[df['title_lower'].str.contains('photoshop|illustrator|ui|ux|design|logo|drawing', regex=True)].index.tolist()
    quant_indices = df[df['title_lower'].str.contains('trading|stock|forex|invest|accounting|finance|excel', regex=True)].index.tolist()

    # Level-based partitions
    beginner_indices = set(df[df['level'].isin(['Beginner Level', 'All Levels'])].index.tolist())
    advanced_indices = set(df[df['level'].isin(['Intermediate Level', 'Expert Level'])].index.tolist())

    tracks = [
        # Track Name, Primary Pool, Advanced Pool, Weight
        ('Full-Stack Web Dev', js_frontend_indices, backend_indices, 0.30),
        ('Python & Data Science', python_indices, web_indices, 0.25),
        ('UI/UX & Graphic Design', uiux_indices, design_indices, 0.20),
        ('Business & Quantitative Finance', quant_indices, finance_indices, 0.15),
        ('Creative Arts & Audio', music_indices, music_indices, 0.10)
    ]

    track_names = [t[0] for t in tracks]
    track_weights = [t[3] for t in tracks]

    user_records = []
    total_enrollments = 0

    print("Synthesizing coherent academic enrollment trajectories...")
    for user_id in range(num_users):
        # Choose primary academic track for student
        track_idx = np.random.choice(len(tracks), p=track_weights)
        track_name, primary_pool, adv_pool, _ = tracks[track_idx]

        # Determine number of course enrollments for this student (between 4 and 15)
        num_courses_enrolled = np.random.randint(4, 16)

        # 1. 60-70% courses from primary foundational curriculum
        n_primary = max(2, int(num_courses_enrolled * 0.65))
        n_primary = min(n_primary, len(primary_pool))
        enrolled_primary = np.random.choice(primary_pool, size=n_primary, replace=False).tolist()

        # 2. 20-25% from advanced continuation track
        n_adv = max(1, int(num_courses_enrolled * 0.20))
        avail_adv = [idx for idx in adv_pool if idx not in enrolled_primary]
        if avail_adv and n_adv > 0:
            n_adv = min(n_adv, len(avail_adv))
            enrolled_adv = np.random.choice(avail_adv, size=n_adv, replace=False).tolist()
        else:
            enrolled_adv = []

        # 3. 10-15% minor interdisciplinary electives from any domain
        all_enrolled = set(enrolled_primary + enrolled_adv)
        remaining_needed = num_courses_enrolled - len(all_enrolled)
        
        if remaining_needed > 0:
            general_pool = [idx for idx in range(num_courses) if idx not in all_enrolled]
            # Bias electives by popularity (num_subscribers)
            elective_sample = np.random.choice(general_pool, size=remaining_needed, replace=False).tolist()
            all_enrolled.update(elective_sample)

        for course_idx in all_enrolled:
            user_records.append({
                'user_id': user_id,
                'course_index': course_idx,
                'course_id': df.iloc[course_idx]['course_id'],
                'track': track_name,
                'rating': 1.0  # Positive interaction
            })
            total_enrollments += 1

    interactions_df = pd.DataFrame(user_records)
    os.makedirs("dataset", exist_ok=True)
    interactions_df.to_csv(output_path, index=False)

    sparsity = 100.0 * (1.0 - (total_enrollments / (num_users * num_courses)))
    print(f"\n✅ Large-Scale Dataset Generated Successfully:")
    print(f"   - Total Students:     {num_users:,}")
    print(f"   - Total Interactions: {total_enrollments:,}")
    print(f"   - Average per Student: {total_enrollments / num_users:.1f} courses")
    print(f"   - Catalog Coverage:   {interactions_df['course_index'].nunique():,}/{num_courses:,} courses")
    print(f"   - Matrix Sparsity:    {sparsity:.2f}%")
    print(f"   - Output File:        {output_path}\n")

    return interactions_df

if __name__ == "__main__":
    generate_large_scale_dataset(num_users=25000)
