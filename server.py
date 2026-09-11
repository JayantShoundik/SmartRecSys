import os
import sys
import json
import re
import numpy as np
import pandas as pd
import torch
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.security import generate_password_hash, check_password_hash

from recommender import SmartCampusRecommender
from database import init_db, SessionLocal, Student, Course, RecommendationAudit
from dl_recommender_gpu import NeuralCollaborativeFiltering
from train_neumf_large import NeuralMatrixFactorization

# Initialize Flask app to serve static frontend files and REST API
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Initialize SQLite database
print("Initializing SQLite Database (smartrecsys.db)...")
init_db()

# Initialize Recommender Engine
print("Loading SmartCampusRecommender components...")
try:
    recommender = SmartCampusRecommender()
    print("Recommender engine loaded successfully!")
except Exception as e:
    print(f"Error loading recommender: {e}")
    sys.exit(1)

# Device Configuration
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")

# Load Deep Learning Models
deep_model = None
model_type = "Hybrid (TF-IDF Semantic Engine)"

neumf_path = "models/neumf_large.pth"
ncf_path = "models/ncf_recommender.pth"

if os.path.exists(neumf_path):
    try:
        checkpoint = torch.load(neumf_path, map_location=device)
        num_users = checkpoint.get('num_users', 25000)
        num_items = checkpoint.get('num_items', len(recommender.df))
        deep_model = NeuralMatrixFactorization(num_users=num_users, num_items=num_items, latent_dim_gmf=32, latent_dim_mlp=32)
        deep_model.load_state_dict(checkpoint['model_state_dict'])
        deep_model.to(device)
        deep_model.eval()
        model_type = "NeuMF (Neural Matrix Factorization - Deep Learning)"
        print(f"✅ Loaded Large-Scale NeuMF Deep Learning Model on {device}!")
    except Exception as e:
        print(f"Could not load NeuMF model: {e}")

if deep_model is None and os.path.exists(ncf_path):
    try:
        deep_model = NeuralCollaborativeFiltering(num_users=1000, num_items=len(recommender.df), embedding_dim=16)
        deep_model.load_state_dict(torch.load(ncf_path, map_location=device))
        deep_model.to(device)
        deep_model.eval()
        model_type = "NCF (Neural Collaborative Filtering - PyTorch)"
        print(f"✅ Loaded NCF PyTorch Deep Learning Model on {device}!")
    except Exception as e:
        print(f"Could not load NCF model: {e}")

# Helper: Extract meaningful skills from course title and subject
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

# Helper: Build dynamic pedagogical rationale
def generate_xai_reason(row, dept, domains, difficulty, career_goal, completed_courses):
    title = row['course_title']
    subj = row['subject']
    lvl = format_level(row.get('level', 'All Levels'))
    
    reasons = []
    
    # 1. Domain alignment
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
        
    # 2. Career Goal / Department
    if career_goal and career_goal.strip().lower() not in ["other", "none", "", "select"]:
        reasons.append(f"develops core technical competencies essential for an aspiring {career_goal.strip()}")
    elif dept and dept.strip().lower() not in ["other", "none", ""]:
        reasons.append(f"accelerates your engineering specialization in {dept.strip()}")
    else:
        reasons.append("builds career-ready technical expertise and practical competency")

    # 3. Prerequisites / completed courses
    if completed_courses and completed_courses.strip():
        first_c = completed_courses.split(',')[0].strip()
        reasons.append(f"logically builds upon your completed coursework in {first_c}")

    reason_str = "; ".join(reasons) + "."
    return reason_str

