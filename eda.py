import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re

# Load dataset
dataset_path = "dataset/udemy_courses.csv"
if not os.path.exists(dataset_path):
    print(f"Error: {dataset_path} not found. Please run download_dataset.py first!")
    exit(1)

df = pd.read_csv(dataset_path)
print("Dataset Loaded. Shape:", df.shape)

# Create plots directory
os.makedirs("plots", exist_ok=True)

# Set style
sns.set_theme(style="whitegrid")

# 1. Subject Distribution (Pie Chart)
plt.figure(figsize=(8, 8))
subject_counts = df['subject'].value_counts()
plt.pie(subject_counts, labels=subject_counts.index, autopct='%1.1f%%', startangle=140, 
        colors=sns.color_palette("pastel"))
plt.title("Distribution of Courses across Subjects", fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig("plots/subject_distribution.png", dpi=150)
plt.close()
print("Saved plots/subject_distribution.png")

# 2. Difficulty Level Distribution (Bar Chart)
plt.figure(figsize=(8, 5))
sns.countplot(data=df, x='level', order=df['level'].value_counts().index, palette="viridis")
plt.title("Distribution of Courses across Difficulty Levels", fontsize=14, fontweight='bold')
plt.xlabel("Difficulty Level", fontsize=12)
plt.ylabel("Number of Courses", fontsize=12)
plt.xticks(rotation=15)
plt.tight_layout()
plt.savefig("plots/level_distribution.png", dpi=150)
plt.close()
print("Saved plots/level_distribution.png")

# 3. Correlation Heatmap
plt.figure(figsize=(8, 6))
# Select numeric columns
numeric_cols = ['price', 'num_subscribers', 'num_reviews', 'num_lectures', 'content_duration']
corr = df[numeric_cols].corr()
sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5)
plt.title("Correlation Matrix of Numeric Features", fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig("plots/correlation_matrix.png", dpi=150)
plt.close()
print("Saved plots/correlation_matrix.png")

# 4. Top Words in Course Titles
plt.figure(figsize=(10, 5))
stop_words = set(['and', 'the', 'a', 'to', 'for', 'in', 'of', 'with', 'on', 'your', 'how', 'an', 'is', 'from', 'you', 'this'])
words = []
for title in df['course_title']:
    # Clean text
    clean_title = re.sub(r'[^a-zA-Z\s]', '', str(title)).lower()
    words.extend([w for w in clean_title.split() if w not in stop_words and len(w) > 2])

word_counts = Counter(words).most_common(15)
word_df = pd.DataFrame(word_counts, columns=['Word', 'Frequency'])

sns.barplot(data=word_df, y='Word', x='Frequency', palette="mako")
plt.title("Top 15 Most Frequent Words in Course Titles", fontsize=14, fontweight='bold')
plt.xlabel("Frequency", fontsize=12)
plt.ylabel("Word", fontsize=12)
plt.tight_layout()
plt.savefig("plots/top_words.png", dpi=150)
plt.close()
print("Saved plots/top_words.png")

print("EDA completed successfully. All plots saved to 'plots/' folder.")
