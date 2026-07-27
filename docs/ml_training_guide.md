# SmartRecSys: Machine Learning & Deep Learning Training Guide

This guide outlines environment setup, model training steps, and parameter tuning workflows for Member 4 (ML/DL Model Engineer).

---

## 🛠️ Environment Setup

Ensure your local machine has Python 3.10+ and the required AI libraries installed.

### Installation Command
```bash
pip install torch pandas scikit-learn matplotlib seaborn
```

### Checking for GPU Acceleration (Crucial for strong laptops)
Our deep learning script (`dl_recommender_gpu.py`) automatically utilizes GPU hardware. Open a python console and run this check:
```python
import torch
print("CUDA (Nvidia GPU):", torch.cuda.is_available())
print("MPS (Apple M-Series GPU):", torch.backends.mps.is_available())
```
*If either outputs `True`, PyTorch will automatically run training on the GPU, significantly decreasing epoch latency.*

---

## 🚀 Model Training & Verification

You are in charge of training and evaluating two core models:

### 1. The Machine Learning Model (SVD Matrix Factorization)
*   **Script:** `evaluate_ml.py`
*   **Command:** `python3 evaluate_ml.py`
*   **What it does:** Runs 6-fold cross-validation on our simulated campus user matrix. It fits Singular Value Decomposition (SVD), reconstructs preferences, evaluates Precision/Recall, and saves a performance chart to `plots/evaluation_comparison.png`.

### 2. The Deep Learning Model (Neural Collaborative Filtering in PyTorch)
*   **Script:** `dl_recommender_gpu.py`
*   **Command:** `python3 dl_recommender_gpu.py`
*   **What it does:** Maps users and courses to a latent embedding layer, passes them through a Multi-Layer Perceptron (MLP) neural network, trains weights using Binary Cross-Entropy Loss (`BCELoss`), and saves the trained state to `models/ncf_recommender.pth`.

---

## ⚙️ Hyperparameter Tuning (Optimization)

To achieve the best Precision/Recall trade-off, you must experiment with the following parameters (based on feedback from Member 3's literature review):

### 1. Tuning the Hybrid Score Weight ($\alpha$)
*   In `recommender.py` / `evaluate_ml.py`, modify the hybrid score equation weight:
    $$\text{Score}_{\text{hybrid}} = \alpha \cdot \text{Score}_{\text{content}} + (1 - \alpha) \cdot \text{Score}_{\text{collaborative}}$$
    *   Test values: $\alpha = 0.3, 0.5, 0.7$.
    *   **Goal:** Find if semantic keywords or peer behaviors are more predictive of student course registrations.

### 2. Tuning SVD Dimensions
*   In `evaluate_ml.py`, modify the SVD latent factor count:
    `svd = TruncatedSVD(n_components=12, random_state=42)`
    *   Test values: `n_components = 8, 12, 16, 24`.
    *   **Goal:** Balance model capacity against overfitting (too many dimensions captures noise; too few loses patterns).

### 3. Tuning NCF Deep Learning Parameters
*   In `dl_recommender_gpu.py`, modify:
    *   `embedding_dim = 16` (Test: 8, 16, 32)
    *   Optimizer learning rate: `lr=0.001` (Test: 0.01, 0.001, 0.0001)
    *   Network Depth: Add/remove dense layers in the MLP block.
