import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_system_architecture():
    fig, ax = plt.subplots(figsize=(14, 9), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Color Palette - Professional IEEE Styling
    c_input = '#e0e7ff'      # Indigo light
    c_sem = '#dbeafe'        # Blue light
    c_deep = '#fce7f3'       # Pink/Rose light
    c_gate = '#fef3c7'       # Amber light
    c_fusion = '#d1fae5'     # Emerald light
    c_xai = '#ede9fe'        # Purple light
    c_border = '#1e293b'     # Slate dark

    def box(x, y, w, h, bg, title, text, subtext=""):
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.12,rounding_size=0.15",
            facecolor=bg, edgecolor=c_border, linewidth=1.5
        )
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.35, title, ha='center', va='top', fontsize=10, fontweight='bold', color='#0f172a')
        if text:
            ax.text(x + w/2, y + h/2 - 0.1, text, ha='center', va='center', fontsize=8.5, color='#334155')
        if subtext:
            ax.text(x + w/2, y + 0.3, subtext, ha='center', va='bottom', fontsize=7.5, fontstyle='italic', color='#64748b')

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="-|>", color='#334155', lw=1.8, mutation_scale=15)
        )
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label, ha='center', va='bottom', fontsize=8, fontweight='bold', color='#1e293b')

    # Title Banner
    ax.text(7, 9.6, "SmartRecSys End-to-End Hybrid Recommendation & Explainability Pipeline", ha='center', va='center', fontsize=13, fontweight='bold', color='#0f172a')

    # 1. Input Layer
    box(0.5, 7.3, 13.0, 1.7, c_input, "1. STUDENT ACADEMIC PROFILE INTAKE", 
        "Department | Degree Program (B.Tech 4-Yr / BCA 3-Yr) | Batch Year & Active Semester | Target Domain Specialties\nPrior Completed Prerequisites | Certified Skill Competencies | Declared Career Aspiration",
        "Resolves Zero-History Freshman Cold-Start via Multi-Token Semantic Formulation")

    # 2. Dual Pathway Modeling
    # Pathway A: Semantic TF-IDF
    box(0.8, 4.4, 3.8, 2.2, c_sem, "2A. SEMANTIC PROFILING",
        "Sublinear TF-IDF Vectorizer\nVocab Dimension: |V| tokens\nContinuous Cosine Metric\nS_sem(u, i) in [0, 1]",
        "Content Continuity Bridge")

    # Pathway B: Deep PyTorch NCF
    box(5.1, 4.4, 3.8, 2.2, c_deep, "2B. DEEP LEARNING (NCF)",
        "PyTorch Dual Embeddings (d=16)\nConcatenation: z_0 = [P_u || Q_i]\n3-Layer Non-Linear MLP (ReLU, Dropout)\nSigmoid Prediction: S_neu(u, i)",
        "Accelerated via Apple Silicon MPS / CUDA")

    # Pathway C: Latent SVD
    box(9.4, 4.4, 3.8, 2.2, c_gate, "2C. SVD FACTORIZATION",
        "Truncated SVD Matrix Decomp.\nRank k=12 Latent Curricular Factors\nFrobenius Norm Reconstruction\nR_hat = U * Sigma * V^T",
        "Historical Campus Interaction Matrix")

    # Connect Layer 1 to Layer 2
    arrow(3.0, 7.3, 2.7, 6.6, "Profile Tokens")
    arrow(7.0, 7.3, 7.0, 6.6, "User/Course ID")
    arrow(11.0, 7.3, 11.3, 6.6, "Historical Links")

    # 3. Pedagogical Policy & Domain Affinity Masking
    box(1.5, 2.4, 11.0, 1.4, c_gate, "3. PEDAGOGICAL POLICY & DOMAIN AFFINITY MASKING",
        "Domain Affinity Mask S_dom: Strict Boundary Guard (S_dom = 0 -> S_final = 0.05 Penalty)\nCognitive Difficulty Alignment S_dif: Delta(Target_Level, Course_Level) in [0.10, 1.00]\nPrerequisite Verification: Chaining completed foundations to prospective syllabi",
        "Eliminates Out-of-Domain Leakage & Prevents Cognitive Overload")

    # Connect Layer 2 to Layer 3
    arrow(2.7, 4.4, 4.0, 3.8)
    arrow(7.0, 4.4, 7.0, 3.8)
    arrow(11.3, 4.4, 10.0, 3.8)

    # 4. Master Calibrated Hybrid Fusion
    box(1.5, 0.4, 5.2, 1.5, c_fusion, "4. MASTER CALIBRATED HYBRID FUSION",
        "S_raw = 0.40*S_dom + 0.30*S_sem + 0.20*S_dif + 0.10*S_neu\nScore_final = min(0.98, max(0.65, 0.65 + 0.33*S_raw))\nTop-K Academic Ranking Permutation",
        "+16.6% Recall@5 Gain over CF")

    # 5. XAI & Audit Report
    box(7.3, 0.4, 5.2, 1.5, c_xai, "5. XAI EXPLAINABILITY & AUDIT REPORT",
        "Pedagogical Attribution: psi_dom + psi_career + psi_prereq\nPersistent SQLite Logging (smartrecsys.db)\nInteractive UI Cards & One-Click Printable PDF Advisory",
        "Institutional Transparency & Advisory Compliance")

    # Connect Layer 3 to Layer 4 & 5
    arrow(5.5, 2.4, 4.1, 1.9, "Regularized Weights")
    arrow(8.5, 2.4, 9.9, 1.9, "Attribution Features")
    arrow(6.7, 1.15, 7.3, 1.15, "Ranked Permutation")

    plt.tight_layout()
    output_path = "paper/figures/system_architecture.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Generated high-resolution system architecture flowchart at '{output_path}'")

if __name__ == "__main__":
    draw_system_architecture()
