// Navbar hamburger
const btn = document.getElementById('hamburgerBtn');
const menu = document.getElementById('navMenu');

if (btn && menu) {
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('nav-open');
  });

  // Cerrar menú al hacer clic fuera
  document.addEventListener('click', (e) => {
    if (!btn.contains(e.target) && !menu.contains(e.target)) {
      menu.classList.remove('nav-open');
    }
  });
}

// Navbar scroll
const nav = document.getElementById('mainNav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('nav-scrolled', window.scrollY > 60);
  });
}

// Animate on scroll
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) e.target.classList.add('anim-in');
  });
}, { threshold: 0.1 });

document.querySelectorAll('.anim').forEach(el => observer.observe(el));