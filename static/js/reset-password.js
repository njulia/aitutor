'use strict';

const params = new URLSearchParams(window.location.search);
const token = params.get('token') || '';
const form = document.getElementById('reset-form');

function notice(message, type) {
  const box = document.getElementById('reset-notice');
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

async function validateLink() {
  if (!token) {
    notice('This reset link is missing its security token. Please request a new link.', 'error');
    return;
  }
  try {
    const response = await fetch(`/api/password-reset/validate?token=${encodeURIComponent(token)}`, {credentials:'same-origin'});
    const data = await response.json();
    if (!data.valid) {
      notice('This reset link is invalid or has expired. Please request a new one.', 'error');
      return;
    }
    form.hidden = false;
  } catch (_) {
    notice('The reset link could not be checked. Please try again.', 'error');
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const password = document.getElementById('password').value;
  const confirmPassword = document.getElementById('confirm-password').value;
  if (password !== confirmPassword) {
    notice('The passwords do not match.', 'error');
    return;
  }
  const button = document.getElementById('reset-button');
  button.disabled = true;
  button.textContent = 'Changing…';
  try {
    const response = await fetch('/api/password-reset/confirm', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      credentials: 'same-origin',
      body: JSON.stringify({token, password, confirm_password: confirmPassword})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'The password could not be changed.');
    localStorage.removeItem('student_id');
    localStorage.removeItem('student_email');
    form.hidden = true;
    notice(data.message, 'success');
    setTimeout(() => window.location.assign('/login'), 1800);
  } catch (error) {
    notice(error.message || 'The password could not be changed.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Change password';
  }
});

validateLink();
