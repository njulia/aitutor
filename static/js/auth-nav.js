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

  const AVATAR_DEFAULTS = {
    character: 'girl',
    clothes: 'pink_dress',
    shoes: 'trainers',
    skin_tone: 'warm',
    hair_colour: 'brown',
    hair_length: 'long',
    hair_style: 'ponytail',
    eye_shape: 'round',
    eye_colour: 'green',
    nose: 'button',
    mouth: 'smile',
    eyebrows: 'arched',
  };

  const CHARACTER_PRESETS = {
    girl: {
      clothes: 'pink_dress',
      shoes: 'trainers',
      hair_colour: 'brown',
      hair_length: 'long',
      hair_style: 'ponytail',
      eye_shape: 'round',
      eye_colour: 'green',
      nose: 'button',
      mouth: 'smile',
      eyebrows: 'arched',
    },
    boy: {
      clothes: 'blue_tshirt',
      shoes: 'boots',
      hair_colour: 'black',
      hair_length: 'short',
      hair_style: 'spiky',
      eye_shape: 'almond',
      eye_colour: 'blue',
      nose: 'small',
      mouth: 'grin',
      eyebrows: 'straight',
    },
  };

  const AVATAR_OPTIONS = {
    character: [
      {value: 'girl', label: 'Girl character', symbol: '👧'},
      {value: 'boy', label: 'Boy character', symbol: '👦'},
    ],
    clothes: [
      {value: 'purple_hoodie', label: 'Purple', symbol: '🧥'},
      {value: 'blue_tshirt', label: 'Blue', symbol: '👕'},
      {value: 'green_jumper', label: 'Green', symbol: '🟢'},
      {value: 'pink_dress', label: 'Pink', symbol: '👗'},
    ],
    shoes: [
      {value: 'trainers', label: 'Trainers', symbol: '👟'},
      {value: 'boots', label: 'Boots', symbol: '🥾'},
      {value: 'school_shoes', label: 'Flats', symbol: '👞'},
    ],
    skin_tone: [
      {value: 'light', label: 'Light skin tone', symbol: '●', swatch: '#f2c9aa'},
      {value: 'warm', label: 'Warm skin tone', symbol: '●', swatch: '#d99a70'},
      {value: 'tan', label: 'Tan skin tone', symbol: '●', swatch: '#ae704d'},
      {value: 'deep', label: 'Deep skin tone', symbol: '●', swatch: '#70462f'},
    ],
    hair_colour: [
      {value: 'black', label: 'Black hair', symbol: '●', swatch: '#28242a'},
      {value: 'brown', label: 'Brown hair', symbol: '●', swatch: '#6f442d'},
      {value: 'blonde', label: 'Blonde hair', symbol: '●', swatch: '#e3bd62'},
      {value: 'red', label: 'Red hair', symbol: '●', swatch: '#ad4e32'},
    ],
    hair_length: [
      {value: 'short', label: 'Short'},
      {value: 'medium', label: 'Medium'},
      {value: 'long', label: 'Long'},
    ],
    hair_style: [
      {value: 'straight', label: 'Straight'},
      {value: 'curly', label: 'Curly'},
      {value: 'ponytail', label: 'Ponytail'},
      {value: 'spiky', label: 'Spiky'},
    ],
    eye_shape: [
      {value: 'round', label: 'Round'},
      {value: 'almond', label: 'Almond'},
      {value: 'smiling', label: 'Smiling'},
    ],
    eye_colour: [
      {value: 'brown', label: 'Brown eyes', symbol: '●', swatch: '#6a432e'},
      {value: 'blue', label: 'Blue eyes', symbol: '●', swatch: '#3f85bc'},
      {value: 'green', label: 'Green eyes', symbol: '●', swatch: '#4d8a62'},
      {value: 'grey', label: 'Grey eyes', symbol: '●', swatch: '#7d8490'},
    ],
    nose: [
      {value: 'button', label: 'Button nose'},
      {value: 'small', label: 'Small nose'},
      {value: 'round', label: 'Round nose'},
    ],
    mouth: [
      {value: 'smile', label: 'Smile'},
      {value: 'grin', label: 'Toothy grin'},
      {value: 'open', label: 'Open smile'},
      {value: 'calm', label: 'Calm'},
    ],
    eyebrows: [
      {value: 'soft', label: 'Soft eyebrows'},
      {value: 'straight', label: 'Straight eyebrows'},
      {value: 'arched', label: 'Arched eyebrows'},
    ],
  };

  const AVATAR_ATTRIBUTES = {
    character: 'data-character',
    clothes: 'data-clothes',
    shoes: 'data-shoes',
    skin_tone: 'data-skin-tone',
    hair_colour: 'data-hair-colour',
    hair_length: 'data-hair-length',
    hair_style: 'data-hair-style',
    eye_shape: 'data-eye-shape',
    eye_colour: 'data-eye-colour',
    nose: 'data-nose',
    mouth: 'data-mouth',
    eyebrows: 'data-eyebrows',
  };

  const AVATAR_GROWTH_STAGES = [
    {stage: 1, threshold: 0, name: 'Little Learner'},
    {stage: 2, threshold: 100, name: 'Curious Explorer'},
    {stage: 3, threshold: 500, name: 'Growing Star'},
    {stage: 4, threshold: 1000, name: 'Clever Champion'},
    {stage: 5, threshold: 2000, name: 'Super Scholar'},
    {stage: 6, threshold: 5000, name: 'Learning Legend'},
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

  function appendFigurePart(parent, className) {
    return appendTextElement(parent, 'span', className, '');
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

  function validAvatarValue(group, value) {
    const options = AVATAR_OPTIONS[group] || [];
    const selected = options.find((option) => option.value === value);
    return selected ? selected.value : AVATAR_DEFAULTS[group];
  }

  function avatarProfileCopy(profile) {
    const safe = {};
    Object.keys(AVATAR_DEFAULTS).forEach((group) => {
      safe[group] = validAvatarValue(group, profile && profile[group]);
    });
    safe.customised = Boolean(profile && profile.customised);
    return safe;
  }

  function normaliseAvatarState(summary) {
    const source = summary && typeof summary === 'object' ? summary : {};
    const profile = source.profile && typeof source.profile === 'object'
      ? source.profile : {};
    const growth = source.growth && typeof source.growth === 'object'
      ? source.growth : {};
    return {
      profile: avatarProfileCopy(profile),
      growth: growthForXp(growth.lifetime_xp),
    };
  }

  function applyAvatarAppearance(profile) {
    if (!avatarRoot) return;
    const safeProfile = avatarProfileCopy(profile);
    avatarRoot.querySelectorAll('[data-character-figure]').forEach((figure) => {
      Object.keys(AVATAR_ATTRIBUTES).forEach((group) => {
        figure.setAttribute(AVATAR_ATTRIBUTES[group], safeProfile[group]);
      });
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
        : 'Your character is fully grown—a learning legend!';
    }
  }

  function updateAvatarControls() {
    if (!avatarRoot || !avatarDraft) return;
    avatarRoot.querySelectorAll('[data-avatar-choice]').forEach((button) => {
      const group = button.getAttribute('data-avatar-choice-group');
      const selected = avatarDraft[group] === button.getAttribute('data-avatar-choice');
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      button.classList.toggle('is-selected', selected);
    });
    avatarRoot.querySelectorAll('[data-avatar-select]').forEach((select) => {
      const group = select.getAttribute('data-avatar-select');
      select.value = avatarDraft[group];
    });
  }

  function applyAvatarState(summary) {
    avatarState = normaliseAvatarState(summary);
    applyAvatarAppearance(avatarState.profile);
    renderAvatarGrowth(avatarState.growth);
    avatarDraft = avatarProfileCopy(avatarState.profile);
    updateAvatarControls();
  }

  function createCharacterFigure(extraClass) {
    const figure = document.createElement('span');
    figure.className = `hm-character-avatar ${extraClass || ''}`.trim();
    figure.setAttribute('data-character-figure', '');
    figure.setAttribute('aria-hidden', 'true');

    appendFigurePart(figure, 'hm-character-hair-back');
    appendFigurePart(figure, 'hm-character-ear hm-character-ear-left');
    appendFigurePart(figure, 'hm-character-ear hm-character-ear-right');
    appendFigurePart(figure, 'hm-character-neck');
    appendFigurePart(figure, 'hm-character-arm hm-character-arm-left');
    appendFigurePart(figure, 'hm-character-arm hm-character-arm-right');
    appendFigurePart(figure, 'hm-character-leg hm-character-leg-left');
    appendFigurePart(figure, 'hm-character-leg hm-character-leg-right');
    appendFigurePart(figure, 'hm-character-shoe hm-character-shoe-left');
    appendFigurePart(figure, 'hm-character-shoe hm-character-shoe-right');
    const body = appendFigurePart(figure, 'hm-character-body');
    appendFigurePart(body, 'hm-character-clothes-detail');

    const head = appendFigurePart(figure, 'hm-character-head');
    appendFigurePart(head, 'hm-character-hair-front');
    appendFigurePart(head, 'hm-character-eyebrow hm-character-eyebrow-left');
    appendFigurePart(head, 'hm-character-eyebrow hm-character-eyebrow-right');
    const leftEye = appendFigurePart(head, 'hm-character-eye hm-character-eye-left');
    appendFigurePart(leftEye, 'hm-character-pupil');
    const rightEye = appendFigurePart(head, 'hm-character-eye hm-character-eye-right');
    appendFigurePart(rightEye, 'hm-character-pupil');
    appendFigurePart(head, 'hm-character-cheek hm-character-cheek-left');
    appendFigurePart(head, 'hm-character-cheek hm-character-cheek-right');
    appendFigurePart(head, 'hm-character-nose');
    appendFigurePart(head, 'hm-character-mouth');
    appendFigurePart(head, 'hm-character-face-detail');
    return figure;
  }

  function previewAvatarDraft() {
    if (!avatarDraft) return;
    applyAvatarAppearance(Object.assign({}, avatarDraft, {customised: true}));
  }

  function createAvatarChoice(group, option) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `hm-kid-avatar-choice hm-kid-avatar-choice-${group}`;
    button.setAttribute('data-avatar-choice', option.value);
    button.setAttribute('data-avatar-choice-group', group);
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-label', option.label);
    button.title = option.label;
    if (option.swatch) button.style.setProperty('--hm-choice-colour', option.swatch);
    appendTextElement(button, 'span', 'hm-kid-avatar-choice-symbol', option.symbol || '◆')
      .setAttribute('aria-hidden', 'true');
    appendTextElement(button, 'span', 'hm-kid-avatar-choice-label', option.label);
    button.addEventListener('click', () => {
      if (!avatarDraft || avatarSavePending) return;
      if (group === 'character' && CHARACTER_PRESETS[option.value]) {
        const skinTone = avatarDraft.skin_tone;
        avatarDraft = Object.assign(
          {}, avatarDraft, CHARACTER_PRESETS[option.value], {
            character: option.value,
            skin_tone: skinTone,
          }
        );
      } else {
        avatarDraft[group] = option.value;
      }
      updateAvatarControls();
      previewAvatarDraft();
    });
    return button;
  }

  function createChoiceFieldset(label, group, extraClass) {
    const fieldset = document.createElement('fieldset');
    fieldset.className = `hm-kid-avatar-choice-group ${extraClass || ''}`.trim();
    appendTextElement(fieldset, 'legend', '', label);
    const grid = document.createElement('div');
    grid.className = 'hm-kid-avatar-choice-grid';
    (AVATAR_OPTIONS[group] || []).forEach((option) => {
      grid.appendChild(createAvatarChoice(group, option));
    });
    fieldset.appendChild(grid);
    return fieldset;
  }

  function createAvatarSelect(group, label) {
    const wrapper = document.createElement('label');
    wrapper.className = 'hm-kid-avatar-select-field';
    appendTextElement(wrapper, 'span', '', label);
    const select = document.createElement('select');
    select.setAttribute('data-avatar-select', group);
    select.setAttribute('aria-label', label);
    (AVATAR_OPTIONS[group] || []).forEach((option) => {
      const node = document.createElement('option');
      node.value = option.value;
      node.textContent = option.label;
      select.appendChild(node);
    });
    select.addEventListener('change', () => {
      if (!avatarDraft || avatarSavePending) return;
      avatarDraft[group] = validAvatarValue(group, select.value);
      updateAvatarControls();
      previewAvatarDraft();
    });
    wrapper.appendChild(select);
    return wrapper;
  }

  function createCustomiserSection(label, open) {
    const section = document.createElement('details');
    section.className = 'hm-kid-avatar-editor-section';
    section.open = Boolean(open);
    appendTextElement(section, 'summary', '', label);
    return section;
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
    if (status) status.textContent = 'Saving your character…';
    try {
      const requestProfile = {};
      Object.keys(AVATAR_DEFAULTS).forEach((group) => {
        requestProfile[group] = avatarDraft[group];
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
      applyAvatarState(data.avatar);
      if (window.HomeworkMagicSession) window.HomeworkMagicSession.clear();
      if (status) status.textContent = data.message || 'Your character style is saved!';
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
    button.appendChild(createCharacterFigure('hm-character-avatar-button-figure'));
    avatarRoot.appendChild(button);

    const menu = document.createElement('section');
    menu.id = 'kid-avatar-menu';
    menu.className = 'hm-kid-avatar-menu';
    menu.setAttribute('data-kid-avatar-menu', '');
    menu.setAttribute('aria-labelledby', 'kid-avatar-button');
    menu.hidden = true;

    const welcome = document.createElement('div');
    welcome.className = 'hm-kid-avatar-welcome';
    welcome.appendChild(createCharacterFigure('hm-character-avatar-mini'));
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
    growthProgress.setAttribute('aria-label', 'Progress to the next character stage');
    growth.appendChild(growthProgress);
    appendTextElement(
      growth, 'small', 'hm-kid-avatar-growth-next', '100 XP until Curious Explorer'
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
      menu, 'button', 'hm-kid-avatar-customise-toggle', '🎨 Customise my character'
    );
    customiseToggle.type = 'button';
    customiseToggle.setAttribute('aria-expanded', 'false');
    customiseToggle.setAttribute('aria-controls', 'kid-avatar-customiser');

    const customiser = document.createElement('section');
    customiser.id = 'kid-avatar-customiser';
    customiser.className = 'hm-kid-avatar-customiser';
    customiser.hidden = true;
    const preview = document.createElement('div');
    preview.className = 'hm-kid-avatar-editor-preview';
    preview.setAttribute('aria-label', 'Character preview');
    preview.appendChild(createCharacterFigure('hm-character-avatar-preview'));
    customiser.appendChild(preview);
    customiser.appendChild(createChoiceFieldset('Choose a character', 'character'));

    const hairSection = createCustomiserSection('💇 Hair', true);
    hairSection.appendChild(createChoiceFieldset('Hair colour', 'hair_colour', 'hm-avatar-swatch-group'));
    const hairSelects = document.createElement('div');
    hairSelects.className = 'hm-kid-avatar-select-grid';
    hairSelects.appendChild(createAvatarSelect('hair_length', 'Hair length'));
    hairSelects.appendChild(createAvatarSelect('hair_style', 'Hair style'));
    hairSection.appendChild(hairSelects);
    customiser.appendChild(hairSection);

    const faceSection = createCustomiserSection('🙂 Face', false);
    faceSection.appendChild(createChoiceFieldset('Skin tone', 'skin_tone', 'hm-avatar-swatch-group'));
    faceSection.appendChild(createChoiceFieldset('Eye colour', 'eye_colour', 'hm-avatar-swatch-group'));
    const faceSelects = document.createElement('div');
    faceSelects.className = 'hm-kid-avatar-select-grid';
    faceSelects.appendChild(createAvatarSelect('eye_shape', 'Eye shape'));
    faceSelects.appendChild(createAvatarSelect('eyebrows', 'Eyebrows'));
    faceSelects.appendChild(createAvatarSelect('nose', 'Nose'));
    faceSelects.appendChild(createAvatarSelect('mouth', 'Mouth'));
    faceSection.appendChild(faceSelects);
    customiser.appendChild(faceSection);

    const outfitSection = createCustomiserSection('👕 Clothes & shoes', false);
    outfitSection.appendChild(createChoiceFieldset('Clothes', 'clothes'));
    outfitSection.appendChild(createChoiceFieldset('Shoes', 'shoes'));
    customiser.appendChild(outfitSection);

    const saveAvatarButton = appendTextElement(
      customiser, 'button', 'hm-kid-avatar-save', 'Save my character'
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
        avatarDraft = avatarProfileCopy(
          avatarState ? avatarState.profile : AVATAR_DEFAULTS
        );
        customiseStatus.textContent = '';
        updateAvatarControls();
        previewAvatarDraft();
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
