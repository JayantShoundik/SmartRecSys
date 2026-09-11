// ── Dashboard access guard ────────────────────────────────────────────────────
// Runs immediately (before DOM parse) so the redirect is instant.
// dashboard.html loads this script as the very first thing in <body>.
(function () {
  const page = window.location.pathname.split('/').pop();
  if (page === 'dashboard.html') {
    const params = new URLSearchParams(window.location.search);
    const name = params.get('name');
    if (!name || !name.trim()) {
      // Check if student is logged in via persistent session
      const savedStudent = localStorage.getItem('srs_session_student');
      if (savedStudent) {
        try {
          const s = JSON.parse(savedStudent);
          const newParams = new URLSearchParams({
            name:              s.name || 'Student',
            dept:              s.department || 'Computer Science',
            degree:            s.degree || 'B.Tech (4-Year)',
            batch:             s.year || '2nd Year',
            semester:          String(s.semester || '3'),
            cgpa:              s.cgpa !== null && s.cgpa !== undefined ? String(s.cgpa) : '',
            completed_courses: s.completed_courses || '',
            current_courses:   s.current_courses || '',
            domains:           (s.domains || []).join(','),
            level:             s.difficulty || 'Beginner',
            goal:              s.career_goal || 'Software Engineer',
            roll:              s.roll_number || ''
          });
          window.location.replace('dashboard.html?' + newParams.toString());
          return;
        } catch (e) {
          console.warn('Invalid session JSON:', e);
        }
      }
      window.location.replace('login.html');
    }
  }
})();

// ── DOM-dependent setup ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

  // ── Active nav link ─────────────────────────────────────────────────────────
  const page = window.location.pathname.split('/').pop().replace('.html', '') || 'welcome';
  document.querySelectorAll('.nav-link[data-page]').forEach(function (link) {
    if (link.dataset.page === page) link.classList.add('nav-active');
  });

  // ── Global Navbar Auth Status ───────────────────────────────────────────────
  const nav = document.querySelector('.topnav');
  const linksList = nav ? nav.querySelector('.nav-links') : null;

  if (linksList) {
    const savedStudent = localStorage.getItem('srs_session_student');
    const authLi = document.createElement('li');
    authLi.className = 'nav-auth-item';
    authLi.style.display = 'flex';
    authLi.style.alignItems = 'center';
    authLi.style.gap = '8px';
    authLi.style.marginLeft = '12px';

    if (savedStudent) {
      try {
        const student = JSON.parse(savedStudent);
        const firstName = student.name ? student.name.split(' ')[0] : 'Student';
        const deptShort = student.department ? (student.department === 'Computer Science' ? 'CS' : student.department === 'Information Technology' ? 'IT' : student.department) : '';

        authLi.innerHTML = `
          <a href="dashboard.html" style="text-decoration:none; display:inline-flex; align-items:center; gap:6px; background:var(--indigo-soft, #eceeff); color:var(--indigo, #4a55d0); font-size:0.82rem; font-weight:600; padding:4px 10px; border-radius:20px; border:1px solid #c7d2fe;">
            <span>🎓</span> ${firstName} ${deptShort ? `(${deptShort})` : ''}
          </a>
          <button id="navLogoutBtn" type="button" style="background:transparent; border:1px solid var(--border, #e4e7f0); color:var(--ink-2, #454b6b); font-size:0.78rem; font-weight:600; padding:4px 9px; border-radius:6px; cursor:pointer; transition:all 0.15s;">
            Logout
          </button>
        `;

        linksList.appendChild(authLi);

        const logoutBtn = authLi.querySelector('#navLogoutBtn');
        if (logoutBtn) {
          logoutBtn.addEventListener('click', async () => {
            try {
              await fetch('http://127.0.0.1:5001/api/auth/logout', { method: 'POST' });
            } catch (err) {}
            localStorage.removeItem('srs_session_student');
            localStorage.removeItem('srs_token');
            localStorage.removeItem('srs_student_id');
            localStorage.removeItem('srs_student_name');
            sessionStorage.clear();
            window.location.href = 'login.html';
          });
        }
      } catch (e) {
        linksList.innerHTML += `<li><a href="login.html" class="nav-link" data-page="login" style="font-weight:600; color:var(--indigo);">Portal Sign In</a></li>`;
      }
    } else {
      authLi.innerHTML = `
        <a href="login.html" style="text-decoration:none; display:inline-flex; align-items:center; gap:6px; background:var(--indigo, #4a55d0); color:#fff; font-size:0.84rem; font-weight:600; padding:5px 12px; border-radius:8px;">
          Student Sign In →
        </a>
      `;
      linksList.appendChild(authLi);
    }
  }

  // ── Mobile hamburger ────────────────────────────────────────────────────────
  if (!nav || !linksList) return;

  const btn = document.createElement('button');
  btn.className = 'nav-hamburger';
  btn.setAttribute('aria-label', 'Toggle navigation');
  btn.setAttribute('aria-expanded', 'false');
  btn.innerHTML = '<span></span><span></span><span></span>';
  nav.appendChild(btn);

  function closeMenu() {
    linksList.classList.remove('nav-open');
    btn.setAttribute('aria-expanded', 'false');
    btn.classList.remove('is-open');
  }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    const open = linksList.classList.toggle('nav-open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.classList.toggle('is-open', open);
  });

  // Close on outside click
  document.addEventListener('click', function (e) {
    if (!nav.contains(e.target)) closeMenu();
  });

  // Close when a nav link is clicked (useful on mobile)
  linksList.querySelectorAll('.nav-link').forEach(function (a) {
    a.addEventListener('click', closeMenu);
  });

  // Close on Escape key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMenu();
  });
});
