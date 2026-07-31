import os
import sys
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from recommender import SmartCampusRecommender

# Initialize Flask app
app = Flask(__name__)
# Enable CORS for frontend integration
CORS(app)

print("Loading Recommender System components...")
try:
    recommender = SmartCampusRecommender()
    print("Recommender loaded successfully!")
except Exception as e:
    print(f"Error loading recommender: {e}")
    sys.exit(1)

# Deep Learning (NCF) Model Loading if available
ncf_model = None
device = None
ncf_dataset = None

try:
    import torch
    from dl_recommender_gpu import NeuralCollaborativeFiltering, CourseInteractionDataset
    
    model_path = "models/ncf_recommender.pth"
    if os.path.exists(model_path):
        print("Found trained NCF model weights. Loading...")
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")
            
        ncf_dataset = CourseInteractionDataset(recommender.df, num_users=1000)
        ncf_model = NeuralCollaborativeFiltering(num_users=1000, num_items=ncf_dataset.num_items, embedding_dim=16)
        ncf_model.load_state_dict(torch.load(model_path, map_location=device))
        ncf_model.to(device)
        ncf_model.eval()
        print(f"NCF model loaded successfully on {device}!")
except Exception as e:
    print(f"Deep learning NCF components not initialized: {e}")

# Simple hash function to map any name string to a stable User ID (0-999)
def get_user_id_from_name(name):
    if not name:
        return 42
    hash_val = sum(ord(char) for char in name)
    return hash_val % 1000

# Helper to generate duration, description, skills, and why recommended based on course row
def build_course_metadata(row, domain, difficulty, score, dept):
    title = row['course_title']
    subj = row['subject']
    
    # 1. Map difficulty level
    lvl = row['level'].replace(" Level", "")
    
    # 2. Dynamic duration
    lectures = int(row['num_lectures'])
    duration = f"{max(4, min(12, lectures // 4))} Weeks"
    
    # 3. Dynamic description
    desc = f"Master the essentials of {title}. This comprehensive class covers fundamental concepts, practical assignments, and key applications in {subj}."
    
    # 4. Dynamic skills tags
    skills = [subj]
    if "python" in title.lower():
        skills.extend(["Python", "Programming"])
    elif "javascript" in title.lower() or "js" in title.lower():
        skills.extend(["JavaScript", "Frontend"])
    elif "design" in title.lower():
        skills.extend(["UI/UX", "Visual Arts"])
    elif "finance" in title.lower() or "accounting" in title.lower():
        skills.extend(["Financial Analysis", "Excel"])
    else:
        skills.extend(["Practical Skills", "Problem Solving"])
        
    # 5. Dynamic personalized reasoning
    if dept == "Electrical Engineering":
        reason = f"Highly relevant for Electrical Engineering students interested in {domain}. Combines computational modeling and mathematical logic."
    else:
        reason = f"Recommended based on your interest in {domain} at a {difficulty} level. Aligns with your stated post-graduation career goals."
        
    return {
        "title": title,
        "domain": subj,
        "difficulty": lvl,
        "score": float(score),
        "duration": duration,
        "description": desc,
        "skills": list(set(skills)),
        "reason": reason
    }

