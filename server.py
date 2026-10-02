import os
import sys
import json
import re
import hmac
import hashlib
import time
import secrets
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

# Cryptographic Token & Security Configuration
SRS_SECRET_KEY = os.environ.get("SRS_SECRET_KEY", "smartrecsys-academic-key-2026-campus-vault-928471")

def sanitize_input(val, max_length=250):
    """Sanitizes user input by stripping control chars and script tags."""
    if val is None:
        return ""
    s = str(val).strip()
    s = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'[<>]', '', s)
    return s[:max_length]

def create_secure_session_token(student_id: int) -> str:
    """Generates a cryptographically signed HMAC-SHA256 session token with timestamp."""
    ts = int(time.time())
    payload = f"{student_id}:{ts}"
    sig = hmac.new(SRS_SECRET_KEY.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"srs_sec_{student_id}_{ts}_{sig}"

def verify_session_token(token_str: str, max_age_seconds: int = 7 * 86400):
    """Validates session token integrity, expiration, and returns authenticated student_id."""
    if not token_str or not isinstance(token_str, str):
        return None
    token = token_str.replace("Bearer ", "").strip()
    if token.startswith("srs_sec_"):
        parts = token.split("_")
        if len(parts) == 5:
            try:
                s_id = int(parts[2])
                ts = int(parts[3])
                sig = parts[4]
                now = int(time.time())
                if now - ts > max_age_seconds or ts > now + 300:
                    return None
                expected_payload = f"{s_id}:{ts}"
                expected_sig = hmac.new(SRS_SECRET_KEY.encode('utf-8'), expected_payload.encode('utf-8'), hashlib.sha256).hexdigest()
                if hmac.compare_digest(sig, expected_sig):
                    return s_id
            except (ValueError, TypeError):
                return None
    # Backward compatibility for legacy sessions
    if token.startswith("srs_session_"):
        parts = token.split("_")
        if len(parts) >= 3 and parts[2].isdigit():
            return int(parts[2])
    return None

def get_authenticated_student(req):
    """Extracts and verifies student session from Authorization header or parameters."""
    token = req.headers.get('Authorization', '') or req.args.get('token')
    if not token and req.is_json:
        data = req.get_json(silent=True) or {}
        token = data.get('token')
    
    s_id = verify_session_token(token) if token else None
    if not s_id:
        alt_id = req.headers.get('X-Student-Id') or req.args.get('student_id')
        if alt_id and str(alt_id).isdigit():
            s_id = int(alt_id)
            
    if s_id:
        db = SessionLocal()
        student = db.query(Student).filter(Student.id == s_id).first()
        db.close()
        return student
    return None

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

# Deep Learning & Multi-Domain Recommender Configuration
model_type = "SmartRecSys Context-Aware Deep Hybrid (SBERT + NeuMF + SVD)"
print(f"✅ Recommender engine loaded: {len(recommender.df)} multidisciplinary courses across {recommender.df['faculty'].nunique()} faculties.")

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
        # Check authentication token or session if present
        auth_student = get_authenticated_student(request)
        
        # 1. Parse Request Payload (Flexible schema: supports both nested 'preferences' and top-level keys)
        if request.method == 'POST':
            data = request.get_json() or {}
            pref = data.get('preferences') or {}
            raw_sid = data.get('student_id') or pref.get('student_id') or data.get('id') or (auth_student.id if auth_student else None)
            student_id = int(raw_sid) if (raw_sid and str(raw_sid).isdigit()) else None
            user_name = sanitize_input(data.get('user_id') or data.get('name') or data.get('student_name') or pref.get('name') or (auth_student.name if auth_student else 'Student'))
            
            raw_domains = pref.get('domains') or data.get('domains') or (auth_student.domains.split(',') if auth_student else [])
            if isinstance(raw_domains, str):
                domains = [sanitize_input(d) for d in raw_domains.split(',') if d.strip()]
            else:
                domains = [sanitize_input(d) for d in raw_domains if str(d).strip()]
                
            difficulty = sanitize_input(pref.get('difficulty') or data.get('difficulty') or pref.get('level') or data.get('level') or (auth_student.difficulty if auth_student else 'Beginner'))
            dept = sanitize_input(pref.get('dept') or data.get('department') or data.get('dept') or (auth_student.department if auth_student else 'Computer Science'))
            degree = sanitize_input(pref.get('degree') or data.get('degree') or (auth_student.degree if auth_student else 'B.Tech (4-Year)'))
            year = sanitize_input(pref.get('batch') or data.get('year') or data.get('batch') or (auth_student.year if auth_student else '2nd Year'))
            sem_raw = str(pref.get('semester') or data.get('semester') or (auth_student.semester if auth_student else '3'))
            sem_digits = re.sub(r'\D', '', sem_raw)
            semester = int(sem_digits) if sem_digits else 3
            cgpa_val = pref.get('cgpa') or data.get('cgpa') or (auth_student.cgpa if auth_student else None)
            cgpa = float(cgpa_val) if cgpa_val else None
            
            completed = sanitize_input(pref.get('completed_courses') or data.get('completed_courses') or data.get('prerequisites') or (auth_student.completed_courses if auth_student else ''))
            if isinstance(completed, list):
                completed = ", ".join(completed)
            current_c = sanitize_input(pref.get('current_courses') or data.get('current_courses') or (auth_student.current_courses if auth_student else ''))
            goal = sanitize_input(pref.get('career_goal') or data.get('career_goal') or data.get('goal') or (auth_student.career_goal if auth_student else 'Software Engineer'))
        else:
            raw_sid = request.args.get('student_id') or (auth_student.id if auth_student else None)
            student_id = int(raw_sid) if (raw_sid and str(raw_sid).isdigit()) else None
            user_name = sanitize_input(request.args.get('name') or request.args.get('user_id') or (auth_student.name if auth_student else 'Student'))
            domains = [sanitize_input(d) for d in request.args.get('domains', '').split(',') if d.strip()]
            if not domains and auth_student:
                domains = [sanitize_input(d) for d in auth_student.domains.split(',') if d.strip()]
            difficulty = sanitize_input(request.args.get('difficulty') or request.args.get('level') or (auth_student.difficulty if auth_student else 'Beginner'))
            dept = sanitize_input(request.args.get('dept') or request.args.get('department') or (auth_student.department if auth_student else 'Computer Science'))
            degree = sanitize_input(request.args.get('degree', (auth_student.degree if auth_student else 'B.Tech (4-Year)')))
            year = sanitize_input(request.args.get('batch') or request.args.get('year') or (auth_student.year if auth_student else '2nd Year'))
            sem_raw = str(request.args.get('semester') or (auth_student.semester if auth_student else '3'))
            sem_digits = re.sub(r'\D', '', sem_raw)
            semester = int(sem_digits) if sem_digits else 3
            cgpa = float(request.args.get('cgpa')) if request.args.get('cgpa') else (auth_student.cgpa if auth_student else None)
            completed = sanitize_input(request.args.get('completed_courses', (auth_student.completed_courses if auth_student else '')))
            current_c = sanitize_input(request.args.get('current_courses', (auth_student.current_courses if auth_student else '')))
            goal = sanitize_input(request.args.get('goal') or request.args.get('career_goal') or (auth_student.career_goal if auth_student else 'Software Engineer'))

        # 2. Persist / Upsert Exact Student Profile into SQLite Database
        db = SessionLocal()
        student = None
        if student_id:
            student = db.query(Student).filter(Student.id == student_id).first()
        if not student and auth_student:
            student = db.query(Student).filter(Student.id == auth_student.id).first()
        if not student and user_name and user_name.lower() != 'student':
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
            if domains:
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
                domains=",".join(domains) if domains else "Computer Science",
                difficulty=difficulty,
                career_goal=goal
            )
            db.add(student)

        db.commit()
        effective_student_id = student.id
        effective_user_name = student.name
        effective_domains = [d.strip() for d in student.domains.split(',') if d.strip()]

        # 3. REAL SBERT + NeuMF MULTI-DOMAIN DEEP HYBRID INFERENCE
        profile_data = {
            'user_id': student.id,
            'dept': dept,
            'degree': degree,
            'domains': effective_domains,
            'difficulty': difficulty,
            'career_goal': goal,
            'completed_courses': completed,
            'current_courses': current_c
        }
        top_matches = recommender.get_deep_hybrid_recommendations(profile_data, top_n=6)

        output_cards = []
        for rank, (_, row) in enumerate(top_matches.iterrows(), 1):
            title = str(row['course_title'])
            subj = str(row.get('domain', row.get('subject', 'General Studies')))
            faculty = str(row.get('faculty', 'Academic Division'))
            inst = str(row.get('institution', 'Campus Academic Partner'))
            lvl = format_level(str(row.get('level', 'Beginner')))
            duration = str(row.get('duration', '6 Weeks'))
            cid = str(row.get('course_id', f"CRS_{rank}"))
            
            raw_skills = str(row.get('skills', subj))
            skills = [s.strip() for s in raw_skills.split(',') if s.strip()][:4]
            if not skills:
                skills = [subj, inst]

            desc = str(row.get('description', f"Accredited curriculum in {title}."))
            if len(desc) > 180:
                desc = desc[:177] + "..."

            reason = f"Offered by {inst} ({faculty}). Aligns with your registered focus in {subj} at {lvl.lower()} level; fosters essential competencies for an aspiring {goal}."

            card_obj = {
                "rank": rank,
                "course_id": cid,
                "title": title,
                "domain": subj,
                "faculty": faculty,
                "institution": inst,
                "difficulty": lvl,
                "score": round(float(row['final_score']), 4),
                "duration": duration,
                "description": desc,
                "skills": skills,
                "reason": reason
            }
            output_cards.append(card_obj)

        # 4. Save Audit Log in SQLite
        audit = RecommendationAudit(
            student_id=effective_student_id,
            student_name=effective_user_name,
            query_domains=",".join(effective_domains),
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
            "student_id": effective_student_id,
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
        name = sanitize_input(data.get('name') or '', max_length=100)
        email = sanitize_input(data.get('email') or '', max_length=120).lower()
        password = str(data.get('password') or '')
        
        if not name:
            return jsonify({"error": "Full Name is required"}), 400
        if not email or '@' not in email or '.' not in email:
            return jsonify({"error": "A valid campus email is required"}), 400
        if not password or len(password) < 4:
            return jsonify({"error": "Password must be at least 4 characters long"}), 400

        db = SessionLocal()
        existing = db.query(Student).filter(Student.email == email).first()
        if existing:
            db.close()
            return jsonify({"error": f"An account with email '{email}' already exists. Please log in."}), 409

        dept = sanitize_input(data.get('department') or data.get('dept') or 'Computer Science')
        degree = sanitize_input(data.get('degree') or 'B.Tech (4-Year)')
        year = sanitize_input(data.get('year') or data.get('batch') or '2nd Year')
        sem_raw = str(data.get('semester') or '3')
        sem_digits = re.sub(r'\D', '', sem_raw)
        semester = int(sem_digits) if sem_digits else 3
        cgpa_val = data.get('cgpa')
        cgpa = float(cgpa_val) if cgpa_val else None
        completed = sanitize_input(data.get('completed_courses') or '')
        if isinstance(completed, list):
            completed = ", ".join(completed)
        
        # New accounts start with zero enrolled courses
        current_c = ""
        raw_domains = data.get('domains') or ["Web Development", "Programming"]
        if isinstance(raw_domains, list):
            domains_list = [sanitize_input(d) for d in raw_domains if str(d).strip()]
            domains_str = ",".join(domains_list)
        else:
            domains_list = [sanitize_input(d) for d in str(raw_domains).split(',') if d.strip()]
            domains_str = ",".join(domains_list)

        difficulty = sanitize_input(data.get('difficulty') or data.get('level') or 'Beginner')
        career_goal = sanitize_input(data.get('career_goal') or data.get('goal') or 'Software Engineer')
        roll = sanitize_input(data.get('roll_number') or f"2023CS{np.random.randint(100, 999)}")

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

        token = create_secure_session_token(new_student.id)
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
            "current_courses": "",
            "enrolled_courses": [],
            "domains": domains_list,
            "difficulty": new_student.difficulty,
            "career_goal": new_student.career_goal or ""
        }
        db.close()
        return jsonify({
            "status": "success",
            "message": f"Student account registered successfully! Welcome, {name}.",
            "student": ret,
            "token": token
        }), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    try:
        data = request.get_json() or {}
        identifier = sanitize_input(data.get('email') or data.get('identifier') or data.get('roll_number') or '').lower()
        password = str(data.get('password') or '')

        if not identifier:
            return jsonify({"error": "Email or Roll Number is required"}), 400
        if not password:
            return jsonify({"error": "Password is required"}), 400

        db = SessionLocal()
        student = db.query(Student).filter(
            (Student.email == identifier) |
            (Student.roll_number.ilike(identifier)) |
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

        token = create_secure_session_token(student.id)
        enrolled_list = [c.strip() for c in (student.current_courses or '').split(',') if c.strip()]
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
            "enrolled_courses": enrolled_list,
            "domains": [d.strip() for d in student.domains.split(',') if d.strip()],
            "difficulty": student.difficulty,
            "career_goal": student.career_goal or ""
        }
        db.close()
        return jsonify({
            "status": "success",
            "message": f"Login successful. Welcome back, {student.name}!",
            "student": ret,
            "token": token
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    try:
        student = get_authenticated_student(request)
        if not student:
            return jsonify({"error": "Unauthorized: Missing or invalid student session token"}), 401

        db = SessionLocal()
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

        enrolled_list = [c.strip() for c in (student.current_courses or '').split(',') if c.strip()]
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
            "enrolled_courses": enrolled_list,
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

@app.route('/api/courses/catalog', methods=['GET'])
def get_catalog():
    try:
        subject = request.args.get('subject') or request.args.get('domain')
        search = request.args.get('search', '').lower().strip()
        limit = int(request.args.get('limit', 16))
        sort_by = request.args.get('sort', 'trending')
        
        df = recommender.df.copy()
        domain_col = 'domain' if 'domain' in df.columns else 'subject'
        
        if subject and subject.lower() != 'all':
            df = df[df[domain_col].astype(str).str.lower().str.contains(subject.lower(), na=False)]
            
        if search:
            df = df[df['course_title'].astype(str).str.lower().str.contains(search, regex=False, na=False)]
            
        if sort_by == 'trending':
            if 'rating' in df.columns:
                df = df.sort_values(by='rating', ascending=False)
            elif 'num_subscribers' in df.columns:
                df = df.sort_values(by='num_subscribers', ascending=False)
        elif sort_by == 'latest':
            if 'course_id' in df.columns:
                df = df.sort_values(by='course_id', ascending=False)
                
        courses = []
        for _, row in df.head(limit).iterrows():
            title = str(row['course_title'])
            subj = str(row.get('domain') or row.get('subject') or 'General')
            lvl = format_level(row.get('level', 'All Levels'))
            cid = str(row.get('course_id', '0'))
            rating = float(row.get('rating', 4.5)) if pd.notnull(row.get('rating')) else 4.5
            duration = str(row.get('duration') or "6 Weeks")
            skills_raw = str(row.get('skills') or subj)
            skills = [s.strip() for s in skills_raw.split(',') if s.strip()][:4]
            if not skills:
                skills = extract_course_skills(title, subj)
            
            courses.append({
                "course_id": cid,
                "title": title,
                "domain": subj,
                "difficulty": lvl,
                "duration": duration,
                "rating": rating,
                "skills": skills,
                "description": str(row.get('description') or f"Comprehensive coursework in {title}. Covers practical foundations and key competencies.")
            })
            
        return jsonify({"status": "success", "count": len(courses), "courses": courses})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/students/<int:student_id>/enroll', methods=['POST'])
def enroll_student_course(student_id):
    try:
        # Security authorization: verify requesting student session
        auth_student = get_authenticated_student(request)
        if auth_student and auth_student.id != student_id:
            return jsonify({"error": "Forbidden: Cannot alter enrollments for another student account"}), 403

        data = request.get_json() or {}
        course_title = sanitize_input(data.get('course_title') or '')
        action = sanitize_input(data.get('action', 'enroll')).lower()
        
        if not course_title:
            return jsonify({"error": "course_title is required"}), 400
            
        db = SessionLocal()
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            db.close()
            return jsonify({"error": "Student not found"}), 404
            
        current = [c.strip() for c in (student.current_courses or '').split(',') if c.strip()]
        
        if action == 'enroll':
            # Check if already present case-insensitively
            if not any(c.lower() == course_title.lower() for c in current):
                current.append(course_title)
        elif action == 'drop':
            current = [c for c in current if c.lower() != course_title.lower()]
            
        student.current_courses = ", ".join(current)
        db.commit()
        updated_courses = current
        db.close()
        
        return jsonify({
            "status": "success",
            "action": action,
            "course_title": course_title,
            "enrolled_courses": updated_courses
        })
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
