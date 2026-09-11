// ── auth.js: SmartRecSys Campus Authentication & Session Management ───────────

document.addEventListener('DOMContentLoaded', () => {
  const tabLoginBtn = document.getElementById('tabLoginBtn');
  const tabRegisterBtn = document.getElementById('tabRegisterBtn');
  const loginContent = document.getElementById('loginTabContent');
  const registerContent = document.getElementById('registerTabContent');
  const authAlert = document.getElementById('authAlert');

  // Tab switching
  if (tabLoginBtn && tabRegisterBtn) {
    tabLoginBtn.addEventListener('click', () => {
      tabLoginBtn.classList.add('active');
      tabRegisterBtn.classList.remove('active');
      loginContent.style.display = 'block';
      registerContent.style.display = 'none';
      hideAlert();
    });

    tabRegisterBtn.addEventListener('click', () => {
      tabRegisterBtn.classList.add('active');
      tabLoginBtn.classList.remove('active');
      loginContent.style.display = 'none';
      registerContent.style.display = 'block';
      hideAlert();
    });
  }

  // Alert helpers
  function showAlert(msg, isSuccess = false) {
    if (!authAlert) return;
    authAlert.textContent = msg;
    authAlert.className = isSuccess ? 'auth-alert success' : 'auth-alert error';
  }

  function hideAlert() {
    if (!authAlert) return;
    authAlert.className = 'auth-alert';
    authAlert.textContent = '';
  }

  // Helper to persist student session and redirect to dashboard
  function completeStudentLogin(student, token) {
    localStorage.setItem('srs_session_student', JSON.stringify(student));
    localStorage.setItem('srs_token', token || '');
    localStorage.setItem('srs_student_id', student.id);
    localStorage.setItem('srs_student_name', student.name);

    // Save session storage variables for dashboard & back navigation
    sessionStorage.setItem('srs_studentName', student.name);
    sessionStorage.setItem('srs_department', student.department);
    sessionStorage.setItem('srs_degree', student.degree);
    sessionStorage.setItem('srs_batch', student.year);
    sessionStorage.setItem('srs_semester', student.semester);
    sessionStorage.setItem('srs_cgpa', student.cgpa !== null ? student.cgpa : '');
    sessionStorage.setItem('srs_completedCourses', student.completed_courses || '');
    sessionStorage.setItem('srs_currentCourses', student.current_courses || '');
    sessionStorage.setItem('srs_careerGoal', student.career_goal || '');
    sessionStorage.setItem('srs_domainInterest', JSON.stringify(student.domains || []));
    sessionStorage.setItem('srs_level', student.difficulty || 'Beginner');

    const params = new URLSearchParams({
      name:              student.name,
      dept:              student.department,
      degree:            student.degree,
      batch:             student.year,
      semester:          String(student.semester),
      cgpa:              student.cgpa !== null ? String(student.cgpa) : '',
      completed_courses: student.completed_courses || '',
      current_courses:   student.current_courses || '',
      domains:           (student.domains || []).join(','),
      level:             student.difficulty || 'Beginner',
      goal:              student.career_goal || 'Software Engineer',
      roll:              student.roll_number || ''
    });

    showAlert(`Welcome back, ${student.name}! Redirecting to Student Portal...`, true);
    setTimeout(() => {
      window.location.href = 'dashboard.html?' + params.toString();
    }, 450);
  }

  // ── Handle Sign In ────────────────────────────────────────────────────────
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideAlert();

      const identifier = document.getElementById('loginIdentifier').value.trim();
      const password   = document.getElementById('loginPassword').value;
      const submitBtn  = document.getElementById('loginSubmitBtn');

      if (!identifier || !password) {
        showAlert('Please enter both your email/roll number and password.');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span>Verifying credentials...</span>';

      try {
        const res = await fetch('http://127.0.0.1:5001/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier, password })
        });

        const data = await res.json();
        if (!res.ok) {
          showAlert(data.error || 'Authentication failed. Please verify credentials.');
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span>Sign In to Student Portal →</span>';
          return;
        }

        completeStudentLogin(data.student, data.token);
      } catch (err) {
        showAlert('Could not connect to backend server. Make sure server.py is running on port 5001.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Sign In to Student Portal →</span>';
      }
    });
  }

  // ── Handle Registration ───────────────────────────────────────────────────
  const regForm = document.getElementById('registerForm');
  if (regForm) {
    regForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideAlert();

      const name     = document.getElementById('regName').value.trim();
      const email    = document.getElementById('regEmail').value.trim().toLowerCase();
      const password = document.getElementById('regPassword').value;
      const roll     = document.getElementById('regRoll').value.trim();
      const dept     = document.getElementById('regDept').value;
      const degree   = document.getElementById('regDegree').value;
      const semester = parseInt(document.getElementById('regSemester').value, 10);
      const cgpaVal  = document.getElementById('regCgpa').value;
      const cgpa     = cgpaVal ? parseFloat(cgpaVal) : null;
      const completed = document.getElementById('regCompleted').value.trim();
      const goal     = document.getElementById('regCareerGoal').value;
      const diff     = document.getElementById('regDifficulty').value;

      const domains = [...document.querySelectorAll('[name="regDomain"]:checked')].map(c => c.value);

      if (!name || !email || !password) {
        showAlert('Please fill in all required credentials.');
        return;
      }
      if (domains.length === 0) {
        showAlert('Please select at least one domain interest.');
        return;
      }

      const submitBtn = document.getElementById('regSubmitBtn');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span>Registering student profile...</span>';

      const payload = {
        name,
        email,
        password,
        roll_number: roll,
        department: dept,
        degree: degree,
        year: semester <= 2 ? '1st Year' : semester <= 4 ? '2nd Year' : semester <= 6 ? '3rd Year' : '4th Year',
        semester: semester,
        cgpa: cgpa,
        completed_courses: completed,
        current_courses: '',
        domains: domains,
        difficulty: diff,
        career_goal: goal
      };

      try {
        const res = await fetch('http://127.0.0.1:5001/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
          showAlert(data.error || 'Registration failed.');
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span>Register Account & Enter Portal →</span>';
          return;
        }

        completeStudentLogin(data.student, data.token);
      } catch (err) {
        showAlert('Could not connect to backend server. Make sure server.py is running on port 5001.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Register Account & Enter Portal →</span>';
      }
    });
  }
});

// Quick 1-click login function exposed globally for buttons
window.quickFillLogin = function(identifier, password) {
  const idInput = document.getElementById('loginIdentifier');
  const passInput = document.getElementById('loginPassword');
  if (idInput && passInput) {
    idInput.value = identifier;
    passInput.value = password;
    document.getElementById('loginSubmitBtn').click();
  }
};