@app.route('/recommend', methods=['GET', 'POST'])
def get_recommendations():
    try:
        # Support both GET and POST requests
        if request.method == 'POST':
            req_data = request.get_json() or {}
            user_input = req_data.get('user_id', 'Student')
            preferences = req_data.get('preferences', {})
            domains = preferences.get('domains', [])
            difficulty = preferences.get('difficulty', '')
            dept = preferences.get('dept', '')
        else:
            user_input = request.args.get('user_id', 'Student')
            domains = request.args.get('domains', '').split(',')
            domains = [d.strip() for d in domains if d.strip()]
            difficulty = request.args.get('difficulty', '')
            dept = request.args.get('dept', '')

        # Resolve User ID from string name or integer
        try:
            user_id = int(user_input)
        except ValueError:
            user_id = get_user_id_from_name(str(user_input))
            
        print(f"Inference request - User ID: {user_id} | Dept: {dept} | Domains: {domains} | Difficulty: {difficulty}")

        # Retrieve user history
        user_enrollments = np.where(recommender.user_course_matrix.values[user_id] == 1)[0]
        
        # 1. Subject/Domain filtering rules based on Department and Domain preferences
        # We find courses matching the selected subject areas
        filtered_df = recommender.df.copy()
        
        # Mapping domain checkbox strings to Udemy subjects/keywords
        domain_keywords = []
        subject_filters = []
        
        # If student belongs to Electrical Engineering, we prioritize programming, quantitative data science, and excel/modeling
        is_electrical = (dept == "Electrical Engineering")
        
        for dom in domains:
            if dom == "Web Development":
                subject_filters.append("Web Development")
            elif dom == "Programming" or dom == "Software Engineering":
                subject_filters.append("Web Development") # Web Dev contains all general programming courses in this dataset
                domain_keywords.extend(["javascript", "python", "java", "c++", "programming", "git", "coding", "software"])
            elif dom == "Data Science" or dom == "Machine Learning" or dom == "AI":
                domain_keywords.extend(["data", "python", "machine learning", "ai", "artificial intelligence", "pandas", "excel", "neural", "statistics"])
            elif dom == "Cloud Computing" or dom == "Cybersecurity":
                domain_keywords.extend(["aws", "cloud", "security", "network", "cyber", "hacking"])
                
        # Apply department-specific boosts/keywords
        if is_electrical:
            domain_keywords.extend(["matlab", "circuit", "arduino", "electronics", "electricity", "math", "signal", "power", "python"])
            
        # Apply filters
        conditions = []
        if subject_filters:
            conditions.append(filtered_df['subject'].isin(subject_filters))
        if domain_keywords:
            kw_regex = '|'.join(domain_keywords)
            conditions.append(filtered_df['course_title'].str.contains(kw_regex, case=False, na=False))
            
        if conditions:
            # Combine conditions with OR (matching either the subject or key keywords)
            filtered_df = filtered_df[np.logical_or.reduce(conditions)]
            
        # If filter is too strict and results are empty, fall back to full dataset
        if len(filtered_df) == 0:
            filtered_df = recommender.df.copy()
            
        # 2. Filter by difficulty
        if difficulty:
            difficulty_map = {
                "Beginner": "Beginner Level",
                "Intermediate": "Intermediate Level",
                "Advanced": "Expert Level"
            }
            target_difficulty = difficulty_map.get(difficulty)
            if target_difficulty and target_difficulty in filtered_df['level'].values:
                filtered_df = filtered_df[filtered_df['level'] == target_difficulty]
                
        # 3. Retrieve scored items
        # If NCF model is loaded, we use NCF scores, otherwise Hybrid recommender scores
        n_candidates = len(filtered_df)
        top_k = 6 # Render top-6 recommended cards on the dashboard
        
        # Make query course selection
        if len(user_enrollments) == 0:
            query_idx = 0
        else:
            query_idx = user_enrollments[0]
            
        query_course_id = recommender.df.iloc[query_idx]['course_id']
        
        # Calculate hybrid recommendation scores
        scores_df = recommender.get_hybrid_recommendations(query_course_id, alpha=0.5, top_n=len(recommender.df))
        scores_df = scores_df.set_index('course_id')
        
        # Map calculated scores to our filtered candidates list
        candidate_ids = filtered_df['course_id'].values
        candidate_scores = []
        for cid in candidate_ids:
            if cid in scores_df.index:
                candidate_scores.append(scores_df.loc[cid, 'hybrid_score'])
            else:
                candidate_scores.append(0.5) # fallback score
                
        filtered_df = filtered_df.copy()
        filtered_df['score'] = candidate_scores
        
        # Sort and take top k
        recs_df = filtered_df.sort_values(by='score', ascending=False).head(top_k)
        
        # 4. Package JSON response matching the card builder properties
        output = []
        chosen_domain = domains[0] if domains else "General"
        chosen_difficulty = difficulty if difficulty else "Any"
        
        for i, (_, row) in enumerate(recs_df.iterrows(), 1):
            metadata = build_course_metadata(row, chosen_domain, chosen_difficulty, row['score'], dept)
            metadata["rank"] = i
            output.append(metadata)
            
        return jsonify(output)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "status": "online",
        "total_courses": len(recommender.df) if recommender.df is not None else 0,
        "ncf_loaded": ncf_model is not None,
        "device": str(device) if device is not None else "cpu"
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
