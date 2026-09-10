import os
import sys
import json
import re
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics.pairwise import cosine_similarity
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from recommender import SmartCampusRecommender
from database import SessionLocal, Student, RecommendationAudit
from dl_recommender_gpu import NeuralCollaborativeFiltering

# Device Configuration
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")

# Load Recommender
rec = SmartCampusRecommender()
df = rec.df.copy()

deep_model = None
model_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), "models", "ncf_recommender.pth")
if os.path.exists(model_path):
    try:
        deep_model = NeuralCollaborativeFiltering(num_users=1000, num_items=len(df), embedding_dim=16).to(device)
        deep_model.load_state_dict(torch.load(model_path, map_location=device))
        deep_model.eval()
        print(f"✅ Loaded NCF PyTorch Deep Learning Model on {device}!")
    except Exception as e:
        print(f"Model load notice: {e}")

def extract_course_skills(title, subject):
    skills = [subject]
    t = title.lower()
    keywords = {
        "python": "Python", "javascript": "JavaScript", "react": "React.js",
        "node": "Node.js", "html": "HTML5", "css": "CSS3", "sql": "SQL",
        "django": "Django", "flask": "Flask", "bootstrap": "Bootstrap",
        "java": "Java", "c++": "C++", "data science": "Data Science",
        "machine learning": "Machine Learning", "deep learning": "Deep Learning",
        "pandas": "Pandas", "numpy": "NumPy", "docker": "Docker", "aws": "AWS",
        "photoshop": "Photoshop", "illustrator": "Illustrator", "ui/ux": "UI/UX Design",
        "ui": "UI Design", "ux": "UX Design", "trading": "Technical Analysis",
        "finance": "Financial Modeling", "excel": "Microsoft Excel", "accounting": "Accounting",
        "git": "Git", "security": "Cybersecurity", "cloud": "Cloud Computing",
        "lamp": "LAMP Stack", "linux": "Linux", "spring": "Spring Framework",
        "wordpress": "WordPress"
    }
    short_words = {"ui", "ux", "git", "aws", "sql", "java", "css", "html", "lamp", "node"}
    for kw, skill in keywords.items():
        if kw in short_words or len(kw) <= 3:
            if re.search(r'\b' + re.escape(kw) + r'\b', t):
                skills.append(skill)
        else:
            if kw in t:
                skills.append(skill)
    if len(skills) == 1:
        skills.extend(["Core Concepts", "Hands-on Projects"])
    return list(dict.fromkeys(skills))

def format_level(level_str):
    l = str(level_str).strip().lower()
    if "all" in l:
        return "All Levels"
    elif "beginner" in l:
        return "Beginner"
    elif "intermediate" in l:
        return "Intermediate"
    elif "expert" in l or "advanced" in l:
        return "Advanced"
    return str(level_str).replace(" Levels", "").replace(" Level", "").strip()

def generate_xai_reason(row, dept, domains, difficulty, career_goal, completed_courses):
    title = row['course_title']
    subj = row['subject']
    lvl = format_level(row.get('level', 'All Levels'))
    reasons = []
    matched_domain = None
    if domains:
        t_low = title.lower()
        for d in domains:
            d_low = d.lower()
            if d_low in t_low or (d_low in ["web development", "programming"] and subj == "Web Development"):
                matched_domain = d
                break
            elif any(k in d_low for k in ["cyber", "cloud", "security", "network"]) and any(k in t_low for k in ["security", "aws", "cloud", "network", "linux"]):
                matched_domain = d
                break
            elif any(k in d_low for k in ["data", "machine learning", "ai"]) and any(k in t_low for k in ["data", "python", "machine", "learning", "ai"]):
                matched_domain = d
                break
            elif any(k in d_low for k in ["design", "ui", "ux"]) and subj == "Graphic Design":
                matched_domain = d
                break
            elif any(k in d_low for k in ["finance", "business"]) and subj == "Business Finance":
                matched_domain = d
                break
        if not matched_domain:
            matched_domain = domains[0]
            
    if matched_domain and matched_domain != "General":
        reasons.append(f"Directly satisfies your academic focus in {matched_domain} at {lvl.lower()} level")
    else:
        reasons.append(f"Directly fulfills your technical focus in {subj} at {lvl.lower()} level")
        
    if career_goal and career_goal.strip().lower() not in ["other", "none", "", "select"]:
        reasons.append(f"develops core technical competencies essential for an aspiring {career_goal.strip()}")
    elif dept and dept.strip().lower() not in ["other", "none", ""]:
        reasons.append(f"accelerates your engineering specialization in {dept.strip()}")
    else:
        reasons.append("builds career-ready technical expertise and practical competency")

    if completed_courses and completed_courses.strip():
        first_c = completed_courses.split(',')[0].strip()
        reasons.append(f"logically builds upon your completed coursework in {first_c}")

    return "; ".join(reasons) + "."

