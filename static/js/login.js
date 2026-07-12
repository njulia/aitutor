'use strict';

function showNotice(message, type) {
  const box = document.getElementById('login-notice');
  box.textContent = message;
  box.className = `notice show ${type}`;
}

document.querySelectorAll('.show-password').forEach((button) => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.target);
    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    button.textContent = showing ? 'Show' : 'Hide';
    button.setAttribute('aria-pressed', String(!showing));
  });
});

document.getElementById('login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = document.getElementById('email').value.trim().toLowerCase();
  const password = document.getElementById('password').value;
  const button = document.getElementById('login-button');
  button.disabled = true;
  button.textContent = 'Logging in…';
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'same-origin',
      body: JSON.stringify({email, password})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.success) throw new Error(data.error || data.detail || 'Login failed.');
    localStorage.setItem('student_id', data.username || email);
    localStorage.setItem('student_email', data.username || email);
    window.location.assign('/app');
  } catch (error) {
    showNotice(error.message || 'Login failed. Please try again.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Log in';
  }
});
