'use strict';

(function initialiseHomeAuthNavigation() {
  const loginLinks = Array.from(document.querySelectorAll(
    '#home-login-link, [data-auth-login], a[href="/login"], a[href^="/login?"]'
  ));
  const logoutLinks = Array.from(document.querySelectorAll(
    '#home-logout-link, [data-auth-logout], body:not(.hm-app) #logout-link'
  ));
  const parentDashboardLinks = Array.from(document.querySelectorAll(
    '#parent-dashboard-link, a[href="/parent-dashboard"]'
  ));
  const parentPlanLinks = Array.from(document.querySelectorAll('#parent-plan-link'));
  const kidProgressLinks = Array.from(document.querySelectorAll('#kid-progress-link'));
  const kidRewardsLinks = Array.from(document.querySelectorAll('#kid-rewards-link'));
  const registerLinks = Array.from(document.querySelectorAll('a[href="/register"]'));
  const avatarHost = document.querySelector(
    '.hm-nav-wrap, .header-content, .header-inner, body.hm-page > header'
  );
  let activeRole = 'anonymous';
  let avatarRoot = null;
  let logoutPending = false;

  function setVisible(nodes, visible) {
    nodes.forEach((node) => {
      node.hidden = !visible;
      node.style.display = visible ? '' : 'none';
    });
  }

  function appendTextElement(parent, tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function closeAvatarMenu(returnFocus) {
    if (!avatarRoot) return;
    const button = avatarRoot.querySelector('[data-kid-avatar-button]');
    const menu = avatarRoot.querySelector('[data-kid-avatar-menu]');
    if (!button || !menu) return;
    menu.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    avatarRoot.classList.remove('is-open');
    if (returnFocus) button.focus();
  }

  function avatarColour(name) {
    let score = 0;
    for (let index = 0; index < name.length; index += 1) {
      score = (score + name.charCodeAt(index) * (index + 1)) % 4;
    }
    return String(score);
  }

  function createAvatarAction(href, icon, label, detail) {
    const link = document.createElement('a');
    link.className = 'hm-kid-avatar-action';
    link.href = href;

    appendTextElement(link, 'span', 'hm-kid-avatar-action-icon', icon)
      .setAttribute('aria-hidden', 'true');
    const copy = document.createElement('span');
    appendTextElement(copy, 'strong', '', label);
    appendTextElement(copy, 'small', '', detail);
    link.appendChild(copy);
    return link;
  }

  function ensureKidAvatar() {
    if (avatarRoot) return avatarRoot;

    avatarRoot = document.createElement('div');
    avatarRoot.className = 'hm-kid-avatar';
    avatarRoot.setAttribute('data-kid-avatar', '');
    avatarRoot.hidden = true;

    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'kid-avatar-button';
    button.className = 'hm-kid-avatar-button';
    button.setAttribute('data-kid-avatar-button', '');
    button.setAttribute('aria-haspopup', 'true');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', 'kid-avatar-menu');

    const face = document.createElement('span');
    face.className = 'hm-kid-avatar-face';
    face.setAttribute('aria-hidden', 'true');
    appendTextElement(face, 'span', 'hm-kid-avatar-star', '★');
    button.appendChild(face);
    avatarRoot.appendChild(button);

    const menu = document.createElement('section');
    menu.id = 'kid-avatar-menu';
    menu.className = 'hm-kid-avatar-menu';
    menu.setAttribute('data-kid-avatar-menu', '');
    menu.setAttribute('aria-labelledby', 'kid-avatar-button');
    menu.hidden = true;

    const welcome = document.createElement('div');
    welcome.className = 'hm-kid-avatar-welcome';
    const miniFace = document.createElement('span');
    miniFace.className = 'hm-kid-avatar-face hm-kid-avatar-face-small';
    miniFace.setAttribute('aria-hidden', 'true');
    welcome.appendChild(miniFace);
    const welcomeCopy = document.createElement('div');
    appendTextElement(welcomeCopy, 'strong', 'hm-kid-avatar-name', 'Hi, Learner!')
      .setAttribute('data-kid-avatar-name', '');
    appendTextElement(welcomeCopy, 'span', 'hm-kid-avatar-year', 'Your learning space')
      .setAttribute('data-kid-avatar-year', '');
    welcome.appendChild(welcomeCopy);
    menu.appendChild(welcome);

    const actions = document.createElement('nav');
    actions.className = 'hm-kid-avatar-actions';
    actions.setAttribute('aria-label', 'My learning shortcuts');
    actions.appendChild(createAvatarAction(
      '/app', '🚀', 'Start a quest', 'Choose today\'s practice'
    ));
    actions.appendChild(createAvatarAction(
      '/progress', '📈', 'My progress', 'See how your learning grows'
    ));
    actions.appendChild(createAvatarAction(
      '/rewards', '🎁', 'My rewards', 'Check XP, levels and rewards'
    ));
    menu.appendChild(actions);

    const logoutButton = appendTextElement(
      menu, 'button', 'hm-kid-avatar-logout', '↪ Log out of my space'
    );
    logoutButton.type = 'button';
    logoutButton.setAttribute('data-kid-avatar-logout', '');
    const status = appendTextElement(menu, 'span', 'hm-kid-avatar-status', '');
    status.setAttribute('data-kid-avatar-status', '');
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    avatarRoot.appendChild(menu);
    if (avatarHost) {
      avatarHost.classList.add('hm-kid-avatar-host');
      avatarHost.appendChild(avatarRoot);
    } else {
      avatarRoot.classList.add('hm-kid-avatar-floating');
      document.body.appendChild(avatarRoot);
    }

    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const opening = menu.hidden;
      menu.hidden = !opening;
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
      avatarRoot.classList.toggle('is-open', opening);
    });
    menu.addEventListener('click', (event) => event.stopPropagation());
    logoutButton.addEventListener('click', (event) => {
      event.preventDefault();
      performLogout(logoutButton);
    });
    document.addEventListener('click', () => closeAvatarMenu(false));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !menu.hidden) closeAvatarMenu(true);
    });

    return avatarRoot;
  }

  function renderKidAvatar(context, isKid) {
    if (!isKid) {
      if (avatarRoot) {
        closeAvatarMenu(false);
        avatarRoot.hidden = true;
      }
      if (avatarHost) avatarHost.classList.remove('hm-kid-avatar-host');
      return;
    }

    const avatar = ensureKidAvatar();
    const student = context.student || {};
    const fullName = String(student.name || 'Learner').trim() || 'Learner';
    const firstName = fullName.split(/\s+/)[0].slice(0, 24);
    const year = Number(student.year_group);
    const yearLabel = Number.isFinite(year) && year >= 1 && year <= 6
      ? `Year ${year} explorer` : 'Your learning space';
    const button = avatar.querySelector('[data-kid-avatar-button]');
    const name = avatar.querySelector('[data-kid-avatar-name]');
    const yearCopy = avatar.querySelector('[data-kid-avatar-year]');
    const status = avatar.querySelector('[data-kid-avatar-status]');

    avatar.setAttribute('data-avatar-colour', avatarColour(fullName));
    avatar.hidden = false;
    if (avatarHost) avatarHost.classList.add('hm-kid-avatar-host');
    button.setAttribute('aria-label', `Open ${firstName}'s learning menu`);
    button.title = `${firstName}'s learning menu`;
    name.textContent = `Hi, ${firstName}!`;
    yearCopy.textContent = yearLabel;
    status.textContent = '';
  }

  function render(context) {
    const loggedIn = Boolean(context && context.authenticated);
    const isParent = loggedIn && context.role === 'parent';
    const isKid = loggedIn && context.role === 'kid';
    activeRole = loggedIn ? context.role : 'anonymous';

    setVisible(loginLinks, !loggedIn);
    // Kids use the avatar menu, which keeps the crowded header simpler.
    setVisible(logoutLinks, loggedIn && !isKid);
    setVisible(registerLinks, !loggedIn);
    setVisible(parentDashboardLinks, isParent);
    setVisible(parentPlanLinks, isParent);
    setVisible(kidProgressLinks, isKid);
    setVisible(kidRewardsLinks, isKid);
    renderKidAvatar(context || {}, isKid);

    parentDashboardLinks.forEach((parentDashboardLink) => {
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
    });
  }

  function clearLocalSession() {
    try {
      ['auth_state', 'student_id', 'student_email', 'kid_session_token',
        'kid_student_id', 'kid_student_name'].forEach(
        (key) => window.localStorage.removeItem(key)
      );
    } catch (error) {
      console.warn('Could not clear local login hints:', error);
    }
  }

  async function performLogout(trigger) {
    if (logoutPending) return;
    logoutPending = true;
    const originalText = trigger.textContent;
    const status = avatarRoot
      ? avatarRoot.querySelector('[data-kid-avatar-status]') : null;
    trigger.textContent = 'Logging out…';
    trigger.setAttribute('aria-disabled', 'true');
    if ('disabled' in trigger) trigger.disabled = true;
    if (status) status.textContent = 'Closing your learning space…';

    try {
      const logoutUrl = activeRole === 'kid' ? '/api/kid-logout' : '/api/logout';
      const response = await fetch(logoutUrl, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Accept': 'application/json'}
      });
      if (!response.ok) throw new Error('Logout request failed.');
      clearLocalSession();
      if (window.HomeworkMagicSession) window.HomeworkMagicSession.clear();
      window.location.assign('/');
    } catch (error) {
      console.error('Logout failed:', error);
      logoutPending = false;
      trigger.textContent = originalText;
      trigger.removeAttribute('aria-disabled');
      if ('disabled' in trigger) trigger.disabled = false;
      const message = 'We could not log you out just now. Please try again.';
      if (status) status.textContent = message;
      else window.alert(message);
    }
  }

  async function refreshLoginStatus(force = false) {
    try {
      const context = window.HomeworkMagicSession
        ? await window.HomeworkMagicSession.get(force)
        : await fetch('/api/session-context', {
            credentials: 'same-origin', cache: 'no-store',
            headers: {'Accept': 'application/json'}
          }).then((response) => {
            if (!response.ok) throw new Error('Session request failed.');
            return response.json();
          });
      render(context);
      try {
        if (context.authenticated && context.role === 'parent') {
          window.localStorage.setItem('auth_state', 'logged_in');
        } else {
          window.localStorage.removeItem('auth_state');
        }
      } catch (error) {
        console.warn('Could not save the local login hint:', error);
      }
    } catch (error) {
      console.warn('Could not refresh login status:', error);
      render({authenticated: false, role: 'anonymous'});
    }
  }

  logoutLinks.forEach((logoutLink) => {
    logoutLink.addEventListener('click', (event) => {
      event.preventDefault();
      performLogout(logoutLink);
    });
  });

  window.HomeworkMagicAuthNavigation = {
    refresh: refreshLoginStatus,
    render: render,
  };
  refreshLoginStatus();
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) refreshLoginStatus(true);
  });
  window.addEventListener('storage', (event) => {
    if (event.key === 'auth_state') refreshLoginStatus(true);
  });
})();
