import os
import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SmartCampusRecommender:
    def __init__(self, dataset_path="dataset/udemy_courses.csv"):
        self.dataset_path = dataset_path
        self.df = None
        self.tfidf_matrix = None
        self.vectorizer = None
        self.content_similarity = None
        self.user_course_matrix = None
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
            raise FileNotFoundError(f"Dataset not found at {self.dataset_path}. Run download_dataset.py first!")
        
        self.df = pd.read_csv(self.dataset_path)
        
        self.df['clean_title'] = self.df['course_title'].apply(self.clean_text)
        self.df['clean_subject'] = self.df['subject'].apply(self.clean_text)
        self.df['clean_level'] = self.df['level'].apply(self.clean_text)
        self.df['full_text'] = self.df['clean_title'] + " " + self.df['clean_subject'] + " " + self.df['clean_level']
        
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = self.vectorizer.fit_transform(self.df['full_text'])
        
        self.content_similarity = cosine_similarity(self.tfidf_matrix, self.tfidf_matrix)
        self.generate_synthetic_interactions()

    def generate_synthetic_interactions(self, num_users=1000, random_seed=42):
        np.random.seed(random_seed)
        subjects = self.df['subject'].unique()
        num_courses = len(self.df)
        
        interaction_matrix = np.zeros((num_users, num_courses), dtype=int)
        subject_to_indices = {sub: self.df[self.df['subject'] == sub].index.tolist() for sub in subjects}
        
        for user_id in range(num_users):
            pref_subject = np.random.choice(subjects)
            pref_indices = subject_to_indices[pref_subject]
            num_enrollments = np.random.randint(3, 11)
            
            if len(pref_indices) >= num_enrollments:
                enrolled = np.random.choice(pref_indices, size=num_enrollments, replace=False)
            else:
                enrolled = pref_indices
                
            interaction_matrix[user_id, enrolled] = 1
            
        self.user_course_matrix = pd.DataFrame(interaction_matrix, columns=self.df.index)
        self.collaborative_similarity = cosine_similarity(interaction_matrix.T)

    def get_content_recommendations(self, course_id, top_n=5):
        course_idx = self.df[self.df['course_id'] == course_id].index[0]
        sim_scores = list(enumerate(self.content_similarity[course_idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        # Exclude the query course itself
        sim_scores = [item for item in sim_scores if item[0] != course_idx]
        top_indices = [idx for idx, score in sim_scores[:top_n]]
        return self.df.iloc[top_indices][['course_id', 'course_title', 'subject', 'level']]

    def get_collaborative_recommendations(self, course_id, top_n=5):
        course_idx = self.df[self.df['course_id'] == course_id].index[0]
        sim_scores = list(enumerate(self.collaborative_similarity[course_idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        # Exclude the query course itself
        sim_scores = [item for item in sim_scores if item[0] != course_idx]
        top_indices = [idx for idx, score in sim_scores[:top_n]]
        return self.df.iloc[top_indices][['course_id', 'course_title', 'subject', 'level']]

    def get_hybrid_recommendations(self, course_id, alpha=0.5, top_n=5):
        course_idx = self.df[self.df['course_id'] == course_id].index[0]
        content_scores = self.content_similarity[course_idx]
        collab_scores = self.collaborative_similarity[course_idx]
        
        hybrid_scores = alpha * content_scores + (1 - alpha) * collab_scores
        sim_scores = list(enumerate(hybrid_scores))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        # Exclude the query course itself
        sim_scores = [item for item in sim_scores if item[0] != course_idx]
        top_indices = [idx for idx, score in sim_scores[:top_n]]
        
        results = self.df.iloc[top_indices].copy()
        results['hybrid_score'] = [hybrid_scores[idx] for idx in top_indices]
        return results[['course_id', 'course_title', 'subject', 'level', 'hybrid_score']]