def run_cohort(cohort_id, profile):
    name = profile['name']
    dept = profile['dept']
    degree = profile['degree']
    year = profile['batch']
    sem = profile['semester']
    domains = profile['domains']
    diff = profile['difficulty']
    goal = profile['career_goal']
    completed = profile.get('completed_courses', '')

    # 1. Semantic Profile Vectorization
    profile_terms = [
        dept, degree, year, f"Semester {sem}",
        " ".join(domains), diff, goal, completed
    ]
    query_str = " ".join([p for p in profile_terms if p]).strip()
    profile_vec = rec.vectorizer.transform([query_str])
    semantic_sim = cosine_similarity(profile_vec, rec.tfidf_matrix).flatten()

    # 2. Domain Keywords & Subject Alignment
    domain_keywords = []
    target_subjects = []
    for d in domains:
        d_lower = d.lower()
        if "web" in d_lower or "software" in d_lower or "programming" in d_lower:
            target_subjects.append("Web Development")
            domain_keywords.extend(["python", "javascript", "react", "html", "css", "django", "flask", "web", "frontend", "fullstack", "programming", "algorithms", "git"])
        elif "data" in d_lower or "machine learning" in d_lower or "ai" in d_lower:
            domain_keywords.extend(["data", "python", "machine learning", "ai", "pandas", "numpy", "deep learning", "neural", "statistics"])
        elif "cyber" in d_lower or "cloud" in d_lower or "network" in d_lower:
            domain_keywords.extend(["network", "security", "cloud", "aws", "cyber", "linux", "server", "penetration", "docker"])
        elif "design" in d_lower or "ui" in d_lower:
            target_subjects.append("Graphic Design")
            domain_keywords.extend(["photoshop", "illustrator", "ui", "ux", "design", "figma", "drawing"])
        elif "finance" in d_lower or "business" in d_lower:
            target_subjects.append("Business Finance")
            domain_keywords.extend(["finance", "accounting", "trading", "stock", "excel", "investing"])

    domain_scores = np.zeros(len(df))
    title_lower = df['course_title'].str.lower().values
    subject_vals = df['subject'].values

    for i in range(len(df)):
        subj = subject_vals[i]
        t = title_lower[i]
        score = 0.0
        if target_subjects and subj in target_subjects:
            score += 0.50
        matched_kw = sum(1 for kw in domain_keywords if kw in t)
        if matched_kw > 0:
            score += min(0.50, matched_kw * 0.20)
        domain_scores[i] = score

    # 3. Difficulty Alignment
    diff_scores = np.zeros(len(df))
    diff_target = diff.lower()
    for i, lvl in enumerate(df['level'].values):
        l_low = lvl.lower()
        if "beginner" in diff_target:
            if "beginner" in l_low: diff_scores[i] = 1.0
            elif "all" in l_low: diff_scores[i] = 0.85
            elif "intermediate" in l_low: diff_scores[i] = 0.40
            else: diff_scores[i] = 0.10
        elif "intermediate" in diff_target:
            if "intermediate" in l_low: diff_scores[i] = 1.0
            elif "all" in l_low: diff_scores[i] = 0.80
            elif "expert" in l_low or "advanced" in l_low: diff_scores[i] = 0.70
            else: diff_scores[i] = 0.50
        else:
            if "expert" in l_low or "advanced" in l_low: diff_scores[i] = 1.0
            elif "intermediate" in l_low: diff_scores[i] = 0.85
            elif "all" in l_low: diff_scores[i] = 0.70
            else: diff_scores[i] = 0.30

    # 4. Neural Scoring
    neural_scores = np.zeros(len(df))
    if deep_model is not None:
        try:
            candidate_idx = np.arange(len(df))
            u_tens = torch.full((len(df),), cohort_id * 101 % 1000, dtype=torch.long, device=device)
            i_tens = torch.tensor(candidate_idx, dtype=torch.long, device=device)
            with torch.no_grad():
                neural_scores = deep_model(u_tens, i_tens).cpu().numpy()
        except Exception:
            neural_scores = np.zeros(len(df))

    # 5. Hybrid Fusion
    final_scores = np.zeros(len(df))
    for i in range(len(df)):
        if domain_scores[i] == 0.0 and len(domain_keywords) > 0:
            final_scores[i] = 0.05
        else:
            s_sem = semantic_sim[i]
            s_dom = domain_scores[i]
            s_dif = diff_scores[i]
            s_neu = neural_scores[i] if neural_scores[i] > 0 else 0.5
            raw = (0.40 * s_dom) + (0.30 * s_sem) + (0.20 * s_dif) + (0.10 * s_neu)
            final_scores[i] = min(0.98, max(0.65, 0.65 + (raw * 0.33)))

    df_cohort = df.copy()
    df_cohort['final_score'] = final_scores
    top_k = df_cohort.sort_values(by='final_score', ascending=False).head(5)

    results = []
    for rank, (_, row) in enumerate(top_k.iterrows(), 1):
        results.append({
            "rank": rank,
            "title": row['course_title'],
            "subject": row['subject'],
            "level": format_level(row['level']),
            "score": round(float(row['final_score']) * 100, 2),
            "skills": extract_course_skills(row['course_title'], row['subject']),
            "reason": generate_xai_reason(row, dept, domains, diff, goal, completed)
        })

    return {
        "cohort_id": cohort_id,
        "profile": profile,
        "recommendations": results
    }

