'use strict';

(function initCharacterCustomiser() {
  const Avatar = window.HomeworkMagicAvatar;
  const previewFigure = document.querySelector('.hm-character-avatar-preview');
  const playground = document.getElementById('character-playground');
  const stageButton = document.getElementById('character-stage');
  const message = document.getElementById('character-message');
  let currentProfile = null;
  let draftProfile = null;
  let learner = {age: 7, year_group: 2};
  let growth = {lifetime_xp: 0, name: 'Little Learner'};
  let savePending = false;

  if (!Avatar || !previewFigure) {
    const status = document.getElementById('page-status');
    if (status) status.textContent = 'Your character could not start. Please refresh the page.';
    return;
  }

  Avatar.hydrateFigure(previewFigure);
  Avatar.enableTilt(playground, previewFigure);

  function applyAvatarAppearance(profile) {
    return Avatar.applyAll(document, profile, {
      age: learner.age,
      year_group: learner.year_group,
      lifetime_xp: growth.lifetime_xp,
    });
  }

  function renderLearningCertificates(certificates, lifetimeXp) {
    const grid = document.getElementById('character-certificate-grid');
    if (!grid) return;
    grid.replaceChildren();
    const seenTitles = new Set();
    const all = Array.isArray(certificates) ? certificates : [];
    all.forEach((certificate) => {
      const titleCopy = String(certificate && certificate.title || '').trim();
      const titleKey = titleCopy.toLocaleLowerCase();
      if (!titleCopy || seenTitles.has(titleKey)) return;
      seenTitles.add(titleKey);

      const card = document.createElement('article');
      card.className = `hm-character-badge ${certificate.unlocked ? 'earned' : 'locked'}`;
      card.title = String(certificate.message || '');
      const icon = document.createElement('span');
      icon.textContent = certificate.unlocked ? (certificate.icon || '🏅') : '🔒';
      icon.setAttribute('aria-hidden', 'true');
      const title = document.createElement('strong');
      title.textContent = titleCopy;
      const progress = document.createElement('small');
      const threshold = Math.max(0, Number(certificate.threshold) || 0);
      const safeXp = Math.max(0, Number(lifetimeXp) || 0);
      progress.textContent = certificate.unlocked
        ? 'Certificate unlocked!'
        : `${Math.min(safeXp, threshold)}/${threshold} XP`;
      card.append(icon, title, progress);
      grid.append(card);
    });
  }

  function renderLearningBadges(badges) {
    const grid = document.getElementById('character-badge-grid');
    if (!grid) return;
    grid.replaceChildren();
    const all = Array.isArray(badges && badges.all) ? badges.all : [];
    all.forEach((badge) => {
      const card = document.createElement('article');
      card.className = `hm-character-badge ${badge.earned ? 'earned' : 'locked'}`;
      card.title = String(badge.description || '');
      const icon = document.createElement('span');
      icon.textContent = badge.earned ? (badge.icon || '🏅') : '🔒';
      icon.setAttribute('aria-hidden', 'true');
      const title = document.createElement('strong');
      title.textContent = String(badge.title || 'Learning badge');
      const progress = document.createElement('small');
      const target = Math.max(1, Number(badge.target) || 1);
      const current = Math.max(0, Math.min(Number(badge.progress) || 0, target));
      progress.textContent = badge.earned ? 'Badge earned!' : `${current}/${target}`;
      card.append(icon, title, progress);
      grid.append(card);
    });
  }

  function updateCharacterDetails() {
    const age = Avatar.ageDetails(learner.age, learner.year_group);
    const safeGrowth = Avatar.growthForXp(growth.lifetime_xp);
    const name = document.getElementById('character-name');
    const ageBadge = document.getElementById('character-age-badge');
    const growthNote = document.getElementById('character-growth-note');
    if (name) name.textContent = safeGrowth.name;
    if (ageBadge) ageBadge.textContent = `Age ${age.age} • ${age.label}`;
    if (growthNote) {
      growthNote.textContent = safeGrowth.next_stage
        ? `${safeGrowth.xp_to_next} XP until the next glow.`
        : 'Your learning glow is complete!';
    }
  }

  function updateAllControls() {
    if (!draftProfile) return;
    document.querySelectorAll('[data-avatar-choice]').forEach((button) => {
      const group = button.getAttribute('data-avatar-choice-group');
      const selected = draftProfile[group] === button.getAttribute('data-avatar-choice');
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      button.classList.toggle('is-selected', selected);
    });
    document.querySelectorAll('[data-avatar-select]').forEach((select) => {
      const group = select.getAttribute('data-avatar-select');
      select.value = draftProfile[group];
    });
  }

  function previewDraft() {
    updateAllControls();
    applyAvatarAppearance(Object.assign({}, draftProfile, {customised: true}));
  }

  function buildChoiceButton(group, option) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `hm-kid-avatar-choice hm-kid-avatar-choice-${group}`;
    button.setAttribute('data-avatar-choice', option.value);
    button.setAttribute('data-avatar-choice-group', group);
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-label', option.label);
    button.title = option.label;
    if (option.swatch) button.style.setProperty('--hm-choice-colour', option.swatch);

    const symbol = document.createElement('span');
    symbol.className = 'hm-kid-avatar-choice-symbol';
    symbol.setAttribute('aria-hidden', 'true');
    symbol.textContent = option.symbol || '◆';
    button.appendChild(symbol);

    const label = document.createElement('span');
    label.className = 'hm-kid-avatar-choice-label';
    label.textContent = option.label;
    button.appendChild(label);

    button.addEventListener('click', () => {
      if (!draftProfile || savePending) return;
      if (group === 'character' && Avatar.CHARACTER_PRESETS[option.value]) {
        const skinTone = draftProfile.skin_tone;
        draftProfile = Object.assign(
          {}, draftProfile, Avatar.CHARACTER_PRESETS[option.value],
          {character: option.value, skin_tone: skinTone}
        );
      } else {
        draftProfile[group] = option.value;
      }
      previewDraft();
      Avatar.play(previewFigure, 'celebrate');
    });
    return button;
  }

  function populateChoiceGrid(container, group) {
    (Avatar.OPTIONS[group] || []).forEach((option) => {
      container.appendChild(buildChoiceButton(group, option));
    });
  }

  function buildSelect(select, group) {
    (Avatar.OPTIONS[group] || []).forEach((option) => {
      const node = document.createElement('option');
      node.value = option.value;
      node.textContent = option.label;
      select.appendChild(node);
    });
    select.addEventListener('change', () => {
      if (!draftProfile || savePending) return;
      draftProfile[group] = Avatar.optionValue(group, select.value);
      previewDraft();
    });
  }

  function initUI() {
    document.querySelectorAll('[data-choices]').forEach((grid) => {
      populateChoiceGrid(grid, grid.getAttribute('data-choices'));
    });
    document.querySelectorAll('[data-avatar-select]').forEach((select) => {
      buildSelect(select, select.getAttribute('data-avatar-select'));
    });
  }

  function showStatus(copy, isError) {
    const status = document.getElementById('page-status');
    if (status) {
      status.textContent = copy;
      status.style.color = isError ? 'var(--hm-danger)' : '';
    }
  }

  function playCharacter(action) {
    const safeAction = ['dance', 'celebrate'].includes(action) ? action : 'celebrate';
    const messages = {
      dance: 'That deserves a happy dance! 🎵',
      celebrate: 'Hooray for your effort! ✨',
    };
    Avatar.play(previewFigure, safeAction);
    if (message) message.textContent = messages[safeAction];
  }

  function setBuddySearchStatus(copy, isError) {
    const status = document.getElementById('study-buddy-search-status');
    if (!status) return;
    status.textContent = copy;
    status.dataset.state = isError ? 'error' : 'success';
  }

  function clearBuddySearchResults() {
    const results = document.getElementById('study-buddy-search-results');
    if (results) results.replaceChildren();
    return results;
  }

  async function requestStudyBuddy(studentId, button) {
    if (!studentId || !button) return;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Sending…';
    try {
      const response = await fetch('/api/study-buddies/request', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
        body: JSON.stringify({target_student_id: studentId}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'We could not send that request.');
      if (data.status === 'active') {
        setBuddySearchStatus('You are Study Buddies now! 🎉', false);
        button.textContent = 'Study Buddies!';
      } else {
        setBuddySearchStatus('Buddy request sent! Both families need to say yes.', false);
        button.textContent = 'Request sent';
      }
    } catch (error) {
      console.error('Could not send study buddy request:', error);
      setBuddySearchStatus(error.message || 'We could not send that request. Please try again.', true);
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  function showBuddySearchResults(students) {
    const results = clearBuddySearchResults();
    if (!results) return;
    if (!students.length) {
      setBuddySearchStatus('No buddy found. Check the Buddy Code with a grown-up and try again.', false);
      return;
    }
    setBuddySearchStatus('Choose your friend, then send a buddy request.', false);
    students.forEach((student) => {
      const card = document.createElement('article');
      card.className = 'hm-char-study-buddy-result';

      const details = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = student.nickname || 'Learner';
      const year = document.createElement('span');
      year.textContent = student.year_group ? `Year ${student.year_group}` : 'Learner';
      details.append(name, year);

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'hm-char-customise-btn primary hm-char-study-buddy-request';
      button.textContent = 'Send buddy request';
      button.addEventListener('click', () => requestStudyBuddy(student.student_id, button));
      card.append(details, button);
      results.append(card);
    });
  }

  async function searchStudyBuddies(event) {
    event.preventDefault();
    const input = document.getElementById('study-buddy-search');
    const button = document.getElementById('study-buddy-search-button');
    const query = input ? input.value.trim().toUpperCase() : '';
    if (!/^[A-Z0-9]{1,10}\d{4}$/.test(query)) {
      clearBuddySearchResults();
      setBuddySearchStatus('Please type the Buddy Code like ALEX4821.', true);
      if (input) input.focus();
      return;
    }
    if (button) {
      button.disabled = true;
      button.textContent = 'Searching…';
    }
    clearBuddySearchResults();
    setBuddySearchStatus('Looking for your buddy…', false);
    try {
      const response = await fetch('/api/study-buddies/search', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
        body: JSON.stringify({query}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'We could not search for a buddy.');
      showBuddySearchResults(Array.isArray(data.students) ? data.students : []);
    } catch (error) {
      console.error('Study buddy search failed:', error);
      setBuddySearchStatus(error.message || 'We could not search for a buddy. Please try again.', true);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = 'Find my friend';
      }
    }
  }

  async function loadAvatar() {
    showStatus('Loading your character…');
    try {
      const response = await fetch('/api/rewards/avatar', {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {'Accept': 'application/json'},
      });
      if (!response.ok) throw new Error('Could not load avatar.');
      const data = await response.json();
      const avatar = data && data.avatar ? data.avatar : {};
      currentProfile = Avatar.profileCopy(avatar.profile);
      draftProfile = Avatar.profileCopy(avatar.profile);
      learner = data && data.learner ? data.learner : learner;
      growth = avatar.growth || growth;
      renderLearningCertificates(avatar.certificates, growth.lifetime_xp);
      renderLearningBadges(avatar.badges);
      applyAvatarAppearance(draftProfile);
      updateAllControls();
      updateCharacterDetails();

      document.getElementById('page-status').hidden = true;
      document.getElementById('customiser-content').hidden = false;
      window.setTimeout(() => playCharacter('celebrate'), 260);
    } catch (error) {
      console.error('Avatar load failed:', error);
      document.getElementById('page-status').hidden = true;
      document.getElementById('login-needed').hidden = false;
    }
  }

  async function saveAvatar() {
    if (savePending || !draftProfile) return;
    savePending = true;
    const button = document.getElementById('save-button');
    const status = document.getElementById('save-status');
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Saving…';
    if (status) status.textContent = 'Saving your character…';

    try {
      const requestProfile = {};
      Object.keys(Avatar.DEFAULTS).forEach((group) => {
        requestProfile[group] = draftProfile[group];
      });
      const response = await fetch('/api/rewards/avatar', {
        method: 'PUT',
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
        body: JSON.stringify(requestProfile),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success || !data.avatar) {
        throw new Error(data.detail || data.error || 'Character save failed.');
      }
      currentProfile = Avatar.profileCopy(data.avatar.profile);
      draftProfile = Avatar.profileCopy(currentProfile);
      learner = data.learner || learner;
      growth = data.avatar.growth || growth;
      applyAvatarAppearance(currentProfile);
      updateAllControls();
      updateCharacterDetails();
      if (window.HomeworkMagicSession) window.HomeworkMagicSession.clear();
      window.dispatchEvent(new CustomEvent('homeworkmagic:avatar-updated'));
      if (status) status.textContent = data.message || 'Your character style is saved!';
      playCharacter('celebrate');
    } catch (error) {
      console.error('Could not save avatar:', error);
      if (status) status.textContent = 'We could not save that style. Please try again.';
      if (currentProfile) {
        draftProfile = Avatar.profileCopy(currentProfile);
        applyAvatarAppearance(currentProfile);
        updateAllControls();
      }
    } finally {
      savePending = false;
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  initUI();
  loadAvatar();

  document.getElementById('save-button').addEventListener('click', saveAvatar);
  stageButton.addEventListener('click', () => playCharacter('celebrate'));
  document.querySelectorAll('[data-character-action]').forEach((button) => {
    button.addEventListener('click', () => {
      playCharacter(button.getAttribute('data-character-action'));
    });
  });
  const studyBuddySearchForm = document.getElementById('study-buddy-search-form');
  if (studyBuddySearchForm) studyBuddySearchForm.addEventListener('submit', searchStudyBuddies);
})();
