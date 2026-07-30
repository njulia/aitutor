'use strict';

(function initialiseHomeAuthNavigation() {
  const loginLink = document.getElementById('home-login-link');
  const logoutLink = document.getElementById('home-logout-link');
  const parentDashboardLink = document.getElementById('parent-dashboard-link');
  const registerLink = document.querySelector('a[href="/register"]');

  if (!loginLink || !logoutLink) return;

  function renderLoggedIn(loggedIn) {
    loginLink.hidden = loggedIn;
    logoutLink.hidden = !loggedIn;
    if (parentDashboardLink) {
      parentDashboardLink.style.display = loggedIn ? 'inline' : 'none';
    }
    if (registerLink) {
      registerLink.style.display = loggedIn ? 'none' : 'inline';
    }
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
        
        // Check if user is a parent and enhance the parent dashboard link
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
              // Enhance the parent dashboard link for parents
              if (parentDashboardLink) {
                // Add a visual indicator that this is important for parents
                if (!parentDashboardLink.querySelector('.parent-badge')) {
                  const badge = document.createElement('span');
                  badge.className = 'parent-badge';
                  badge.textContent = ` 👪 ${parentData.child_count} child${parentData.child_count !== 1 ? 'ren' : ''}`;
                  badge.style = 'background: #667eea; color: white; border-radius: 12px; padding: 2px 6px; font-size: 12px; margin-left: 4px;';
                  parentDashboardLink.appendChild(badge);
                }
              }
            }
          }
        } catch (parentError) {
          console.warn('Could not check parent status:', parentError);
        }
      } else {
        localStorage.removeItem('auth_state');
        // Remove parent badge if user is not logged in
        if (parentDashboardLink) {
          const badge = parentDashboardLink.querySelector('.parent-badge');
          if (badge) {
            badge.remove();
          }
        }
      }
    } catch (error) {
      console.warn('Could not refresh login status:', error);
      // Keep the safe default: show Sign in unless the server confirms a session.
      renderLoggedIn(false);
      // Remove parent badge if there's an error
      if (parentDashboardLink) {
        const badge = parentDashboardLink.querySelector('.parent-badge');
        if (badge) {
          badge.remove();
        }
      }
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
