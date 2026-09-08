import os
import datetime
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_PATH = "smartrecsys.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    degree = Column(String(100), nullable=False)
    year = Column(String(50), nullable=False)
    semester = Column(Integer, nullable=False)
    cgpa = Column(Float, nullable=True)
    completed_courses = Column(Text, nullable=True)
    current_courses = Column(Text, nullable=True)
    domains = Column(String(255), nullable=False)
    difficulty = Column(String(50), nullable=False)
    career_goal = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    recommendations = relationship("RecommendationAudit", back_populates="student")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, unique=True, index=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=False)
    level = Column(String(50), nullable=False)
    num_subscribers = Column(Integer, default=0)
    num_reviews = Column(Integer, default=0)
    num_lectures = Column(Integer, default=0)
    content_duration = Column(Float, default=0.0)
    price = Column(Float, default=0.0)

class RecommendationAudit(Base):
    __tablename__ = "recommendation_audits"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    student_name = Column(String(100), nullable=False)
    query_domains = Column(String(255), nullable=False)
    query_difficulty = Column(String(50), nullable=False)
    active_model = Column(String(100), default="Hybrid Semantic + Neural")
    top_courses_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    student = relationship("Student", back_populates="recommendations")

def init_db(dataset_csv="dataset/udemy_courses.csv"):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    
    # Check if catalog already populated
    if session.query(Course).count() == 0 and os.path.exists(dataset_csv):
        print("🌱 Seeding Course Catalog into SQLite (smartrecsys.db)...")
        df = pd.read_csv(dataset_csv).drop_duplicates(subset=['course_id'])
        courses_to_add = []
        for _, row in df.iterrows():
            c = Course(
                course_id=int(row['course_id']),
                title=str(row['course_title']),
                subject=str(row['subject']),
                level=str(row['level']),
                num_subscribers=int(row.get('num_subscribers', 0)),
                num_reviews=int(row.get('num_reviews', 0)),
                num_lectures=int(row.get('num_lectures', 0)),
                content_duration=float(row.get('content_duration', 0.0)),
                price=float(row.get('price', 0.0))
            )
            courses_to_add.append(c)
        session.bulk_save_objects(courses_to_add)
        session.commit()
        print(f"✅ Seeded {len(courses_to_add):,} courses into SQLite database.")
    session.close()

if __name__ == "__main__":
    init_db()
