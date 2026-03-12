// ===== Navbar scroll effect =====
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 50);
});

// ===== Mobile nav toggle =====
const navToggle = document.querySelector('.nav-toggle');
const navLinks = document.querySelector('.nav-links');

navToggle.addEventListener('click', () => {
  const isOpen = navLinks.classList.toggle('open');
  navToggle.setAttribute('aria-expanded', isOpen);
});

// Close mobile nav when a link is clicked
navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    navLinks.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
  });
});

// ===== Smooth scroll for anchor links =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', (e) => {
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  });
});

// ===== Form handling =====
const form = document.getElementById('quote-form');
const formStatus = document.getElementById('form-status');

form.addEventListener('submit', (e) => {
  e.preventDefault();

  // Clear previous errors
  form.querySelectorAll('.form-group').forEach(g => g.classList.remove('error'));
  formStatus.textContent = '';
  formStatus.className = 'form-status';

  // Validate required fields
  const name = form.querySelector('#name');
  const phone = form.querySelector('#phone');
  const service = form.querySelector('#service');
  let valid = true;

  if (!name.value.trim()) {
    name.closest('.form-group').classList.add('error');
    valid = false;
  }
  if (!phone.value.trim()) {
    phone.closest('.form-group').classList.add('error');
    valid = false;
  }
  if (!service.value) {
    service.closest('.form-group').classList.add('error');
    valid = false;
  }

  if (!valid) {
    formStatus.textContent = 'Please fill in all required fields.';
    formStatus.className = 'form-status error';
    return;
  }

  // Collect form data
  const data = {
    name: name.value.trim(),
    phone: phone.value.trim(),
    email: form.querySelector('#email').value.trim(),
    service: service.value,
    vehicle: form.querySelector('#vehicle').value.trim(),
    message: form.querySelector('#message').value.trim(),
    timestamp: new Date().toISOString()
  };

  // Store lead locally (for demo / can be replaced with API call)
  const leads = JSON.parse(localStorage.getItem('leads') || '[]');
  leads.push(data);
  localStorage.setItem('leads', JSON.stringify(leads));

  // Show success
  formStatus.textContent = 'Thank you! We\'ll get back to you shortly.';
  formStatus.className = 'form-status success';
  form.reset();

  // Clear success message after 5 seconds
  setTimeout(() => {
    formStatus.textContent = '';
    formStatus.className = 'form-status';
  }, 5000);
});

// ===== Intersection Observer for fade-in animations =====
const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -40px 0px' };

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
      observer.unobserve(entry.target);
    }
  });
}, observerOptions);

// Animate cards on scroll
document.querySelectorAll('.service-card, .feature, .review-card, .gallery-placeholder').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
  observer.observe(el);
});
