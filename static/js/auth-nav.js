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
  let activeStudentId = '';
  let activeLearnerName = 'Learner';
  let avatarRoot = null;
  let avatarState = null;
  let avatarDraft = null;
  let avatarSavePending = false;
  let logoutPending = false;

  const AVATAR_COLOURS = [
    {value: 'purple', label: 'Magic purple', symbol: '●', index: '0'},
    {value: 'teal', label: 'Forest teal', symbol: '●', index: '1'},
    {value: 'rose', label: 'Berry pink', symbol: '●', index: '2'},
    {value: 'blue', label: 'Sky blue', symbol: '●', index: '3'},
  ];
  const AVATAR_ACCESSORIES = [
    {value: 'star', label: 'Shiny star', symbol: '★'},
    {value: 'apple', label: 'Learning apple', symbol: '🍎'},
    {value: 'bow', label: 'Bright bow', symbol: '🎀'},
    {value: 'crown', label: 'Quest crown', symbol: '👑'},
  ];
  const AVATAR_GROWTH_STAGES = [
    {stage: 1, threshold: 0, name: 'Tiny Capybara'},
    {stage: 2, threshold: 100, name: 'Curious Cub'},
    {stage: 3, threshold: 250, name: 'Growing Explorer'},
    {stage: 4, threshold: 500, name: 'Clever Capybara'},
    {stage: 5, threshold: 1000, name: 'Star Capybara'},
    {stage: 6, threshold: 2000, name: 'Legendary Capybara'},
  ];

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
    const customiser = avatarRoot.querySelector('.hm-kid-avatar-customiser');
    const customiseToggle = avatarRoot.querySelector(
      '.hm-kid-avatar-customise-toggle'
    );
    if (customiser) customiser.hidden = true;
    if (customiseToggle) customiseToggle.setAttribute('aria-expanded', 'false');
    if (avatarState) applyAvatarAppearance(avatarState.profile);
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

  function growthForXp(value) {
    const xp = Math.max(0, Number(value) || 0);
    let current = AVATAR_GROWTH_STAGES[0];
    let next = AVATAR_GROWTH_STAGES[1] || null;
    AVATAR_GROWTH_STAGES.forEach((stage, index) => {
      if (xp >= stage.threshold) {
        current = stage;
        next = AVATAR_GROWTH_STAGES[index + 1] || null;
      }
    });
    const progress = next
      ? Math.round((xp - current.threshold) /
          Math.max(1, next.threshold - current.threshold) * 100)
      : 100;
    return {
      stage: current.stage,
      name: current.name,
      lifetime_xp: xp,
      progress_percent: Math.max(0, Math.min(100, progress)),
      xp_to_next: next ? Math.max(0, next.threshold - xp) : 0,
      next_stage: next ? {
        stage: next.stage, name: next.name, threshold: next.threshold
      } : null,
    };
  }

  function validAvatarValue(options, value, fallback) {
    const selected = options.find((option) => option.value === value);
    return selected ? selected.value : fallback;
  }

  function normaliseAvatarState(summary) {
    const source = summary && typeof summary === 'object' ? summary : {};
    const profile = source.profile && typeof source.profile === 'object'
      ? source.profile : {};
    const growth = source.growth && typeof source.growth === 'object'
      ? source.growth : {};
    return {
      profile: {
        colour: validAvatarValue(AVATAR_COLOURS, profile.colour, 'purple'),
        accessory: validAvatarValue(
          AVATAR_ACCESSORIES, profile.accessory, 'star'
        ),
        customised: Boolean(profile.customised),
      },
      growth: growthForXp(growth.lifetime_xp),
    };
  }

  function applyAvatarAppearance(profile) {
    if (!avatarRoot) return;
    const selected = profile && profile.customised
      ? AVATAR_COLOURS.find((option) => option.value === profile.colour)
      : null;
    avatarRoot.setAttribute(
      'data-avatar-colour', selected ? selected.index : avatarColour(activeLearnerName)
    );
    const accessoryValue = validAvatarValue(
      AVATAR_ACCESSORIES, profile && profile.accessory, 'star'
    );
    const accessory = AVATAR_ACCESSORIES.find(
      (option) => option.value === accessoryValue
    );
    avatarRoot.setAttribute('data-avatar-accessory', accessoryValue);
    avatarRoot.querySelectorAll('[data-avatar-accessory-symbol]').forEach((node) => {
      node.textContent = accessory ? accessory.symbol : '★';
    });
  }

  function renderAvatarGrowth(growth) {
    if (!avatarRoot) return;
    const safeGrowth = growthForXp(growth && growth.lifetime_xp);
    avatarRoot.setAttribute('data-growth-stage', String(safeGrowth.stage));
    const name = avatarRoot.querySelector('[data-avatar-growth-name]');
    const xp = avatarRoot.querySelector('[data-avatar-growth-xp]');
    const progress = avatarRoot.querySelector('[data-avatar-growth-progress]');
    const next = avatarRoot.querySelector('[data-avatar-growth-next]');
    if (name) name.textContent = safeGrowth.name;
    if (xp) xp.textContent = `${safeGrowth.lifetime_xp} XP`;
    if (progress) {
      progress.value = safeGrowth.progress_percent;
      progress.textContent = `${safeGrowth.progress_percent}%`;
    }
    if (next) {
      next.textContent = safeGrowth.next_stage
        ? `${safeGrowth.xp_to_next} XP until ${safeGrowth.next_stage.name}`
        : 'Your capybara is fully grown—legendary!';
    }
  }

  function updateAvatarChoiceButtons() {
    if (!avatarRoot || !avatarDraft) return;
    avatarRoot.querySelectorAll('[data-avatar-choice]').forEach((button) => {
      const group = button.getAttribute('data-avatar-choice-group');
      const selected = avatarDraft[group] === button.getAttribute('data-avatar-choice');
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      button.classList.toggle('is-selected', selected);
    });
  }

  function applyAvatarState(summary) {
    avatarState = normaliseAvatarState(summary);
    applyAvatarAppearance(avatarState.profile);
    renderAvatarGrowth(avatarState.growth);
    avatarDraft = {
      colour: avatarState.profile.colour,
      accessory: avatarState.profile.accessory,
    };
    updateAvatarChoiceButtons();
  }

  function createAvatarChoice(group, option) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `hm-kid-avatar-choice hm-kid-avatar-choice-${group}`;
    button.setAttribute('data-avatar-choice', option.value);
    button.setAttribute('data-avatar-choice-group', group);
    button.setAttribute('aria-pressed', 'false');
    button.title = option.label;
    appendTextElement(button, 'span', 'hm-kid-avatar-choice-symbol', option.symbol)
      .setAttribute('aria-hidden', 'true');
    appendTextElement(button, 'span', 'hm-kid-avatar-choice-label', option.label);
    button.addEventListener('click', () => {
      if (!avatarDraft || avatarSavePending) return;
      avatarDraft[group] = option.value;
      updateAvatarChoiceButtons();
      applyAvatarAppearance({
        colour: avatarDraft.colour,
        accessory: avatarDraft.accessory,
        customised: true,
      });
    });
    return button;
  }

  async function saveAvatarPreferences(trigger) {
    if (avatarSavePending || activeRole !== 'kid' || !activeStudentId || !avatarDraft) {
      return;
    }
    avatarSavePending = true;
    const status = avatarRoot.querySelector('[data-avatar-customise-status]');
    const originalText = trigger.textContent;
    trigger.disabled = true;
    trigger.textContent = 'Saving…';
    if (status) status.textContent = 'Saving your capybara style…';
    try {
      const response = await fetch('/api/rewards/avatar', {
        method: 'PUT',
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
        body: JSON.stringify({
          colour: avatarDraft.colour,
          accessory: avatarDraft.accessory,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success || !data.avatar) {
        throw new Error(data.detail || data.error || 'Avatar save failed.');
      }
      applyAvatarState(data.avatar);
      if (window.HomeworkMagicSession) window.HomeworkMagicSession.clear();
      if (status) status.textContent = data.message || 'Your capybara style is saved!';
    } catch (error) {
      console.error('Could not save avatar choices:', error);
      if (status) status.textContent = 'We could not save that style. Please try again.';
      if (avatarState) applyAvatarAppearance(avatarState.profile);
    } finally {
      avatarSavePending = false;
      trigger.disabled = false;
      trigger.textContent = originalText;
    }
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
    appendTextElement(
      face, 'span', 'hm-kid-avatar-star hm-kid-avatar-accessory', '★'
    ).setAttribute('data-avatar-accessory-symbol', '');
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
    appendTextElement(
      miniFace, 'span', 'hm-kid-avatar-star hm-kid-avatar-accessory', '★'
    ).setAttribute('data-avatar-accessory-symbol', '');
    welcome.appendChild(miniFace);
    const welcomeCopy = document.createElement('div');
    appendTextElement(welcomeCopy, 'strong', 'hm-kid-avatar-name', 'Hi, Learner!')
      .setAttribute('data-kid-avatar-name', '');
    appendTextElement(welcomeCopy, 'span', 'hm-kid-avatar-year', 'Your learning space')
      .setAttribute('data-kid-avatar-year', '');
    welcome.appendChild(welcomeCopy);
    menu.appendChild(welcome);

    const growth = document.createElement('section');
    growth.className = 'hm-kid-avatar-growth';
    growth.setAttribute('aria-label', 'Capybara growth');
    const growthHeading = document.createElement('div');
    appendTextElement(
      growthHeading, 'strong', 'hm-kid-avatar-growth-name', 'Tiny Capybara'
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
    growthProgress.setAttribute('aria-label', 'Progress to the next capybara stage');
    growth.appendChild(growthProgress);
    appendTextElement(
      growth, 'small', 'hm-kid-avatar-growth-next', '100 XP until Curious Cub'
    ).setAttribute('data-avatar-growth-next', '');
    menu.appendChild(growth);

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

    const customiseToggle = appendTextElement(
      menu, 'button', 'hm-kid-avatar-customise-toggle', '🎨 Customise my capybara'
    );
    customiseToggle.type = 'button';
    customiseToggle.setAttribute('aria-expanded', 'false');
    customiseToggle.setAttribute('aria-controls', 'kid-avatar-customiser');

    const customiser = document.createElement('section');
    customiser.id = 'kid-avatar-customiser';
    customiser.className = 'hm-kid-avatar-customiser';
    customiser.hidden = true;

    const colourChoices = document.createElement('fieldset');
    colourChoices.className = 'hm-kid-avatar-choice-group';
    appendTextElement(colourChoices, 'legend', '', 'Favourite colour');
    const colourGrid = document.createElement('div');
    colourGrid.className = 'hm-kid-avatar-choice-grid';
    AVATAR_COLOURS.forEach((option) => {
      colourGrid.appendChild(createAvatarChoice('colour', option));
    });
    colourChoices.appendChild(colourGrid);
    customiser.appendChild(colourChoices);

    const accessoryChoices = document.createElement('fieldset');
    accessoryChoices.className = 'hm-kid-avatar-choice-group';
    appendTextElement(accessoryChoices, 'legend', '', 'Accessory');
    const accessoryGrid = document.createElement('div');
    accessoryGrid.className = 'hm-kid-avatar-choice-grid';
    AVATAR_ACCESSORIES.forEach((option) => {
      accessoryGrid.appendChild(createAvatarChoice('accessory', option));
    });
    accessoryChoices.appendChild(accessoryGrid);
    customiser.appendChild(accessoryChoices);

    const saveAvatarButton = appendTextElement(
      customiser, 'button', 'hm-kid-avatar-save', 'Save my style'
    );
    saveAvatarButton.type = 'button';
    saveAvatarButton.addEventListener('click', () => {
      saveAvatarPreferences(saveAvatarButton);
    });
    const customiseStatus = appendTextElement(
      customiser, 'span', 'hm-kid-avatar-customise-status', ''
    );
    customiseStatus.setAttribute('data-avatar-customise-status', '');
    customiseStatus.setAttribute('role', 'status');
    customiseStatus.setAttribute('aria-live', 'polite');
    menu.appendChild(customiser);

    customiseToggle.addEventListener('click', () => {
      const opening = customiser.hidden;
      customiser.hidden = !opening;
      customiseToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      if (opening) {
        const profile = avatarState ? avatarState.profile : {
          colour: 'purple', accessory: 'star'
        };
        avatarDraft = {
          colour: profile.colour,
          accessory: profile.accessory,
        };
        customiseStatus.textContent = '';
        updateAvatarChoiceButtons();
      } else if (avatarState) {
        applyAvatarAppearance(avatarState.profile);
      }
    });

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
      activeStudentId = '';
      activeLearnerName = 'Learner';
      avatarState = null;
      avatarDraft = null;
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
    activeStudentId = String(student.id || '');
    activeLearnerName = fullName;
    const year = Number(student.year_group);
    const yearLabel = Number.isFinite(year) && year >= 1 && year <= 6
      ? `Year ${year} explorer` : 'Your learning space';
    const button = avatar.querySelector('[data-kid-avatar-button]');
    const name = avatar.querySelector('[data-kid-avatar-name]');
    const yearCopy = avatar.querySelector('[data-kid-avatar-year]');
    const status = avatar.querySelector('[data-kid-avatar-status]');

    avatar.hidden = false;
    if (avatarHost) avatarHost.classList.add('hm-kid-avatar-host');
    button.setAttribute('aria-label', `Open ${firstName}'s learning menu`);
    button.title = `${firstName}'s learning menu`;
    name.textContent = `Hi, ${firstName}!`;
    yearCopy.textContent = yearLabel;
    status.textContent = '';
    applyAvatarState(context.avatar || null);
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

  window.addEventListener('homeworkmagic:xp-updated', (event) => {
    if (activeRole !== 'kid' || !avatarRoot) return;
    const detail = event && event.detail && typeof event.detail === 'object'
      ? event.detail : {};
    if (!Number.isFinite(Number(detail.lifetime_xp))) return;
    applyAvatarState({
      profile: avatarState ? avatarState.profile : null,
      growth: {lifetime_xp: Number(detail.lifetime_xp)},
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
