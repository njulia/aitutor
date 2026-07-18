'use strict';

(function initialiseHomeAuthNavigation() {
  const loginLink = document.getElementById('home-login-link');
  const logoutLink = document.getElementById('home-logout-link');

  if (!loginLink || !logoutLink) return;

  function renderLoggedIn(loggedIn) {
    loginLink.hidden = loggedIn;
    logoutLink.hidden = !loggedIn;
  }

  async function refreshLoginStatus() {
    try {
      const response = await fetch('/api/check-subscription', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {'Accept': 'application/json'}
      });

      if (!response.ok) throw new Error('Login status request failed.');
      const data = await response.json();
      const loggedIn = data.logged_in === true;
      renderLoggedIn(loggedIn);

      if (loggedIn) {
        localStorage.setItem('auth_state', 'logged_in');
      } else {
        localStorage.removeItem('auth_state');
      }
    } catch (error) {
      console.warn('Could not refresh login status:', error);
      // Keep the safe default: show Sign in unless the server confirms a session.
      renderLoggedIn(false);
    }
  }

  logoutLink.addEventListener('click', async function logout(event) {
    event.preventDefault();
    const originalText = logoutLink.textContent;
    logoutLink.textContent = 'Logging out…';
    logoutLink.setAttribute('aria-disabled', 'true');

    try {
      const response = await fetch('/api/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Accept': 'application/json'}
      });
      if (!response.ok) throw new Error('Logout request failed.');

      localStorage.removeItem('auth_state');
      localStorage.removeItem('student_id');
      localStorage.removeItem('student_email');
      window.location.assign('/');
    } catch (error) {
      console.error('Logout failed:', error);
      logoutLink.textContent = originalText;
      logoutLink.removeAttribute('aria-disabled');
      window.alert('We could not log you out just now. Please try again.');
    }
  });

  refreshLoginStatus();

  // Refresh after returning from the login page using the browser back button.
  window.addEventListener('pageshow', function onPageShow(event) {
    if (event.persisted) refreshLoginStatus();
  });

  // Keep another open home-page tab in sync after login or logout elsewhere.
  window.addEventListener('storage', function onAuthStorageChange(event) {
    if (event.key === 'auth_state') refreshLoginStatus();
  });
})();
