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
  const Avatar = window.HomeworkMagicAvatar || null;
  let activeRole = 'anonymous';
  let avatarRoot = null;
  let avatarState = null;
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

  function renderAvatarGrowth(state) {
    if (!avatarRoot || !state) return;
    const growth = state.growth;
    const age = state.age;
    avatarRoot.setAttribute('data-growth-stage', String(growth.stage));
    avatarRoot.setAttribute('data-age-stage', String(age.stage));
    const name = avatarRoot.querySelector('[data-avatar-growth-name]');
    const xp = avatarRoot.querySelector('[data-avatar-growth-xp]');
    const progress = avatarRoot.querySelector('[data-avatar-growth-progress]');
    const next = avatarRoot.querySelector('[data-avatar-growth-next]');
    const ageCopy = avatarRoot.querySelector('[data-avatar-age-copy]');
    if (name) name.textContent = growth.name;
    if (xp) xp.textContent = `${growth.lifetime_xp} XP`;
    if (progress) {
      progress.value = growth.progress_percent;
      progress.textContent = `${growth.progress_percent}%`;
    }
    if (next) {
      next.textContent = growth.next_stage
        ? `${growth.xp_to_next} XP until ${growth.next_stage.name}`
        : 'Your learning glow is fully grown!';
    }
    if (ageCopy) {
      ageCopy.textContent = `Age ${age.age} look • ${age.label}`;
    }
  }

  function applyAvatarState(summary, learner) {
    if (!Avatar || !avatarRoot) return;
    avatarState = Avatar.normaliseState(summary, learner);
    Avatar.applyAll(avatarRoot, avatarState.profile, {
      age: avatarState.age.age,
      lifetime_xp: avatarState.growth.lifetime_xp,
    });
    renderAvatarGrowth(avatarState);
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

  function createReaction(action, icon, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'hm-kid-avatar-reaction';
    button.setAttribute('data-avatar-reaction', action);
    button.setAttribute('aria-label', `${label} with my character`);
    button.textContent = `${icon} ${label}`;
    return button;
  }

  function playReaction(action) {
    if (!Avatar || !avatarRoot) return;
    Avatar.playAll(avatarRoot, action);
    const firstName = avatarRoot.getAttribute('data-learner-first-name') || 'Your character';
    const status = avatarRoot.querySelector('[data-avatar-reaction-status]');
    const messages = {
      dance: `${firstName} does a happy dance!`,
      celebrate: `${firstName} celebrates your effort!`,
    };
    if (status) status.textContent = messages[action] || messages.celebrate;
  }

  function ensureKidAvatar() {
    if (avatarRoot) return avatarRoot;
    if (!Avatar) {
      console.warn('The learner character could not be loaded.');
      return null;
    }

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
    button.appendChild(Avatar.createFigure('hm-character-avatar-button-figure'));
    avatarRoot.appendChild(button);

    const menu = document.createElement('section');
    menu.id = 'kid-avatar-menu';
    menu.className = 'hm-kid-avatar-menu';
    menu.setAttribute('data-kid-avatar-menu', '');
    menu.setAttribute('aria-labelledby', 'kid-avatar-button');
    menu.hidden = true;

    const welcome = document.createElement('div');
    welcome.className = 'hm-kid-avatar-welcome';
    welcome.appendChild(Avatar.createFigure('hm-character-avatar-mini'));
    const welcomeCopy = document.createElement('div');
    appendTextElement(welcomeCopy, 'strong', 'hm-kid-avatar-name', 'Hi, Learner!')
      .setAttribute('data-kid-avatar-name', '');
    appendTextElement(welcomeCopy, 'span', 'hm-kid-avatar-year', 'Your learning space')
      .setAttribute('data-kid-avatar-year', '');
    welcome.appendChild(welcomeCopy);
    menu.appendChild(welcome);

    const growth = document.createElement('section');
    growth.className = 'hm-kid-avatar-growth';
    growth.setAttribute('aria-label', 'Character growth');
    const growthHeading = document.createElement('div');
    appendTextElement(
      growthHeading, 'strong', 'hm-kid-avatar-growth-name', 'Little Learner'
    ).setAttribute('data-avatar-growth-name', '');
    appendTextElement(
      growthHeading, 'span', 'hm-kid-avatar-growth-xp', '0 XP'
    ).setAttribute('data-avatar-growth-xp', '');
    growth.appendChild(growthHeading);
    const growthProgress = document.createElement('progress');
    growthProgress.className = 'hm-kid-avatar-growth-progress';
    growthProgress.max = 100;
    growthProgress.value = 0;
    growthProgress.setAttribute('data-avatar-growth-progress', '');
    growthProgress.setAttribute('aria-label', 'Progress to the next character glow');
    growth.appendChild(growthProgress);
    appendTextElement(
      growth, 'small', 'hm-kid-avatar-growth-next', '100 XP until Curious Explorer'
    ).setAttribute('data-avatar-growth-next', '');
    appendTextElement(
      growth, 'small', 'hm-kid-avatar-age-copy', 'Age 7 look • Bright Explorer'
    ).setAttribute('data-avatar-age-copy', '');
    menu.appendChild(growth);

    const reactions = document.createElement('div');
    reactions.className = 'hm-kid-avatar-reactions';
    reactions.setAttribute('aria-label', 'Play with my character');
    reactions.appendChild(createReaction('dance', '🎵', 'Dance'));
    reactions.appendChild(createReaction('celebrate', '✨', 'Cheer'));
    menu.appendChild(reactions);
    const reactionStatus = appendTextElement(menu, 'span', 'hm-kid-avatar-reaction-status', '');
    reactionStatus.setAttribute('data-avatar-reaction-status', '');
    reactionStatus.setAttribute('role', 'status');
    reactionStatus.setAttribute('aria-live', 'polite');

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
    actions.appendChild(createAvatarAction(
      '/playtime', '🦫', 'Pet playtime', 'Care for your little friend'
    ));
    menu.appendChild(actions);

    const customiseLink = document.createElement('a');
    customiseLink.className = 'hm-kid-avatar-customise-toggle';
    customiseLink.href = '/character-customise';
    customiseLink.textContent = '🎨 Customise my character';
    menu.appendChild(customiseLink);

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
    reactions.addEventListener('click', (event) => {
      event.stopPropagation();
      const trigger = event.target.closest('[data-avatar-reaction]');
      if (trigger) playReaction(trigger.getAttribute('data-avatar-reaction'));
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
      avatarState = null;
      if (avatarRoot) {
        closeAvatarMenu(false);
        avatarRoot.hidden = true;
      }
      if (avatarHost) avatarHost.classList.remove('hm-kid-avatar-host');
      return;
    }

    const avatar = ensureKidAvatar();
    if (!avatar) return;
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
    const reactionStatus = avatar.querySelector('[data-avatar-reaction-status]');

    avatar.hidden = false;
    avatar.setAttribute('data-learner-first-name', firstName);
    if (avatarHost) avatarHost.classList.add('hm-kid-avatar-host');
    button.setAttribute('aria-label', `Open ${firstName}'s learning menu`);
    button.title = `${firstName}'s learning menu`;
    name.textContent = `Hi, ${firstName}!`;
    yearCopy.textContent = yearLabel;
    status.textContent = '';
    reactionStatus.textContent = '';
    applyAvatarState(context.avatar || null, student);
  }

  function render(context) {
    const loggedIn = Boolean(context && context.authenticated);
    const isParent = loggedIn && (context.role === 'parent' || context.role === 'teacher');
    const isKid = loggedIn && context.role === 'kid';
    activeRole = loggedIn ? context.role : 'anonymous';

    setVisible(loginLinks, !loggedIn);
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
        if (context.authenticated && (context.role === 'parent' || context.role === 'teacher')) {
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

  window.addEventListener('homeworkmagic:xp-updated', (event) => {
    if (activeRole !== 'kid' || !avatarRoot || !Avatar) return;
    const detail = event && event.detail && typeof event.detail === 'object'
      ? event.detail : {};
    if (!Number.isFinite(Number(detail.lifetime_xp))) return;
    applyAvatarState({
      profile: avatarState ? avatarState.profile : null,
      growth: {lifetime_xp: Number(detail.lifetime_xp)},
    }, {age: avatarState ? avatarState.age.age : 7});
  });

  window.addEventListener('homeworkmagic:avatar-updated', () => {
    refreshLoginStatus(true);
  });

  window.HomeworkMagicAuthNavigation = {
    refresh: refreshLoginStatus,
    render,
  };
  refreshLoginStatus();
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) refreshLoginStatus(true);
  });
  window.addEventListener('storage', (event) => {
    if (event.key === 'auth_state') refreshLoginStatus(true);
  });
})();
