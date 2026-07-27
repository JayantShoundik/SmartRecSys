# SmartRecSys: Project Implementation Summary (For Literature Lead)

This document provides a detailed summary of the datasets, algorithms, and parameters currently implemented in the **SmartRecSys** repository. Member 3 (Literature Lead) should use this summary to write the Literature Review and compile the project's algorithmic blueprint.

---

## 1. Selected Reference Paper & Dataset

*   **Reference Paper:** *An Intelligent Hybrid Recommendation System for E-Learning Personalization in Smart Campus* by Manar Joundy Hazar (2025).
*   **Core Dataset (`dataset/udemy_courses.csv`):**
    *   **Source:** Scraped Udemy course catalog from Kaggle.
    *   **Shape:** 3,678 courses with 12 features.
    *   **Main Features:** `course_id`, `course_title`, `subject`, `level`, `num_subscribers`, `num_reviews`, `price`, `num_lectures`, `content_duration`.
*   **Interaction Dataset (Generated in memory):**
    *   To simulate a smart campus environment, the backend generates **1,000 synthetic learner profiles**.
    *   Each student profile is assigned a preferred subject and a history of **3 to 10 course enrollments** (biased towards their preferred subject to model real-world interest groups).
    *   Compiled into a binary user-course matrix (dimensions: $1000 \text{ users} \times 3678 \text{ courses}$).

---

## 2. Implemented Algorithms

We have developed three distinct recommendation pipelines:

### Pipeline A: Content-Based Filtering (Baseline)
*   **Method:** Text Vectorization and Semantic Similarity.
*   **Feature Engineering:** Concatenates course `clean_title` + `clean_subject` + `clean_level` into a single string (`full_text`).
*   **Algorithm:** `TfidfVectorizer` (stop words = 'english') converts text to a vector space. Cosine similarity is computed between all course vectors:
    $$\text{Similarity}_{\text{content}}(A, B) = \cos(\theta) = \frac{\vec{A} \cdot \vec{B}}{\|\vec{A}\| \|\vec{B}\|}$$

### Pipeline B: Item-Item Collaborative Filtering (Baseline)
*   **Method:** Co-enrollment behavioral patterns.
*   **Algorithm:** Computes Cosine Similarity on the transposed user-course interaction matrix. Measures how frequently two courses are enrolled in by the same students on campus.

### Pipeline C: Weighted Hybrid Recommender (Primary Architecture)
*   **Method:** Fuses Pipeline A (semantics) and Pipeline B (behaviors).
*   **Formula:** 
    $$\text{Score}_{\text{hybrid}} = \alpha \cdot \text{Score}_{\text{content}} + (1 - \alpha) \cdot \text{Score}_{\text{collaborative}}$$
    *   **Default Parameter:** $\alpha = 0.5$ (tunable between $0.0$ and $1.0$).

### Pipeline D: Machine Learning Matrix Factorization (SVD)
*   **Method:** Low-rank matrix approximation.
*   **Algorithm:** `TruncatedSVD` (Singular Value Decomposition) from scikit-learn.
*   **Parameters:** 
    *   `n_components = 12` (dimensionality of latent user/course space).
    *   Reconstructs rating scores: $\hat{R} = U \cdot \Sigma \cdot V^T$.

### Pipeline E: Deep Learning Neural Collaborative Filtering (NCF)
*   **Method:** Deep neural network with trainable embeddings in **PyTorch**.
*   **Architecture:**
    *   **User Embeddings Layer:** Dimension size = 16.
    *   **Item Embeddings Layer:** Dimension size = 16.
    *   **Multi-Layer Perceptron (MLP):** Fuses concatenated embeddings through dense layers:
        $$\text{Linear}(32 \to 64) \to \text{ReLU} \to \text{Dropout}(0.2) \to \text{Linear}(64 \to 32) \to \text{ReLU} \to \text{Dropout}(0.2) \to \text{Linear}(32 \to 16) \to \text{ReLU} \to \text{Linear}(16 \to 1) \to \text{Sigmoid}$$
*   **Loss Function:** Binary Cross-Entropy Loss (`BCELoss`) to predict enrollment probability ($0$ or $1$).
*   **Optimizer:** `Adam` (learning rate = $0.001$).
*   **Hyperparameters:** Epochs = $15$, Batch Size = $512$.
*   **Hardware Acceleration:** Configured for automatic hardware detection: uses **NVIDIA CUDA** on Windows/Linux or **Apple Metal Performance Shaders (MPS)** on MacBooks, falling back to CPU if no GPU is found.

---

## 3. Evaluation System (`evaluate_ml.py`)

*   **Validation Protocol:** **6-Fold Cross-Validation**.
*   **Procedure:** Masks one random course enrollment for each student. Trains the models on the remaining interactions and tests if the masked course appears in the top-K recommendations.
*   **Metrics Evaluated:**
    *   **Precision@K** (at $K = 3, 5$)
    *   **Recall@K** (at $K = 3, 5$)
*   **Verification:** Comparison graphs are exported automatically to `plots/evaluation_comparison.png`.