cohorts = [
    {
        "name": "Aarav Sharma",
        "dept": "Computer Science & Engineering",
        "degree": "B.Tech (4-Year)",
        "batch": "3rd Year",
        "semester": 5,
        "domains": ["Data Science", "Machine Learning"],
        "difficulty": "Intermediate",
        "career_goal": "Machine Learning Engineer",
        "completed_courses": "Python for Data Analysis, Linear Algebra"
    },
    {
        "name": "Priya Patel",
        "dept": "Information Technology",
        "degree": "B.Tech (4-Year)",
        "batch": "1st Year",
        "semester": 1,
        "domains": ["Cybersecurity", "Cloud Computing"],
        "difficulty": "Beginner",
        "career_goal": "Cloud Security Architect",
        "completed_courses": ""
    },
    {
        "name": "Rohan Verma",
        "dept": "Electronics & Communication",
        "degree": "B.Tech (4-Year)",
        "batch": "2nd Year",
        "semester": 4,
        "domains": ["Programming", "Web Development"],
        "difficulty": "Intermediate",
        "career_goal": "Full Stack Developer",
        "completed_courses": "C++ Programming, Digital Logic"
    },
    {
        "name": "Ananya Iyer",
        "dept": "Computer Applications",
        "degree": "B.Sc / BCA (3-Year)",
        "batch": "3rd Year",
        "semester": 6,
        "domains": ["Web Development", "UI/UX Design"],
        "difficulty": "Advanced",
        "career_goal": "Frontend Architect",
        "completed_courses": "HTML/CSS Basics, JavaScript Fundamentals"
    }
]

print("Executing 4 Cohort Experiments on SmartRecSys Engine...")
experiment_data = []
for c_idx, c_prof in enumerate(cohorts, 1):
    res = run_cohort(c_idx, c_prof)
    experiment_data.append(res)
    print(f"\nCohort {c_idx}: {c_prof['name']} ({c_prof['dept']}) -> Top Match: {res['recommendations'][0]['title']} ({res['recommendations'][0]['score']}%)")

out_file = "experiments/cohort_results.json"
with open(out_file, "w") as f:
    json.dump(experiment_data, f, indent=2)

print(f"\n✅ All 4 cohorts executed successfully! Results saved to '{out_file}'.")
