# SmartRecSys: Frontend Developer Setup & Design Guide

This guide outlines the tasks, dashboard requirements, and API integration steps for Member 2 (Frontend UI/UX Engineer).

---

## 🛠️ Environment Setup

You can build the user interface using either **Vanilla HTML/CSS/JS** (no build steps, fast rendering) or a framework like **React / Next.js**.

### Running a Local Server
To view and test your HTML files locally, run a lightweight server:
*   **Using Python:**
    ```bash
    python3 -m http.server 8000
    ```
*   **Using Node/NPM:**
    ```bash
    npm install -g serve
    serve .
    ```
Navigate to `http://localhost:8000` in your browser.

---

## 🎨 Dashboard Design Requirements

You need to construct a clean, modern dashboard matching the **Smart Campus** ecosystem. Design the following views:

### 1. Student Profile Selector (Mock Login)
*   Since we simulate 1,000 students (User IDs `0` to `999`), provide a dropdown or input field allowing the assessor to "log in" as a specific student (e.g., User `42`).

### 2. Student Dashboard Page
*   **Profile Section:** Displays student ID, Mock Name, and Preferred Subject Area (e.g. *Web Development*, *Graphic Design*, *Business Finance*, *Musical Instruments*).
*   **Enrollment History:** Lists courses the student is already registered in (obtained from their simulated enrollment history).
*   **Search Bar:** Interactive search to find new courses in the catalog.

### 3. Recommendations Panel (Top-K)
*   Displays recommended courses. For academic display, split recommendations into tabs or panels:
    *   **Tab A: Semantic Fits (Content-Based):** Shows courses matching the keywords of their history.
    *   **Tab B: Peer Favorites (Collaborative):** Shows courses popular among other students with similar profiles.
    *   **Tab C: Smart Campus Picks (Hybrid/SVD/Deep Learning):** Fused recommendations with the highest prediction scores.

---

## 🔌 API Integration (Connecting to Backend)

In the final delivery, we will wrap our Python recommender inside a **Flask** or **FastAPI** web server. The API will serve recommendations as JSON payloads.

### Sample API Endpoint Contract
Your JavaScript code (`app.js` or React components) will fetch data from the following mock API:

*   **Endpoint:** `GET /recommend?user_id=42&top_k=5`
*   **Response Payload Structure:**
    ```json
    [
      {
        "rank": 1,
        "course_id": 1070968,
        "course_title": "Learn HTML5 Programming",
        "subject": "Web Development",
        "level": "Beginner Level",
        "hybrid_score": 0.8421
      },
      {
        "rank": 2,
        "course_id": 2323,
        "course_title": "Build Responsive Websites with Bootstrap",
        "subject": "Web Development",
        "level": "Intermediate Level",
        "hybrid_score": 0.7915
      }
    ]
    ```

### Mock JS Integration Code
While the backend models are training, you can mock the fetch calls in your frontend using this helper:
```javascript
async function fetchRecommendations(userId, topK = 5) {
  try {
    // Replace with local backend URL once API is live
    const response = await fetch(`http://localhost:5000/recommend?user_id=${userId}&top_k=${topK}`);
    const data = await response.json();
    renderRecommendations(data);
  } catch (error) {
    console.error("API unavailable, falling back to mock data:", error);
    // Render static placeholder recommendations
  }
}
```
