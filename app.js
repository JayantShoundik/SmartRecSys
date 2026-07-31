// ── State ─────────────────────────────────────────────────────────────────────
let allResults = [];

// ── Mock data ─────────────────────────────────────────────────────────────────
// Each entry mirrors the shape the real API (POST /recommend) will return.
// Replace this block with a real fetch() call in Stage 4.
const MOCK_RESULTS = [
  {
    title:       "Intro to Python",
    domain:      "Programming",
    difficulty:  "Beginner",
    score:       0.92,
    duration:    "6 Weeks",
    description: "A hands-on introduction to Python covering syntax, data types, control flow, and basic file I/O.",
    skills:      ["Python", "Problem Solving", "Scripting"],
    reason:      "Matches your Programming interest and Beginner level. A strong foundation before moving to data or ML courses."
  },
  {
    title:       "React for Beginners",
    domain:      "Web Development",
    difficulty:  "Beginner",
    score:       0.87,
    duration:    "8 Weeks",
    description: "Build interactive UIs with React. Covers components, props, state, hooks, and basic routing.",
    skills:      ["React", "JavaScript", "HTML/CSS", "Component Design"],
    reason:      "Aligns with your Web Development interest. Beginner-friendly and directly applicable to frontend projects."
  },
  {
    title:       "Node.js & Express",
    domain:      "Web Development",
    difficulty:  "Intermediate",
    score:       0.81,
    duration:    "7 Weeks",
    description: "Server-side JavaScript with Node.js and Express. REST API design, middleware, and database integration.",
    skills:      ["Node.js", "Express", "REST APIs", "JavaScript"],
    reason:      "Complements React knowledge. Recommended for students targeting full-stack Web Development roles."
  },
  {
    title:       "Data Analysis with Pandas",
    domain:      "Data Science",
    difficulty:  "Intermediate",
    score:       0.78,
    duration:    "6 Weeks",
    description: "Practical data wrangling, aggregation, and visualisation using Pandas and Matplotlib.",
    skills:      ["Python", "Pandas", "Matplotlib", "Data Cleaning"],
    reason:      "Recommended based on your Data Science interest. Builds directly on Python fundamentals."
  },
  {
    title:       "Neural Networks 101",
    domain:      "Machine Learning",
    difficulty:  "Advanced",
    score:       0.74,
    duration:    "10 Weeks",
    description: "Covers feedforward networks, backpropagation, CNNs, and practical training with PyTorch.",
    skills:      ["PyTorch", "Deep Learning", "Python", "Linear Algebra"],
    reason:      "Matches your AI / ML interest. Requires prior Python and maths background — suitable for Advanced level."
  },
  {
    title:       "AWS Cloud Fundamentals",
    domain:      "Cloud Computing",
    difficulty:  "Beginner",
    score:       0.70,
    duration:    "5 Weeks",
    description: "Introduction to cloud concepts, core AWS services (EC2, S3, IAM), and basic deployment patterns.",
    skills:      ["AWS", "Cloud Concepts", "Networking Basics", "IAM"],
    reason:      "Recommended for students interested in Cloud Computing. No prior cloud experience required."
  },
];

// ── Fetch recommendations ─────────────────────────────────────────────────────
async function fetchRecommendations(userId, preferences) {
  // Stage 3: filter mock data by selected domains
  return MOCK_RESULTS.filter(c =>
    preferences.domains.length === 0 ||
    preferences.domains.includes(c.domain)
  );

  // Stage 4: uncomment and remove the mock return above
  // const res = await fetch("http://localhost:5000/recommend", {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({ user_id: userId, preferences })
  // });
  // if (!res.ok) throw new Error("API error: " + res.status);
  // return res.json();
}

// ── Card builder (single source of truth for card markup) ─────────────────────
function buildCard(course, animIndex, showBadge) {
  const pct  = Math.round(course.score * 100);
  const card = document.createElement("div");
  card.className = "card";
  card.style.animationDelay = `${animIndex * 60}ms`;

  const skillPills = (course.skills || [])
    .map(s => `<span class="skill-pill">${s}</span>`)
    .join("");

  card.innerHTML = `
    ${showBadge ? '<span class="badge-top">Top Match</span>' : ''}
    <div class="card-title">${course.title}</div>
    <div class="tags">
      <span class="tag">${course.domain}</span>
      <span class="tag ${course.difficulty}">${course.difficulty}</span>
      ${course.duration ? `<span class="tag tag-duration">${course.duration}</span>` : ''}
    </div>
    ${course.description ? `<p class="card-desc">${course.description}</p>` : ''}
    ${skillPills ? `<div class="card-skills">${skillPills}</div>` : ''}
    ${course.reason ? `<div class="card-reason"><span class="reason-label">Why recommended</span>${course.reason}</div>` : ''}
    <div class="card-footer">
      <div class="match-ring" style="--pct:${pct}">
        <div class="match-ring-inner">${pct}%</div>
      </div>
      <div class="match-label">Match score<strong>${pct}%</strong></div>
    </div>
  `;
  return card;
}

