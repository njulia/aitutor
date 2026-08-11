'use strict';

(function initialiseCapybaraPlaytime(global) {
  const $ = (selector) => document.querySelector(selector);
  const app = $('#playtime-app');
  const login = $('#playtime-login');
  const status = $('#playtime-status');
  const gone = $('#pet-gone');
  const pet = $('#capybara');
  const fruit = $('#pet-fruit');
  const message = $('#pet-message');
  let current = null;
  let busy = false;

  const activityMessages = {
    play: ['Boing! I can jump! 🦫', 'Roll roll roll! That was fun! 💕'],
    food: ['Nom nom nom! 🥕', 'Munch munch! My tummy is happy! 💕'],
    poo: ['Oops! 💩 Thanks for cleaning up!', 'All clean! My little home is tidy! ✨'],
    sleep: ['Eyes closed… zzz 💤', 'Shhh… I am having a cosy nap! 🌙'],
  };

  function setStatus(text) {
    if (status) status.textContent = text || '';
  }

  function randomMessage(list) {
    return list[Math.floor(Math.random() * list.length)];
  }

  function animate(action) {
    if (!pet) return;
    pet.className = 'hm-capybara';
    document.querySelectorAll('.hm-action-prop, .hm-sleep-z').forEach((el) => {
      el.classList.remove('is-prop-active');
    });
    const prop = document.querySelector(`.hm-prop-${action}`);
    const zzz = $('#sleep-z');
    if (action === 'sleep' && zzz) zzz.classList.add('is-prop-active');
    if (prop) prop.classList.add('is-prop-active');
    if (action === 'poo') {
      const broom = $('#prop-broom');
      if (broom) broom.classList.add('is-prop-active');
    }
    void pet.offsetWidth;
    pet.classList.add(`is-action-${action}`);
    window.setTimeout(() => {
      pet.classList.remove(`is-action-${action}`);
      document.querySelectorAll('.hm-action-prop, .hm-sleep-z').forEach((el) => {
        el.classList.remove('is-prop-active');
      });
    }, action === 'sleep' ? 3000 : 2200);
  }

  function renderGoal(goal) {
    const count = $('#goal-count');
    const title = $('#goal-title');
    const copy = $('#goal-copy');
    const hint = $('#play-hint');
    if (!goal) return;
    count.textContent = `${goal.count} / ${goal.target}`;
    if (goal.completed) {
      title.textContent = 'Daily Goal complete! 🎉';
      copy.textContent = 'Playtime is unlocked. Your capybara is waiting!';
      hint.textContent = 'Pick an activity and make your little friend smile.';
    } else {
      title.textContent = 'Finish today\'s Daily Goal';
      copy.textContent = `${Math.max(0, goal.target - goal.count)} more learning ${goal.target - goal.count === 1 ? 'activity' : 'activities'} to unlock playtime.`;
      hint.textContent = 'Complete today\'s goal first — then all four activities unlock.';
    }
  }

  function renderPet(petState) {
    current = petState;
    if (!petState) return;
    if (!petState.alive) {
      app.hidden = true;
      gone.hidden = false;
      setStatus('Your capybara has finished its little journey.');
      return;
    }
    gone.hidden = true;
    app.hidden = false;
    const growth = petState.growth || {};
    $('#pet-stage-name').textContent = growth.name || 'Baby Capy';
    $('#pet-growth-copy').textContent = growth.copy || 'Tiny paws, huge cuddles!';
    $('#pet-generation').textContent = `Baby #${petState.generation || 1}`;
    $('#care-points').textContent = `${growth.care_points || 0}`;
    const next = Number(growth.next_care_points || 0);
    const points = Number(growth.care_points || 0);
    const pct = next ? Math.min(100, Math.round((points / next) * 100)) : 100;
    $('#care-bar').style.width = `${pct}%`;
    $('#pet-fruit').textContent = (petState.fruit_info || {}).emoji || '🍎';
    pet.setAttribute('data-stage', String(growth.stage || 1));
    document.querySelectorAll('.hm-fruit-choice').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.fruit === petState.fruit ? 'true' : 'false');
    });
    const unlocked = Boolean(petState.daily_goal_completed);
    document.querySelectorAll('.hm-activity').forEach((button) => { button.disabled = !unlocked || busy; });
    if (petState.care_due_today && !petState.played_today) {
      message.textContent = 'I finished today\'s goal with you! Can we play? 🎾';
    }
  }

  function renderFruits(fruits) {
    const grid = $('#fruit-grid');
    if (!grid || !fruits) return;
    grid.textContent = '';
    Object.entries(fruits).forEach(([key, info]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'hm-fruit-choice';
      button.dataset.fruit = key;
      button.setAttribute('aria-pressed', 'false');
      const icon = document.createElement('span');
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = info.emoji;
      const label = document.createElement('small');
      label.textContent = info.label;
      button.appendChild(icon);
      button.appendChild(label);
      button.addEventListener('click', () => chooseFruit(key));
      grid.appendChild(button);
    });
  }

  async function load() {
    setStatus('Loading your capybara…');
    try {
      const session = await fetch('/api/session-context', { credentials: 'same-origin' }).then((r) => r.json());
      if (!session.authenticated || session.role !== 'kid') {
        login.hidden = false;
        app.hidden = true;
        setStatus('');
        return;
      }
      $('#kid-name').textContent = String(session.student?.name || 'Your').split(/\s+/)[0];
      const response = await fetch('/api/rewards/capybara', { credentials: 'same-origin' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load playtime.');
      login.hidden = true;
      renderGoal(data.daily_goal);
      renderFruits(data.pet.fruits);
      renderPet(data.pet);
      setStatus('');
    } catch (error) {
      setStatus(error.message || 'Could not load playtime. Please try again.');
    }
  }

  async function chooseActivity(activity) {
    if (busy || !current || !current.daily_goal_completed) return;
    busy = true;
    document.querySelectorAll('.hm-activity').forEach((button) => { button.disabled = true; });
    try {
      const response = await fetch('/api/rewards/capybara/activity', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({activity}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not do that just now.');
      renderGoal(data.daily_goal);
      renderPet(data.pet);
      message.textContent = randomMessage(activityMessages[activity] || ['That was fun! ✨']);
      animate(activity);
    } catch (error) {
      message.textContent = error.message || 'Let\'s try again!';
    } finally {
      busy = false;
      if (current) renderPet(current);
    }
  }

  async function chooseFruit(key) {
    if (busy || !current || !current.alive) return;
    busy = true;
    try {
      const response = await fetch('/api/rewards/capybara/fruit', {
        method: 'PUT', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({fruit: key}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not change the fruit.');
      renderGoal(data.daily_goal);
      renderPet(data.pet);
      message.textContent = `Yay! ${data.pet.fruit_info.label} looks yummy! ${data.pet.fruit_info.emoji}`;
      animate('fruit');
    } catch (error) {
      message.textContent = error.message || 'Let\'s try another fruit!';
    } finally {
      busy = false;
      if (current) renderPet(current);
    }
  }

  async function adopt() {
    if (busy) return;
    busy = true;
    const button = $('#adopt-button');
    button.disabled = true;
    try {
      const response = await fetch('/api/rewards/capybara/adopt', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({activity: 'adopt'}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not welcome your new baby.');
      renderGoal(data.daily_goal);
      renderFruits(data.pet.fruits);
      renderPet(data.pet);
      message.textContent = 'Hello, baby capy! Let\'s take good care of you. 💕';
    } catch (error) {
      setStatus(error.message || 'Could not welcome your new baby.');
    } finally {
      busy = false;
      button.disabled = false;
    }
  }

  document.querySelectorAll('.hm-activity').forEach((button) => {
    button.addEventListener('click', () => chooseActivity(button.dataset.activity));
  });
  $('#adopt-button').addEventListener('click', adopt);
  load();
})(window);
