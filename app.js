// ── State ─────────────────────────────────────────────────────────────────────
let allResults = [];
let lastStudentId = null;

// ── Fetch recommendations from Flask Backend API ──────────────────────────────
async function fetchRecommendations(userName, preferences) {
  const params = new URLSearchParams(window.location.search);
  
  const payload = {
    user_id: userName,
    preferences: {
      domains: preferences.domains,
      difficulty: preferences.difficulty,
      dept: params.get("dept") || "Computer Science",
      degree: params.get("degree") || "B.Tech (4-Year)",
      batch: params.get("batch") || "2nd Year",
      semester: parseInt(params.get("semester") || "3", 10),
      cgpa: params.get("cgpa") ? parseFloat(params.get("cgpa")) : null,
      completed_courses: params.get("completed_courses") || "",
      current_courses: params.get("current_courses") || "",
      career_goal: params.get("goal") || "Software Engineer"
    }
  };

  const res = await fetch("http://127.0.0.1:5001/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  
  if (!res.ok) throw new Error("API error: " + res.status);
  const data = await res.json();
  
  if (data.student_id) {
    lastStudentId = data.student_id;
  }
  if (data.active_model && document.getElementById("activeModelBadge")) {
    document.getElementById("activeModelBadge").textContent = data.active_model;
  }

  return Array.isArray(data) ? data : (data.recommendations || []);
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
      <span class="tag ${course.difficulty.toLowerCase()}">${course.difficulty}</span>
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
    params.get("batch"),
    params.get("semester") ? "Semester " + params.get("semester") : null,
    params.get("level"),
    params.get("goal") ? "Goal: " + params.get("goal") : null,
  ].filter(Boolean);
  container.innerHTML = items
    .map(v => `<span class="profile-chip">${v}</span>`)
    .join("");
}

// ── Academic Advisory Report Modal Functions ─────────────────────────────────
async function loadAndShowReport() {
  const modal = document.getElementById("reportModal");
  if (!modal) return;

  try {
    const url = lastStudentId 
      ? `http://127.0.0.1:5001/api/report?student_id=${lastStudentId}`
      : `http://127.0.0.1:5001/api/report`;

    const res = await fetch(url);
    if (!res.ok) throw new Error("Could not load advisory report");
    const data = await res.json();

    document.getElementById("repName").textContent = data.student.name;
    document.getElementById("repDept").textContent = data.student.department;
    document.getElementById("repDegree").textContent = data.student.degree;
    document.getElementById("repYear").textContent = data.student.year;
    document.getElementById("repSem").textContent = "Semester " + data.student.semester;
    document.getElementById("repCgpa").textContent = data.student.cgpa;
    document.getElementById("repGoal").textContent = data.student.career_goal;
    document.getElementById("repDomains").textContent = data.student.target_domains;

    document.getElementById("repModel").textContent = data.system_audit.model_engine;
    document.getElementById("repTimestamp").textContent = data.system_audit.generated_at;
    document.getElementById("repHash").textContent = data.system_audit.verification_hash;
    document.getElementById("reportSubtitle").textContent = `Report Reference: ${data.report_id}`;

    const listDiv = document.getElementById("reportCoursesList");
    listDiv.innerHTML = "";

    data.recommendations.forEach((c, idx) => {
      const pct = Math.round(c.score * 100);
      const row = document.createElement("div");
      row.style.cssText = "display:flex; justify-content:space-between; align-items:flex-start; padding:10px 0; border-bottom:1px solid #e5e7eb; gap:12px;";
      row.innerHTML = `
        <div style="flex:1;">
          <div style="font-weight:600; color:#111827;">#${idx+1}. ${c.title}</div>
          <div style="font-size:0.84rem; color:#6b7280; margin-top:2px;">
            Domain: <strong>${c.domain}</strong> | Level: <strong>${c.difficulty}</strong> | Duration: <strong>${c.duration}</strong>
          </div>
          <div style="font-size:0.84rem; color:#4b5563; margin-top:4px; font-style:italic;">
            "${c.reason}"
          </div>
        </div>
        <div style="font-weight:700; font-size:1.05rem; color:#4f46e5; min-width:60px; text-align:right;">
          ${pct}%
        </div>
      `;
      listDiv.appendChild(row);
    });

    modal.classList.remove("hidden");
  } catch (e) {
    alert("Could not generate report: " + e.message);
  }
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
    const domainMap = {
      "AI": "Machine Learning",
      "Software Engineering": "Programming",
      "Networking": "Cybersecurity"
    };
    const resolvedDomains = urlDomains.map(d => domainMap[d] || d);
    document.querySelectorAll("#domainGroup input").forEach(cb => {
      if (resolvedDomains.includes(cb.value)) cb.checked = true;
    });
  }

  // Pre-fill difficulty from URL params
  const urlLevel = params.get("level") || "";
  if (urlLevel) {
    const sel = document.getElementById("difficulty");
    const levelMap = { Beginner: "Beginner", Intermediate: "Intermediate", Advanced: "Advanced" };
    if (levelMap[urlLevel]) sel.value = levelMap[urlLevel];
  }

  // Auto-fetch recommendations on page load
  setTimeout(() => {
    document.getElementById("recommendBtn").click();
  }, 100);

  // Recommend button listener
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
      allResults = difficulty ? data.filter(c => c.difficulty === difficulty || c.difficulty === "All Levels" || c.difficulty === "All") : data;
      if (!allResults.length) allResults = data;
      populateDomainFilter(allResults);
      renderFeatured(allResults);
      renderResults(allResults);
    } catch (err) {
      document.getElementById("results").innerHTML =
        `<p class="error">Failed to load recommendations. Please ensure backend Flask server (server.py) is running on port 5001.</p>`;
    } finally {
      spinner.classList.add("hidden");
    }
  });

  // Filter dropdowns
  document.getElementById("filterDomain").addEventListener("change", applyFilters);
  document.getElementById("filterDifficulty").addEventListener("change", applyFilters);

  // Report Modal Listeners
  const openReportBtn = document.getElementById("openReportBtn");
  if (openReportBtn) openReportBtn.addEventListener("click", loadAndShowReport);

  const closeReportBtn = document.getElementById("closeReportBtn");
  if (closeReportBtn) closeReportBtn.addEventListener("click", () => document.getElementById("reportModal").classList.add("hidden"));

  const closeReportModalBtn = document.getElementById("closeReportModalBtn");
  if (closeReportModalBtn) closeReportModalBtn.addEventListener("click", () => document.getElementById("reportModal").classList.add("hidden"));

  const printReportBtn = document.getElementById("printReportBtn");
  if (printReportBtn) printReportBtn.addEventListener("click", () => window.print());
});
