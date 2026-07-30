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
    localStorage.setItem('auth_state', 'logged_in');
    localStorage.removeItem('student_id');
    localStorage.removeItem('student_email');
    
    // Check if user is a parent and has children
    try {
      const parentResponse = await fetch('/api/check-parent-status', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {'Accept': 'application/json'}
      });
      
      if (parentResponse.ok) {
        const parentData = await parentResponse.json();
        if (parentData.is_parent && parentData.child_count > 0) {
          // If user is a parent with children, redirect to parent dashboard
          window.location.assign('/parent-dashboard');
          return;
        }
      }
    } catch (parentError) {
      console.warn('Could not check parent status:', parentError);
      // Continue with normal redirect if parent status check fails
    }
    
    const params = new URLSearchParams(window.location.search);
    const requestedNext = params.get('next') || sessionStorage.getItem('postLoginPath') || '/app';
    const next = requestedNext.startsWith('/') && !requestedNext.startsWith('//') ? requestedNext : '/app';
    sessionStorage.removeItem('postLoginPath');
    window.location.assign(next);
  } catch (error) {
    showNotice(error.message || 'Login failed. Please try again.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Log in';
  }
});
