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
        ? `Your age changes your character’s size. ${safeGrowth.xp_to_next} XP until the next glow.`
        : 'Your age changes your character’s size. Your learning glow is complete!';
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
})();
