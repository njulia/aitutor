'use strict';

(function initialiseHomeAuthNavigation() {
  const loginLinks = Array.from(document.querySelectorAll(
    '#home-login-link, [data-auth-login]'
  ));
  const logoutLinks = Array.from(document.querySelectorAll(
    '#home-logout-link, [data-auth-logout]'
  ));
  const parentDashboardLink = document.getElementById('parent-dashboard-link');
  const parentPlanLink = document.getElementById('parent-plan-link');
  const kidProgressLink = document.getElementById('kid-progress-link');
  const kidRewardsLink = document.getElementById('kid-rewards-link');
  const registerLinks = Array.from(document.querySelectorAll('a[href="/register"]'));
  let activeRole = 'anonymous';

  if (!loginLinks.length && !logoutLinks.length) return;

  function setVisible(nodes, visible) {
    nodes.forEach((node) => {
      node.hidden = !visible;
      node.style.display = visible ? '' : 'none';
    });
  }

  function render(context) {
    const loggedIn = Boolean(context && context.authenticated);
    const isParent = loggedIn && context.role === 'parent';
    const isKid = loggedIn && context.role === 'kid';
    activeRole = loggedIn ? context.role : 'anonymous';

    setVisible(loginLinks, !loggedIn);
    setVisible(logoutLinks, loggedIn);
    setVisible(registerLinks, !loggedIn);
    if (parentDashboardLink) parentDashboardLink.style.display = isParent ? '' : 'none';
    if (parentPlanLink) parentPlanLink.style.display = isParent ? '' : 'none';
    if (kidProgressLink) kidProgressLink.style.display = isKid ? '' : 'none';
    if (kidRewardsLink) kidRewardsLink.style.display = isKid ? '' : 'none';

    if (parentDashboardLink) {
      const oldBadge = parentDashboardLink.querySelector('.parent-badge');
      if (oldBadge) oldBadge.remove();
      const childCount = isParent && Array.isArray(context.students)
        ? context.students.length : 0;
      if (childCount) {
        const badge = document.createElement('span');
        badge.className = 'parent-badge';
        badge.textContent = ` 👪 ${childCount}`;
        badge.setAttribute('aria-label', `${childCount} learner profiles`);
        parentDashboardLink.appendChild(badge);
      }
    }
  }

  async function refreshLoginStatus(force = false) {
    try {
      const context = window.HomeworkMagicSession
        ? await window.HomeworkMagicSession.get(force)
        : await fetch('/api/session-context', {
            credentials: 'same-origin', cache: 'no-store'
          }).then((response) => response.json());
      render(context);
      if (context.authenticated && context.role === 'parent') {
        localStorage.setItem('auth_state', 'logged_in');
      } else {
        localStorage.removeItem('auth_state');
      }
    } catch (error) {
      console.warn('Could not refresh login status:', error);
      render({authenticated: false, role: 'anonymous'});
    }
  }

  logoutLinks.forEach((logoutLink) => {
    logoutLink.addEventListener('click', async function logout(event) {
      event.preventDefault();
      const originalText = logoutLink.textContent;
      logoutLink.textContent = 'Logging out…';
      logoutLink.setAttribute('aria-disabled', 'true');
      try {
        const logoutUrl = activeRole === 'kid' ? '/api/kid-logout' : '/api/logout';
        const response = await fetch(logoutUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Accept': 'application/json'}
        });
        if (!response.ok) throw new Error('Logout request failed.');
        ['auth_state', 'student_id', 'student_email', 'kid_session_token',
          'kid_student_id', 'kid_student_name'].forEach((key) => localStorage.removeItem(key));
        if (window.HomeworkMagicSession) window.HomeworkMagicSession.clear();
        window.location.assign('/');
      } catch (error) {
        console.error('Logout failed:', error);
        logoutLink.textContent = originalText;
        logoutLink.removeAttribute('aria-disabled');
        window.alert('We could not log you out just now. Please try again.');
      }
    });
  });

  refreshLoginStatus();
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) refreshLoginStatus(true);
  });
  window.addEventListener('storage', (event) => {
    if (event.key === 'auth_state') refreshLoginStatus(true);
  });
})();