// ── Render main grid ──────────────────────────────────────────────────────────
function renderResults(results) {
  const container = document.getElementById("results");
  const empty     = document.getElementById("emptyState");
  container.innerHTML = "";
  if (!results.length) { empty.classList.remove("hidden"); return; }
  empty.classList.add("hidden");
  results.forEach((course, i) => container.appendChild(buildCard(course, i, false)));
}

// ── Render featured top-3 row ─────────────────────────────────────────────────
function renderFeatured(results) {
  const row = document.getElementById("featuredRow");
  row.innerHTML = "";
  results.slice(0, 3).forEach((course, i) =>
    row.appendChild(buildCard(course, i, i === 0))
  );
}

// ── Filters ───────────────────────────────────────────────────────────────────
function applyFilters() {
  const domain     = document.getElementById("filterDomain").value;
  const difficulty = document.getElementById("filterDifficulty").value;
  const filtered   = allResults.filter(c =>
    (!domain     || c.domain     === domain) &&
    (!difficulty || c.difficulty === difficulty)
  );
  renderResults(filtered);
}

function populateDomainFilter(results) {
  const select = document.getElementById("filterDomain");
  select.innerHTML = '<option value="">All Domains</option>';
  [...new Set(results.map(c => c.domain))].forEach(d => {
    const opt = document.createElement("option");
    opt.value = d; opt.textContent = d;
    select.appendChild(opt);
  });
}

// ── Profile chips (summary bar under the greeting) ───────────────────────────
function renderProfileChips(params) {
  const container = document.getElementById("profileChips");
  if (!container) return;
  const items = [
    params.get("dept"),
    params.get("degree"),
    params.get("batch") ? "Semester " + params.get("semester") : null,
    params.get("level"),
    params.get("goal"),
  ].filter(Boolean);
  container.innerHTML = items
    .map(v => `<span class="profile-chip">${v}</span>`)
    .join("");
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);

  // Greeting
  const name = params.get("name") || "Student";
  document.getElementById("userName").textContent = name;

  // Profile summary chips
  renderProfileChips(params);

  // Pre-fill domain chips from URL params (from home.html form)
  const urlDomains = (params.get("domains") || "").split(",").map(d => d.trim()).filter(Boolean);
  if (urlDomains.length) {
    document.querySelectorAll("#domainGroup input").forEach(cb => {
      if (urlDomains.includes(cb.value)) cb.checked = true;
    });
  }

  // Pre-fill difficulty from URL params
  const urlLevel = params.get("level") || "";
  if (urlLevel) {
    const sel = document.getElementById("difficulty");
    // Map home.html level values to dashboard select values
    const levelMap = { Beginner: "Beginner", Intermediate: "Intermediate", Advanced: "Advanced" };
    if (levelMap[urlLevel]) sel.value = levelMap[urlLevel];
  }

  // Recommend button
  document.getElementById("recommendBtn").addEventListener("click", async () => {
    const domains    = [...document.querySelectorAll("#domainGroup input:checked")].map(cb => cb.value);
    const difficulty = document.getElementById("difficulty").value;
    const errorMsg   = document.getElementById("errorMsg");

    if (!domains.length) { errorMsg.classList.remove("hidden"); return; }
    errorMsg.classList.add("hidden");

    const resultsSection = document.getElementById("resultsSection");
    const spinner        = document.getElementById("spinner");

    resultsSection.classList.remove("hidden");
    spinner.classList.remove("hidden");
    document.getElementById("results").innerHTML = "";
    document.getElementById("featuredRow").innerHTML = "";
    document.getElementById("emptyState").classList.add("hidden");

    try {
      const data = await fetchRecommendations(name, { domains, difficulty });
      allResults = difficulty ? data.filter(c => c.difficulty === difficulty) : data;
      populateDomainFilter(allResults);
      renderFeatured(allResults);
      renderResults(allResults);
    } catch (err) {
      document.getElementById("results").innerHTML =
        `<p class="error">Failed to load recommendations. Please try again.</p>`;
    } finally {
      spinner.classList.add("hidden");
    }
  });

  // Filter dropdowns
  document.getElementById("filterDomain").addEventListener("change", applyFilters);
  document.getElementById("filterDifficulty").addEventListener("change", applyFilters);
});
