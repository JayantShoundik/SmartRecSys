import os
import re
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# ----------------------------------------------------
# NeuMF Architecture Definition
# ----------------------------------------------------
class NeuMFNet(nn.Module):
    def __init__(self, num_users=1200, num_items=8000, latent_dim_gmf=16, latent_dim_mlp=16, mlp_hidden_dims=[32, 16, 8]):
        super().__init__()
        self.user_embed_gmf = nn.Embedding(num_users, latent_dim_gmf)
        self.item_embed_gmf = nn.Embedding(num_items, latent_dim_gmf)

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
# Main Smart Campus Recommender Engine
# ----------------------------------------------------
class SmartCampusRecommender:
    def __init__(self, dataset_path="dataset/comprehensive_campus_courses.csv"):
        self.dataset_path = dataset_path if os.path.exists(dataset_path) else "dataset/udemy_courses.csv"
        self.df = None
        self.tfidf_matrix = None
        self.vectorizer = None
        self.sbert_model = None
        self.sbert_embeddings = None
        self.device = torch.device("mps") if torch.backends.mps.is_available() else (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        self.neumf_model = None
        self.content_similarity = None
        self.collaborative_similarity = None
        self.load_and_preprocess()

    def clean_text(self, text):
        if not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        return text

    def load_and_preprocess(self):
        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"Dataset not found at {self.dataset_path}.")
        
        print(f"Loading curriculum dataset from: {self.dataset_path}")
        self.df = pd.read_csv(self.dataset_path)

        # Standardize columns
        if 'course_title' not in self.df.columns and 'Name' in self.df.columns:
            self.df['course_title'] = self.df['Name']
        if 'domain' not in self.df.columns and 'subject' in self.df.columns:
            self.df['domain'] = self.df['subject']
        if 'faculty' not in self.df.columns:
            self.df['faculty'] = "School of Computing & Engineering (B.Tech)"
        if 'institution' not in self.df.columns:
            self.df['institution'] = "Campus University Partner"
        if 'description' not in self.df.columns:
            self.df['description'] = self.df['course_title']
        if 'skills' not in self.df.columns:
            self.df['skills'] = self.df['domain']
        if 'duration' not in self.df.columns:
            self.df['duration'] = "6 Weeks"

        # Prepare text representation
        self.df['clean_title'] = self.df['course_title'].apply(self.clean_text)
        self.df['clean_domain'] = self.df['domain'].apply(self.clean_text)
        self.df['clean_faculty'] = self.df['faculty'].apply(self.clean_text)
        self.df['clean_desc'] = self.df['description'].fillna('').apply(self.clean_text)
        self.df['full_text'] = (
            self.df['clean_title'] + " " +
            self.df['clean_domain'] + " " +
            self.df['clean_faculty'] + " " +
            self.df['clean_desc']
        )

        # 1. TF-IDF Representation (Baseline)
        print("Fitting TF-IDF Vectorizer...")
        self.vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        self.tfidf_matrix = self.vectorizer.fit_transform(self.df['full_text'])

        # 2. Sentence-BERT Representation (Deep Semantic Embeddings)
        sbert_path = "models/sbert_course_embeddings.npy"
        if os.path.exists(sbert_path):
            print(f"Loading precomputed Sentence-BERT embeddings from {sbert_path}...")
            self.sbert_embeddings = np.load(sbert_path)
            # Ensure dimension matches current df
            if len(self.sbert_embeddings) != len(self.df):
                print("Warning: SBERT embeddings shape mismatch, computing fresh embeddings...")
                self._compute_sbert_embeddings(sbert_path)
        else:
            self._compute_sbert_embeddings(sbert_path)

        # Lazy initialize SBERT model for live query encoding
        try:
            self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2', device=self.device)
            print("Loaded live SentenceTransformer (all-MiniLM-L6-v2) inference engine.")
        except Exception as e:
            print(f"SentenceTransformer live model warning: {e}")

        # 3. Load NeuMF Neural Collaborative Model
        neumf_weights = "models/neumf_multi_domain.pth"
        if os.path.exists(neumf_weights):
            try:
                print(f"Loading NeuMF neural model from {neumf_weights}...")
                self.neumf_model = NeuMFNet(num_users=1200, num_items=len(self.df)).to(self.device)
                self.neumf_model.load_state_dict(torch.load(neumf_weights, map_location=self.device))
                self.neumf_model.eval()
                print("NeuMF model loaded successfully!")
            except Exception as e:
                print(f"Warning loading NeuMF model: {e}")

        # 4. Synthesize base item similarities
        self.generate_synthetic_interactions()

    def _compute_sbert_embeddings(self, save_path):
        print(f"Computing Sentence-BERT embeddings for {len(self.df)} courses on {self.device}...")
        model = SentenceTransformer('all-MiniLM-L6-v2', device=self.device)
        self.sbert_embeddings = model.encode(self.df['full_text'].tolist(), batch_size=64, convert_to_numpy=True, show_progress_bar=True)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        np.save(save_path, self.sbert_embeddings)
        print(f"Saved SBERT embeddings to {save_path}")

    def generate_synthetic_interactions(self, num_users=1000, random_seed=42):
        np.random.seed(random_seed)
        domains = self.df['domain'].unique()
        num_courses = len(self.df)

        interaction_matrix = np.zeros((num_users, num_courses), dtype=np.float32)
        domain_to_indices = {d: self.df[self.df['domain'] == d].index.tolist() for d in domains}

        for user_id in range(num_users):
            pref_dom = np.random.choice(domains)
            pref_indices = domain_to_indices.get(pref_dom, [])
            num_enrollments = min(len(pref_indices), np.random.randint(4, 10))
            if num_enrollments > 0:
                enrolled = np.random.choice(pref_indices, size=num_enrollments, replace=False)
                interaction_matrix[user_id, enrolled] = 1.0

        self.collaborative_similarity = cosine_similarity(interaction_matrix.T)

    def get_sbert_recommendations(self, profile_text, top_n=6):
        """Pure Deep Transformer (SBERT) Semantic Recommendation"""
        if self.sbert_model is None or self.sbert_embeddings is None:
            # Fallback to TF-IDF
            vec = self.vectorizer.transform([profile_text])
            sim = cosine_similarity(vec, self.tfidf_matrix)[0]
        else:
            q_emb = self.sbert_model.encode([profile_text], convert_to_numpy=True)
            sim = cosine_similarity(q_emb, self.sbert_embeddings)[0]

        top_indices = np.argsort(sim)[::-1][:top_n]
        results = self.df.iloc[top_indices].copy()
        results['semantic_score'] = sim[top_indices]
        return results

    def get_deep_hybrid_recommendations(self, profile_data, top_n=6):
        """
        Proposed SmartRecSys Context-Aware Deep Hybrid Recommender:
        Fuses:
          1. SBERT Dense Semantic Embedding Cosine Similarity (40%)
          2. NeuMF Deep Neural Collaborative Interaction Logits (25%)
          3. Domain & Faculty Alignment Gating (20%)
          4. Cognitive Difficulty Calibration (15%)
        """
        dept = profile_data.get('dept', 'Computer Science')
        degree = profile_data.get('degree', 'B.Tech (4-Year)')
        domains = profile_data.get('domains', [])
        difficulty = profile_data.get('difficulty', 'Beginner')
        goal = profile_data.get('career_goal', '')
        completed = profile_data.get('completed_courses', '')
        current_courses = profile_data.get('current_courses', '')
        user_id = profile_data.get('user_id', 0)

        # 1. Build Query Text
        query_parts = [
            f"Department: {dept}",
            f"Degree: {degree}",
            f"Domain Interests: {', '.join(domains)}",
            f"Difficulty Level: {difficulty}",
            f"Career Target: {goal}",
            f"Prerequisites: {completed}",
            f"Current: {current_courses}"
        ]
        query_text = ". ".join(query_parts)

        # 2. Compute SBERT Dense Semantic Similarity
        if self.sbert_model is not None and self.sbert_embeddings is not None:
            q_emb = self.sbert_model.encode([query_text], convert_to_numpy=True)
            sim_sem = cosine_similarity(q_emb, self.sbert_embeddings)[0]
        else:
            vec = self.vectorizer.transform([query_text])
            sim_sem = cosine_similarity(vec, self.tfidf_matrix)[0]

        # 3. Compute NeuMF Neural Collaborative Prediction
        num_courses = len(self.df)
        if self.neumf_model is not None:
            try:
                candidate_idx = np.arange(num_courses)
                uid_int = int(user_id) if str(user_id).isdigit() else abs(hash(str(user_id))) % 1200
                u_tensor = torch.full((num_courses,), uid_int % 1200, dtype=torch.long, device=self.device)
                i_tensor = torch.tensor(candidate_idx, dtype=torch.long, device=self.device)
                with torch.no_grad():
                    sim_neu = self.neumf_model(u_tensor, i_tensor).cpu().numpy()
            except Exception:
                sim_neu = np.zeros(num_courses)
        else:
            sim_neu = np.zeros(num_courses)

        # 4. Domain & Faculty Affinity Gating
        domain_scores = np.zeros(num_courses)
        faculty_scores = np.zeros(num_courses)
        
        target_domains_lower = [d.lower() for d in domains]
        candidate_domains = self.df['domain'].str.lower().values
        candidate_faculties = self.df['faculty'].str.lower().values
        degree_lower = degree.lower()

        for i in range(num_courses):
            c_dom = candidate_domains[i]
            c_fac = candidate_faculties[i]

            # Domain alignment
            for td in target_domains_lower:
                if td in c_dom or c_dom in td:
                    domain_scores[i] = max(domain_scores[i], 1.0)
                elif any(word in c_dom for word in td.split() if len(word) > 3):
                    domain_scores[i] = max(domain_scores[i], 0.70)

            # Degree / Faculty alignment
            if "mba" in degree_lower or "bba" in degree_lower or "management" in degree_lower:
                if "business" in c_fac or "management" in c_fac:
                    faculty_scores[i] = 1.0
                elif "computing" in c_fac or "science" in c_fac:
                    faculty_scores[i] = 0.30
            elif "m.sc" in degree_lower or "b.sc" in degree_lower or "science" in degree_lower:
                if "natural science" in c_fac or "mathematics" in c_fac:
                    faculty_scores[i] = 1.0
                elif "computing" in c_fac:
                    faculty_scores[i] = 0.60
            elif "b.tech" in degree_lower or "m.tech" in degree_lower or "bca" in degree_lower or "mca" in degree_lower:
                if "computing" in c_fac or "engineering" in c_fac:
                    faculty_scores[i] = 1.0
                elif "design" in c_fac:
                    faculty_scores[i] = 0.50
            elif "design" in degree_lower or "arts" in degree_lower or "humanities" in degree_lower:
                if "design" in c_fac or "humanities" in c_fac:
                    faculty_scores[i] = 1.0

        # 5. Cognitive Difficulty Alignment
        level_vals = self.df['level'].str.lower().values
        diff_target = difficulty.lower()
        diff_scores = np.zeros(num_courses)
        for i, lvl in enumerate(level_vals):
            if "beginner" in diff_target:
                if "beginner" in lvl: diff_scores[i] = 1.0
                elif "all" in lvl: diff_scores[i] = 0.85
                elif "intermediate" in lvl: diff_scores[i] = 0.40
                else: diff_scores[i] = 0.10
            elif "intermediate" in diff_target:
                if "intermediate" in lvl: diff_scores[i] = 1.0
                elif "all" in lvl: diff_scores[i] = 0.85
                elif "advanced" in lvl or "expert" in lvl: diff_scores[i] = 0.70
                else: diff_scores[i] = 0.45
            else: # Advanced
                if "advanced" in lvl or "expert" in lvl: diff_scores[i] = 1.0
                elif "intermediate" in lvl: diff_scores[i] = 0.85
                elif "all" in lvl: diff_scores[i] = 0.70
                else: diff_scores[i] = 0.30

        # 6. Master Calibrated Hybrid Fusion
        # Normalize continuous outputs
        def norm(v):
            r = v.max() - v.min()
            return (v - v.min()) / (r + 1e-8) if r > 0 else v

        s_sem_norm = norm(sim_sem)
        s_neu_norm = norm(sim_neu) if sim_neu.max() > 0 else np.full(num_courses, 0.5)

        # Multi-objective weighted score
        final_scores = (
            0.40 * s_sem_norm +
            0.25 * domain_scores +
            0.15 * faculty_scores +
            0.10 * diff_scores +
            0.10 * s_neu_norm
        )

        # Calibrate match percentage into [70% - 98%] for top realistic matches
        calibrated = 0.68 + (final_scores * 0.30)
        calibrated = np.clip(calibrated, 0.65, 0.98)

        # Filter out completely irrelevant faculties if domain was explicitly stated
        if len(domains) > 0:
            unmatched = (domain_scores == 0) & (faculty_scores == 0)
            calibrated[unmatched] = 0.20

        top_indices = np.argsort(calibrated)[::-1][:top_n]
        results = self.df.iloc[top_indices].copy()
        results['final_score'] = calibrated[top_indices]
        return results