'use strict';

(function initialiseHomeworkMagicAvatarPet(global) {
  if (global.HomeworkMagicAvatarPet) return;

  const ACTION_ANIMATIONS = {
    cuddle: 'celebrate',
    fetch: 'dance',
    dance: 'dance',
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function clamp(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
  }

  function clearNode(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function makeBar(label, value, icon) {
    const row = el('div', 'hm-avatar-pet-stat');
    const top = el('div', 'hm-avatar-pet-stat-top');
    top.append(el('span', '', `${icon} ${label}`), el('strong', '', `${clamp(value)}%`));
    const track = el('div', 'hm-avatar-pet-track');
    const fill = el('span', 'hm-avatar-pet-fill');
    fill.style.width = `${clamp(value)}%`;
    track.appendChild(fill);
    row.append(top, track);
    return row;
  }

  function mount(root, studentId, firstName, Avatar) {
    if (!root || !studentId) return null;
    let card = root.querySelector('[data-avatar-pet]');
    if (card) {
      card._avatarPetStudentId = studentId;
      card._avatarPetFirstName = firstName || 'Your character';
      card._avatarPetAvatar = Avatar;
      return card;
    }

    card = el('section', 'hm-avatar-pet', '');
    card.setAttribute('data-avatar-pet', '');
    card.setAttribute('aria-label', 'Play with your learning character');
    card._avatarPetStudentId = studentId;
    card._avatarPetFirstName = firstName || 'Your character';
    card._avatarPetAvatar = Avatar;

    const heading = el('div', 'hm-avatar-pet-heading');
    const title = el('div', 'hm-avatar-pet-title');
    title.append(el('span', 'hm-avatar-pet-icon', '🐾'), el('strong', '', 'Character playtime'));
    const badge = el('span', 'hm-avatar-pet-badge', 'LOCKED');
    badge.setAttribute('data-pet-badge', '');
    heading.append(title, badge);
    card.appendChild(heading);

    const speech = el('div', 'hm-avatar-pet-speech', 'Finish today\'s goal and I\'ll be ready to play!');
    speech.setAttribute('data-pet-speech', '');
    speech.setAttribute('role', 'status');
    speech.setAttribute('aria-live', 'polite');
    card.appendChild(speech);

    const stats = el('div', 'hm-avatar-pet-stats');
    stats.setAttribute('data-pet-stats', '');
    card.appendChild(stats);

    const actions = el('div', 'hm-avatar-pet-actions');
    actions.setAttribute('data-pet-actions', '');
    card.appendChild(actions);

    const footer = el('small', 'hm-avatar-pet-footer', 'Playtime never costs XP or Gift Points.');
    card.appendChild(footer);

    const reactionStatus = root.querySelector('[data-kid-avatar-reaction-status]');
    if (reactionStatus && reactionStatus.parentNode === root.querySelector('[data-kid-avatar-menu]')) {
      reactionStatus.parentNode.insertBefore(card, reactionStatus);
    } else {
      root.appendChild(card);
    }

    card._refresh = () => refresh(card);
    return card;
  }

  async function fetchPet(card) {
    const id = encodeURIComponent(card._avatarPetStudentId);
    const response = await fetch(`/api/rewards/avatar/pet?student_id=${id}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {'Accept': 'application/json'},
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'We could not load playtime.');
    return data.pet || {};
  }

  function render(card, pet) {
    const unlocked = Boolean(pet.unlocked);
    const badge = card.querySelector('[data-pet-badge]');
    const speech = card.querySelector('[data-pet-speech]');
    const stats = card.querySelector('[data-pet-stats]');
    const actions = card.querySelector('[data-pet-actions]');
    badge.textContent = unlocked ? 'READY!' : 'LOCKED';
    badge.classList.toggle('ready', unlocked);
    speech.textContent = unlocked
      ? `${card._avatarPetFirstName} is ready! Pick a playtime activity.`
      : `Finish ${Math.max(0, Number(pet.daily_goal || 1) - Number(pet.checked_today || 0))} more ${Number(pet.daily_goal || 1) - Number(pet.checked_today || 0) === 1 ? 'activity' : 'activities'} to unlock playtime.`;
    clearNode(stats);
    stats.append(
      makeBar('Friendship', pet.friendship, '💖'),
      makeBar('Mood', pet.mood, '😊'),
      el('div', 'hm-avatar-pet-streak', `🔥 ${Number(pet.play_streak || 0)} day play streak`),
    );
    clearNode(actions);
    (pet.actions || []).forEach((item) => {
      const button = el('button', 'hm-avatar-pet-action', `${item.icon} ${item.label}`);
      button.type = 'button';
      button.disabled = !unlocked;
      button.setAttribute('data-pet-action', item.code);
      actions.appendChild(button);
    });
    card.dataset.unlocked = unlocked ? 'true' : 'false';
  }

  async function doAction(card, action) {
    const button = Array.from(card.querySelectorAll('[data-pet-action]')).find((item) => item.getAttribute('data-pet-action') === action);
    if (!button || button.disabled) return;
    button.disabled = true;
    const speech = card.querySelector('[data-pet-speech]');
    try {
      const response = await fetch('/api/rewards/avatar/pet/action', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify({student_id: card._avatarPetStudentId, action}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Playtime is not ready yet.');
      const Avatar = card._avatarPetAvatar;
      if (Avatar) Avatar.playAll(card, ACTION_ANIMATIONS[action] || 'celebrate');
      const messages = {
        cuddle: `${card._avatarPetFirstName} gives you a giant cuddle! 💖`,
        fetch: `${card._avatarPetFirstName} zooms off for a fun game! 🎾`,
        dance: `${card._avatarPetFirstName} does a super dance! 🎵`,
      };
      speech.textContent = messages[action] || data.message || 'That was fun!';
      render(card, data.pet || {});
    } catch (error) {
      speech.textContent = error.message || 'Playtime is not ready yet.';
    } finally {
      card.querySelectorAll('[data-pet-action]').forEach((item) => {
        item.disabled = card.dataset.unlocked !== 'true';
      });
    }
  }

  async function refresh(card) {
    if (!card) return;
    try {
      render(card, await fetchPet(card));
    } catch (error) {
      const speech = card.querySelector('[data-pet-speech]');
      if (speech) speech.textContent = 'I\'ll be ready when your learning space is connected.';
    }
  }

  function attach(root, studentId, firstName, Avatar) {
    const card = mount(root, studentId, firstName, Avatar);
    if (!card) return null;
    if (!card._petActionsBound) {
      const actionHost = card.querySelector('[data-pet-actions]');
      if (actionHost) {
        actionHost.addEventListener('click', (event) => {
          const button = event.target.closest('[data-pet-action]');
          if (button) doAction(card, button.getAttribute('data-pet-action'));
        });
      }
      card._petActionsBound = true;
    }
    refresh(card);
    return card;
  }

  global.HomeworkMagicAvatarPet = Object.freeze({attach, refresh});
})(window);