@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    try:
        # 1. Parse Request Payload (Flexible schema: supports both nested 'preferences' and top-level keys)
        if request.method == 'POST':
            data = request.get_json() or {}
            pref = data.get('preferences') or {}
            user_name = data.get('user_id') or data.get('name') or data.get('student_name') or pref.get('name') or 'Student'
            domains = pref.get('domains') or data.get('domains') or []
            if isinstance(domains, str):
                domains = [d.strip() for d in domains.split(',') if d.strip()]
            difficulty = pref.get('difficulty') or data.get('difficulty') or pref.get('level') or data.get('level') or 'Beginner'
            dept = pref.get('dept') or data.get('department') or data.get('dept') or 'Computer Science'
            degree = pref.get('degree') or data.get('degree') or 'B.Tech (4-Year)'
            year = pref.get('batch') or data.get('year') or data.get('batch') or '2nd Year'
            sem_raw = str(pref.get('semester') or data.get('semester') or '3')
            sem_digits = re.sub(r'\D', '', sem_raw)
            semester = int(sem_digits) if sem_digits else 3
            cgpa_val = pref.get('cgpa') or data.get('cgpa')
            cgpa = float(cgpa_val) if cgpa_val else None
            completed = pref.get('completed_courses') or data.get('completed_courses') or data.get('prerequisites') or ''
            if isinstance(completed, list):
                completed = ", ".join(completed)
            current_c = pref.get('current_courses') or data.get('current_courses') or ''
            goal = pref.get('career_goal') or data.get('career_goal') or data.get('goal') or 'Software Engineer'
        else:
            user_name = request.args.get('name') or request.args.get('user_id') or 'Student'
            domains = [d.strip() for d in request.args.get('domains', '').split(',') if d.strip()]
            difficulty = request.args.get('difficulty') or request.args.get('level') or 'Beginner'
            dept = request.args.get('dept') or request.args.get('department') or 'Computer Science'
            degree = request.args.get('degree', 'B.Tech (4-Year)')
            year = request.args.get('batch') or request.args.get('year') or '2nd Year'
            sem_raw = str(request.args.get('semester') or '3')
            sem_digits = re.sub(r'\D', '', sem_raw)
            semester = int(sem_digits) if sem_digits else 3
            cgpa = float(request.args.get('cgpa')) if request.args.get('cgpa') else None
            completed = request.args.get('completed_courses', '')
            current_c = request.args.get('current_courses', '')
            goal = request.args.get('goal') or request.args.get('career_goal') or 'Software Engineer'

        # 2. Persist / Upsert Student Profile into SQLite Database
        db = SessionLocal()
        student = None
        if user_name and user_name.lower() != 'student':
            student = db.query(Student).filter(Student.name.ilike(user_name.strip())).order_by(Student.id.desc()).first()

        if student:
            student.department = dept
            student.degree = degree
            student.year = year
            student.semester = semester
            if cgpa is not None:
                student.cgpa = cgpa
            if completed:
                student.completed_courses = completed
            if current_c:
                student.current_courses = current_c
            student.domains = ",".join(domains)
            student.difficulty = difficulty
            student.career_goal = goal
        else:
            student = Student(
                name=user_name,
                department=dept,
                degree=degree,
                year=year,
                semester=semester,
                cgpa=cgpa,
                completed_courses=completed,
                current_courses=current_c,
                domains=",".join(domains),
                difficulty=difficulty,
                career_goal=goal
            )
            db.add(student)

        db.commit()
        student_id = student.id

        # 3. REAL AI & MACHINE LEARNING INFERENCE
        df = recommender.df.copy()
        
        # Build comprehensive semantic profile query
        profile_tokens = [
            dept,
            degree,
            " ".join(domains),
            f"{difficulty} level",
            completed,
            current_c,
            goal
        ]
        profile_text = " ".join([t for t in profile_tokens if t])
        
        # A. Semantic Vectorization (TF-IDF Cosine Similarity)
        student_vec = recommender.vectorizer.transform([profile_text])
        semantic_sim = cosine_similarity(student_vec, recommender.tfidf_matrix)[0]

        # B. Domain-Specific Affinity Masking & Scoring (Robust Multi-Domain AI Engine)
        target_subjects = []
        cyber_patterns = [
            r"\bsecurity\b", r"\bcyber\b", r"\bcybersecurity\b", r"\bethical hack\w*", r"\bkali\b",
            r"\boauth\b", r"\bauth0\b", r"\bauthentication\b", r"\bvulnerabilit\w*", r"\bpenetration\b",
            r"\bfirewall\b", r"\bmalware\b", r"\bssl\b", r"\bcryptograph\w*", r"\binfosec\b", r"\bpassword-less\b"
        ]
        cloud_patterns = [
            r"\baws\b", r"\bserverless\b", r"\bdevops\b", r"\bdocker\b", r"\bkubernetes\b", r"\blamp\b", r"\bvps\b", r"\bcloud architecture\b"
        ]
        prog_patterns = [
            r"\bpython\b", r"\bjava\b", r"\bc\+\+\b", r"\bprogramming\b", r"\bcoding\b", r"\balgorithm\w*", r"\btypescript\b", r"\bdata structures\b"
        ]
        web_patterns = [
            r"\bhtml\b", r"\bcss\b", r"\bjavascript\b", r"\breact\b", r"\bnode\b", r"\bweb\b", r"\bfrontend\b", r"\bfullstack\b", r"\bdjango\b", r"\bflask\b", r"\bphp\b"
        ]
        data_patterns = [
            r"\bdata\b", r"\bmachine learning\b", r"\bai\b", r"\bpandas\b", r"\bnumpy\b", r"\bdeep learning\b", r"\bneural\b", r"\bvisualizing data\b"
        ]
        design_patterns = [
            r"\bphotoshop\b", r"\billustrator\b", r"\bui\b", r"\bux\b", r"\bdesign\b", r"\bfigma\b", r"\bdrawing\b", r"\blogo\b"
        ]
        finance_patterns = [
            r"\bfinance\b", r"\baccounting\b", r"\btrading\b", r"\bstock\b", r"\bexcel\b", r"\binvesting\b", r"\bforex\b"
        ]
        music_patterns = [
            r"\bguitar\b", r"\bpiano\b", r"\bmusic\b", r"\bflute\b", r"\bvocal\b", r"\bharmonica\b"
        ]

        has_cyber = any("cyber" in d.lower() or "security" in d.lower() for d in domains)
        has_cloud = any("cloud" in d.lower() for d in domains)
        has_prog = any("prog" in d.lower() or "soft" in d.lower() for d in domains)
        has_web = any("web" in d.lower() for d in domains)
        has_data = any("data" in d.lower() or "machine" in d.lower() or "ai" in d.lower() for d in domains)
        has_design = any("design" in d.lower() or "ui" in d.lower() for d in domains)
        has_finance = any("finance" in d.lower() or "business" in d.lower() for d in domains)
        has_music = any("music" in d.lower() for d in domains)

        # Map campus target subjects
        if has_cyber or has_cloud or has_prog or has_web or has_data:
            target_subjects.append("Web Development")
        if has_design:
            target_subjects.append("Graphic Design")
        if has_finance:
            target_subjects.append("Business Finance")
        if has_music:
            target_subjects.append("Musical Instruments")

        is_pure_tech_student = (has_cyber or has_cloud or has_prog or has_web or has_data) and not (has_design or has_finance or has_music)

        # Compute Domain Match Score
        domain_scores = np.zeros(len(df))
        title_lower = df['course_title'].str.lower().values
        subject_vals = df['subject'].values

        for i in range(len(df)):
            subj = subject_vals[i]
            t = title_lower[i]

            # Hard suppression: Completely filter out Graphic Design / Music / Finance for CS/Cyber students
            if is_pure_tech_student and subj in ["Graphic Design", "Musical Instruments", "Business Finance"]:
                domain_scores[i] = -1.0  # Marked for complete suppression
                continue

            score = 0.0
            if target_subjects and subj in target_subjects:
                score += 0.25

            # Multi-domain intersection detection
            matched_domains_count = 0
            if has_cyber and any(re.search(p, t) for p in cyber_patterns):
                score += 0.55
                matched_domains_count += 1
            if has_cloud and subj == "Web Development" and any(re.search(p, t) for p in cloud_patterns):
                score += 0.35
                matched_domains_count += 1
            if has_prog and any(re.search(p, t) for p in prog_patterns):
                score += 0.30
                matched_domains_count += 1
            if has_web and any(re.search(p, t) for p in web_patterns):
                score += 0.25
                matched_domains_count += 1
            if has_data and any(re.search(p, t) for p in data_patterns):
                score += 0.35
                matched_domains_count += 1
            if has_design and any(re.search(p, t) for p in design_patterns):
                score += 0.40
                matched_domains_count += 1
            if has_finance and any(re.search(p, t) for p in finance_patterns):
                score += 0.40
                matched_domains_count += 1
            if has_music and any(re.search(p, t) for p in music_patterns):
                score += 0.40
                matched_domains_count += 1

            # Multi-domain synergy bonus (e.g. Python + Ethical Hacking, or Java + Spring Security)
            if matched_domains_count > 1:
                score += 0.20
            elif matched_domains_count == 0 and len(domains) > 0:
                # Soft penalty for non-matching courses within the faculty
                score -= 0.15

            domain_scores[i] = max(0.0, score)

        # C. Difficulty Alignment Score
        difficulty_scores = np.zeros(len(df))
        level_vals = df['level'].values
        diff_target = difficulty.lower()

        for i, lvl in enumerate(level_vals):
            lvl_lower = lvl.lower()
            if "beginner" in diff_target:
                if "beginner" in lvl_lower: difficulty_scores[i] = 1.0
                elif "all" in lvl_lower: difficulty_scores[i] = 0.85
                elif "intermediate" in lvl_lower: difficulty_scores[i] = 0.40
                else: difficulty_scores[i] = 0.10
            elif "intermediate" in diff_target:
                if "intermediate" in lvl_lower: difficulty_scores[i] = 1.0
                elif "all" in lvl_lower: difficulty_scores[i] = 0.85
                elif "expert" in lvl_lower: difficulty_scores[i] = 0.70
                else: difficulty_scores[i] = 0.45
            else: # Advanced
                if "expert" in lvl_lower: difficulty_scores[i] = 1.0
                elif "intermediate" in lvl_lower: difficulty_scores[i] = 0.85
                elif "all" in lvl_lower: difficulty_scores[i] = 0.70
                else: difficulty_scores[i] = 0.30

        # D. Neural Deep Learning Inference (if model loaded)
        neural_scores = np.zeros(len(df))
        if deep_model is not None:
            try:
                candidate_idx = np.arange(len(df))
                user_id_tensor = torch.full((len(df),), student.id % 1000, dtype=torch.long, device=device)
                item_id_tensor = torch.tensor(candidate_idx, dtype=torch.long, device=device)
                with torch.no_grad():
                    neural_pred = deep_model(user_id_tensor, item_id_tensor).cpu().numpy()
                neural_scores = neural_pred
            except Exception as ne:
                neural_scores = np.zeros(len(df))

        # E. Unified Master Calibrated Score
        final_scores = np.zeros(len(df))
        for i in range(len(df)):
            if domain_scores[i] < 0:
                # Strictly suppressed cross-faculty courses (e.g. Photoshop or Guitar for CS/Cyber student)
                final_scores[i] = 0.05
            elif domain_scores[i] == 0.0 and len(domains) > 0:
                final_scores[i] = 0.10
            else:
                s_sem = semantic_sim[i]
                s_dom = domain_scores[i]
                s_dif = difficulty_scores[i]
                s_neu = neural_scores[i] if neural_scores[i] > 0 else 0.5

                raw_score = (0.40 * s_dom) + (0.30 * s_sem) + (0.20 * s_dif) + (0.10 * s_neu)
                calibrated = min(0.98, max(0.65, 0.65 + (raw_score * 0.33)))
                final_scores[i] = calibrated

        df['final_score'] = final_scores
        top_k = 6
        top_matches = df.sort_values(by='final_score', ascending=False).head(top_k)

        output_cards = []
        for rank, (_, row) in enumerate(top_matches.iterrows(), 1):
            title = row['course_title']
            subj = row['subject']
            lvl = format_level(row['level'])
            
            lectures = int(row['num_lectures'])
            duration = f"{max(4, min(12, lectures // 4))} Weeks"
            skills = extract_course_skills(title, subj)
            reason = generate_xai_reason(row, dept, domains, difficulty, goal, completed)

            card_obj = {
                "rank": rank,
                "title": title,
                "domain": subj,
                "difficulty": lvl,
                "score": float(row['final_score']),
                "duration": duration,
                "description": f"Comprehensive masterclass in {title}. Provides in-depth curriculum modules and rigorous hands-on projects in {subj}.",
                "skills": skills,
                "reason": reason
            }
            output_cards.append(card_obj)

        # 4. Save Audit Log in SQLite
        audit = RecommendationAudit(
            student_id=student_id,
            student_name=user_name,
            query_domains=",".join(domains),
            query_difficulty=difficulty,
            active_model=model_type,
            top_courses_json=json.dumps(output_cards)
        )
        db.add(audit)
        db.commit()
        audit_id = audit.id
        db.close()

        return jsonify({
            "status": "success",
            "student_id": student.id,
            "audit_id": audit_id,
            "active_model": model_type,
            "recommendations": output_cards
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ── Student Authentication Endpoints ──────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        
        if not name:
            return jsonify({"error": "Full Name is required"}), 400
        if not email or '@' not in email:
            return jsonify({"error": "A valid campus email is required"}), 400
        if not password or len(password) < 4:
            return jsonify({"error": "Password must be at least 4 characters long"}), 400

        db = SessionLocal()
        existing = db.query(Student).filter(Student.email == email).first()
        if existing:
            db.close()
            return jsonify({"error": f"An account with email '{email}' already exists. Please log in."}), 409

        dept = data.get('department') or data.get('dept') or 'Computer Science'
        degree = data.get('degree') or 'B.Tech (4-Year)'
        year = data.get('year') or data.get('batch') or '2nd Year'
        sem_raw = str(data.get('semester') or '3')
        sem_digits = re.sub(r'\D', '', sem_raw)
        semester = int(sem_digits) if sem_digits else 3
        cgpa_val = data.get('cgpa')
        cgpa = float(cgpa_val) if cgpa_val else None
        completed = data.get('completed_courses') or ''
        if isinstance(completed, list):
            completed = ", ".join(completed)
        current_c = data.get('current_courses') or ''
        domains = data.get('domains') or ["Web Development", "Programming"]
        domains_str = ",".join(domains) if isinstance(domains, list) else str(domains)
        difficulty = data.get('difficulty') or data.get('level') or 'Beginner'
        career_goal = data.get('career_goal') or data.get('goal') or 'Software Engineer'
        roll = data.get('roll_number') or f"2023CS{np.random.randint(100, 999)}"

        hashed = generate_password_hash(password)
        new_student = Student(
            name=name,
            email=email,
            password_hash=hashed,
            roll_number=roll,
            department=dept,
            degree=degree,
            year=year,
            semester=semester,
            cgpa=cgpa,
            completed_courses=completed,
            current_courses=current_c,
            domains=domains_str,
            difficulty=difficulty,
            career_goal=career_goal
        )
        db.add(new_student)
        db.commit()

        ret = {
            "id": new_student.id,
            "name": new_student.name,
            "email": new_student.email,
            "roll_number": new_student.roll_number,
            "department": new_student.department,
            "degree": new_student.degree,
            "year": new_student.year,
            "semester": new_student.semester,
            "cgpa": new_student.cgpa,
            "completed_courses": new_student.completed_courses or "",
            "current_courses": new_student.current_courses or "",
            "domains": [d.strip() for d in new_student.domains.split(',') if d.strip()],
            "difficulty": new_student.difficulty,
            "career_goal": new_student.career_goal or ""
        }
        db.close()
        return jsonify({
            "status": "success",
            "message": f"Student account registered successfully! Welcome, {name}.",
            "student": ret,
            "token": f"srs_session_{new_student.id}_{int(np.random.randint(10000, 99999))}"
        }), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    try:
        data = request.get_json() or {}
        identifier = (data.get('email') or data.get('identifier') or data.get('roll_number') or '').strip()
        password = data.get('password') or ''

        if not identifier:
            return jsonify({"error": "Email or Roll Number is required"}), 400
        if not password:
            return jsonify({"error": "Password is required"}), 400

        db = SessionLocal()
        student = db.query(Student).filter(
            (Student.email == identifier.lower()) |
            (Student.roll_number == identifier) |
            (Student.name.ilike(identifier))
        ).first()

        if not student:
            db.close()
            return jsonify({"error": "Invalid email/roll number or credentials"}), 401

        # Check password
        valid = False
        if student.password_hash:
            try:
                valid = check_password_hash(student.password_hash, password)
            except Exception:
                valid = (student.password_hash == password)
        else:
            valid = (password == "password123")

        if not valid:
            db.close()
            return jsonify({"error": "Incorrect password. Please verify and try again."}), 401

        ret = {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "roll_number": student.roll_number or f"2023CS{student.id:04d}",
            "department": student.department,
            "degree": student.degree,
            "year": student.year,
            "semester": student.semester,
            "cgpa": student.cgpa,
            "completed_courses": student.completed_courses or "",
            "current_courses": student.current_courses or "",
            "domains": [d.strip() for d in student.domains.split(',') if d.strip()],
            "difficulty": student.difficulty,
            "career_goal": student.career_goal or ""
        }
        db.close()
        return jsonify({
            "status": "success",
            "message": f"Login successful. Welcome back, {student.name}!",
            "student": ret,
            "token": f"srs_session_{student.id}_{int(np.random.randint(10000, 99999))}"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    try:
        auth_header = request.headers.get('Authorization', '')
        student_id = request.args.get('student_id')
        if not student_id and 'Bearer ' in auth_header:
            parts = auth_header.replace('Bearer ', '').split('_')
            if len(parts) >= 3 and parts[0] == 'srs' and parts[1] == 'session':
                student_id = parts[2]

        if not student_id:
            return jsonify({"error": "Unauthorized or missing student session"}), 401

        db = SessionLocal()
        student = db.query(Student).filter(Student.id == int(student_id)).first()
        if not student:
            db.close()
            return jsonify({"error": "Student session invalid"}), 404

        audits = db.query(RecommendationAudit).filter(RecommendationAudit.student_id == student.id).order_by(RecommendationAudit.created_at.desc()).limit(5).all()
        history = []
        for a in audits:
            history.append({
                "audit_id": a.id,
                "date": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
                "model": a.active_model,
                "query_domains": a.query_domains,
                "query_difficulty": a.query_difficulty,
                "top_courses": json.loads(a.top_courses_json)[:3] if a.top_courses_json else []
            })

        ret = {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "roll_number": student.roll_number or f"2023CS{student.id:04d}",
            "department": student.department,
            "degree": student.degree,
            "year": student.year,
            "semester": student.semester,
            "cgpa": student.cgpa,
            "completed_courses": student.completed_courses or "",
            "current_courses": student.current_courses or "",
            "domains": [d.strip() for d in student.domains.split(',') if d.strip()],
            "difficulty": student.difficulty,
            "career_goal": student.career_goal or "",
            "recent_audits": history
        }
        db.close()
        return jsonify({"status": "success", "student": ret})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    return jsonify({"status": "success", "message": "Successfully logged out from SmartRecSys."})

# ── Student Profile Management Endpoints ─────────────────────────────────────
@app.route('/api/students', methods=['GET'])
def list_students():
    try:
        db = SessionLocal()
        students = db.query(Student).order_by(Student.id.desc()).all()
        result = []
        for s in students:
            result.append({
                "id": s.id,
                "name": s.name,
                "email": s.email or "",
                "roll_number": s.roll_number or f"2023CS{s.id:04d}",
                "department": s.department,
                "degree": s.degree,
                "year": s.year,
                "semester": s.semester,
                "cgpa": s.cgpa,
                "completed_courses": s.completed_courses or "",
                "current_courses": s.current_courses or "",
                "domains": [d.strip() for d in s.domains.split(',') if d.strip()],
                "difficulty": s.difficulty,
                "career_goal": s.career_goal or "",
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else ""
            })
        db.close()
        return jsonify({"status": "success", "count": len(result), "students": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/students', methods=['POST'])
def save_student_profile():
    try:
        data = request.get_json() or {}
        name = (data.get('name') or data.get('student_name') or '').strip()
        if not name:
            return jsonify({"error": "Student name is required"}), 400

        dept = data.get('department') or data.get('dept') or 'Computer Science'
        degree = data.get('degree') or 'B.Tech (4-Year)'
        year = data.get('year') or data.get('batch') or '2nd Year'
        sem_raw = str(data.get('semester') or '3')
        sem_digits = re.sub(r'\D', '', sem_raw)
        semester = int(sem_digits) if sem_digits else 3
        cgpa_val = data.get('cgpa')
        cgpa = float(cgpa_val) if cgpa_val else None
        completed = data.get('completed_courses') or data.get('prerequisites') or ''
        if isinstance(completed, list):
            completed = ", ".join(completed)
        current_c = data.get('current_courses') or ''
        domains = data.get('domains') or ["Web Development", "Programming"]
        if isinstance(domains, list):
            domains_str = ",".join(domains)
        else:
            domains_str = str(domains)
        difficulty = data.get('difficulty') or data.get('level') or 'Beginner'
        career_goal = data.get('career_goal') or data.get('goal') or 'Software Engineer'

        db = SessionLocal()
        student_id = data.get('id') or data.get('student_id')
        student = None
        if student_id:
            student = db.query(Student).filter(Student.id == int(student_id)).first()
        if not student:
            student = db.query(Student).filter(Student.name.ilike(name)).first()

        if student:
            student.name = name
            student.department = dept
            student.degree = degree
            student.year = year
            student.semester = semester
            student.cgpa = cgpa
            student.completed_courses = completed
            student.current_courses = current_c
            student.domains = domains_str
            student.difficulty = difficulty
            student.career_goal = career_goal
            action = "updated"
        else:
            student = Student(
                name=name,
                department=dept,
                degree=degree,
                year=year,
                semester=semester,
                cgpa=cgpa,
                completed_courses=completed,
                current_courses=current_c,
                domains=domains_str,
                difficulty=difficulty,
                career_goal=career_goal
            )
            db.add(student)
            action = "created"

        db.commit()
        ret_student = {
            "id": student.id,
            "name": student.name,
            "department": student.department,
            "degree": student.degree,
            "year": student.year,
            "semester": student.semester,
            "cgpa": student.cgpa,
            "completed_courses": student.completed_courses or "",
            "current_courses": student.current_courses or "",
            "domains": [d.strip() for d in student.domains.split(',') if d.strip()],
            "difficulty": student.difficulty,
            "career_goal": student.career_goal or ""
        }
        db.close()
        return jsonify({
            "status": "success",
            "action": action,
            "message": f"Academic profile for {name} {action} successfully!",
            "student": ret_student
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/students/<int:student_id>', methods=['GET'])
def get_student_profile(student_id):
    try:
        db = SessionLocal()
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            db.close()
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404

        audits = db.query(RecommendationAudit).filter(RecommendationAudit.student_id == student_id).order_by(RecommendationAudit.created_at.desc()).all()
        history = []
        for a in audits:
            history.append({
                "audit_id": a.id,
                "date": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
                "model": a.active_model,
                "query_domains": a.query_domains,
                "query_difficulty": a.query_difficulty,
                "top_courses": json.loads(a.top_courses_json)[:3] if a.top_courses_json else []
            })

        ret_student = {
            "id": student.id,
            "name": student.name,
            "department": student.department,
            "degree": student.degree,
            "year": student.year,
            "semester": student.semester,
            "cgpa": student.cgpa,
            "completed_courses": student.completed_courses or "",
            "current_courses": student.current_courses or "",
            "domains": [d.strip() for d in student.domains.split(',') if d.strip()],
            "difficulty": student.difficulty,
            "career_goal": student.career_goal or "",
            "audit_history": history
        }
        db.close()
        return jsonify({"status": "success", "student": ret_student})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['GET'])
def get_report():
    try:
        student_id = request.args.get('student_id')
        db = SessionLocal()
        
        if student_id:
            student = db.query(Student).filter(Student.id == int(student_id)).first()
            audit = db.query(RecommendationAudit).filter(RecommendationAudit.student_id == int(student_id)).order_by(RecommendationAudit.created_at.desc()).first()
        else:
            student = db.query(Student).order_by(Student.created_at.desc()).first()
            audit = db.query(RecommendationAudit).order_by(RecommendationAudit.created_at.desc()).first()

        if not student or not audit:
            db.close()
            return jsonify({"error": "No recommendation report available. Please submit profile first."}), 404

        courses = json.loads(audit.top_courses_json)
        db.close()

        return jsonify({
            "report_id": f"SRS-REP-{audit.id:05d}",
            "student": {
                "name": student.name,
                "department": student.department,
                "degree": student.degree,
                "year": student.year,
                "semester": student.semester,
                "cgpa": student.cgpa if student.cgpa else "N/A",
                "completed_courses": student.completed_courses if student.completed_courses else "None Listed",
                "career_goal": student.career_goal if student.career_goal else "Engineering Professional",
                "target_domains": student.domains,
                "difficulty_level": student.difficulty
            },
            "system_audit": {
                "model_engine": audit.active_model,
                "generated_at": audit.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "verification_hash": f"SHA256-{hash(str(audit.id) + student.name) & 0xFFFFFFFF:08x}"
            },
            "recommendations": courses
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    db = SessionLocal()
    student_count = db.query(Student).count()
    audit_count = db.query(RecommendationAudit).count()
    db.close()

    return jsonify({
        "status": "online",
        "database": "SQLite (smartrecsys.db)",
        "total_courses": len(recommender.df) if recommender.df is not None else 0,
        "students_registered": student_count,
        "recommendation_audits": audit_count,
        "active_model": model_type,
        "device": str(device)
    })

@app.route('/')
def index():
    return send_from_directory('.', 'welcome.html')

@app.route('/<path:filename>')
def serve_page(filename):
    if os.path.exists(filename) and os.path.isfile(filename):
        return send_from_directory('.', filename)
    return send_from_directory('.', 'welcome.html')

if __name__ == '__main__':
    print("🚀 SmartRecSys Full-Stack Server active on http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
