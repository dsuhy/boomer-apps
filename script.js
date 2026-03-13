// Nav scroll
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 30);
});

// Mobile menu
const menuBtn = document.querySelector('.menu-btn');
const navLinks = document.querySelector('.nav-links');

menuBtn.addEventListener('click', () => {
  const open = navLinks.classList.toggle('open');
  menuBtn.setAttribute('aria-expanded', open);
});

navLinks.querySelectorAll('a').forEach(a => {
  a.addEventListener('click', () => {
    navLinks.classList.remove('open');
    menuBtn.setAttribute('aria-expanded', 'false');
  });
});

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const t = document.querySelector(a.getAttribute('href'));
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth' }); }
  });
});

// Form
const form = document.getElementById('quote-form');
const status = document.getElementById('form-status');

form.addEventListener('submit', e => {
  e.preventDefault();
  form.querySelectorAll('.field').forEach(f => f.classList.remove('has-error'));
  status.textContent = '';
  status.className = '';

  const name = form.querySelector('#name');
  const phone = form.querySelector('#phone');
  const service = form.querySelector('#service');
  let ok = true;

  [name, phone, service].forEach(el => {
    if (!el.value || !el.value.trim()) {
      el.closest('.field').classList.add('has-error');
      ok = false;
    }
  });

  if (!ok) {
    status.textContent = 'Fill in the required fields.';
    status.className = 'error';
    return;
  }

  const data = {
    name: name.value.trim(),
    phone: phone.value.trim(),
    email: form.querySelector('#email').value.trim(),
    service: service.value,
    vehicle: form.querySelector('#vehicle').value.trim(),
    message: form.querySelector('#message').value.trim(),
    timestamp: new Date().toISOString()
  };

  const leads = JSON.parse(localStorage.getItem('leads') || '[]');
  leads.push(data);
  localStorage.setItem('leads', JSON.stringify(leads));

  status.textContent = "Got it — Shalend will be in touch soon.";
  status.className = 'success';
  form.reset();

  setTimeout(() => { status.textContent = ''; status.className = ''; }, 5000);
});
