"""
evaluate.py — Cross-Validation Evaluation for SmartRecSys
Evaluates Content-Based, Collaborative Filtering, Matrix Factorization (SVD),
and SmartRecSys Hybrid using 6-Fold Cross-Validation without data leakage.
"""

from evaluate_ml import run_evaluation

if __name__ == "__main__":
    run_evaluation()

