// ── Dashboard access guard ────────────────────────────────────────────────────
// Runs immediately (before DOM parse) so the redirect is instant.
// dashboard.html loads this script as the very first thing in <body>.
(function () {
  const page = window.location.pathname.split('/').pop();
  if (page === 'dashboard.html') {
    const name = new URLSearchParams(window.location.search).get('name');
    if (!name || !name.trim()) {
      window.location.replace('welcome.html');
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

  // ── Mobile hamburger ────────────────────────────────────────────────────────
  const nav = document.querySelector('.topnav');
  if (!nav) return;

  const btn = document.createElement('button');
  btn.className = 'nav-hamburger';
  btn.setAttribute('aria-label', 'Toggle navigation');
  btn.setAttribute('aria-expanded', 'false');
  btn.innerHTML = '<span></span><span></span><span></span>';
  nav.appendChild(btn);

  const linksList = nav.querySelector('.nav-links');

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
