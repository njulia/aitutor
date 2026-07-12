'use strict';

function notice(message, type) {
  const box = document.getElementById('forgot-notice');
  box.textContent = '';
  box.className = `notice show ${type}`;
  const text = document.createElement('span');
  text.textContent = message;
  box.appendChild(text);
}

document.getElementById('forgot-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.getElementById('forgot-button');
  const email = document.getElementById('email').value.trim().toLowerCase();
  button.disabled = true;
  button.textContent = 'Sending…';
  try {
    const response = await fetch('/api/password-reset/request', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'same-origin',
      body: JSON.stringify({email})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'The request could not be completed.');
    notice(data.message, 'success');
    document.getElementById('forgot-form').reset();
    if (data.dev_reset_url) {
      const box = document.getElementById('forgot-notice');
      const p = document.createElement('p');
      p.className = 'dev-link';
      const a = document.createElement('a');
      a.href = data.dev_reset_url;
      a.textContent = 'Open the development reset link';
      p.appendChild(a);
      box.appendChild(p);
    }
  } catch (error) {
    notice(error.message || 'The request could not be completed.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Send reset link';
  }
});
