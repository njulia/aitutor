'use strict';

const familyState = {
  studyPlanEnabled: false,
  kids: new Map(),
  familyCode: '',
  limit: 0,
  canAdd: false,
  editingId: null,
  pendingPasswordAction: null,
  scoreTrendChart: null,
  scoreTrendResizeTimer: null,
  overviewLoaded: false,
};

const SCORE_TREND_COLOURS = [
  '#5d56d8', '#d23c77', '#087f8c', '#d66c00', '#2878b5', '#7d5a3a',
];

function byId(id) { return document.getElementById(id); }

function clearNode(item) {
  while (item.firstChild) item.removeChild(item.firstChild);
}

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined && text !== null) item.textContent = String(text);
  return item;
}

function setStatus(message, isError = false) {
  const text = String(message || '').trim();
  const status = byId('page-status');
  if (status) {
    status.textContent = '';
    status.className = '';
  }
  if (!text) return;

  const modal = byId('notification-modal');
  const title = byId('notification-modal-title');
  const body = byId('notification-modal-body');
  if (!modal || !title || !body) {
    // Keep a safe fallback if the notification markup is unavailable.
    console.warn(text);
    return;
  }

  title.textContent = isError ? 'Something went wrong' : 'Message';
  body.textContent = text;
  modal.dataset.error = isError ? 'true' : 'false';
  modal.classList.add('show');
  byId('close-notification').focus();
}

function closeNotificationModal() {
  const modal = byId('notification-modal');
  if (modal) modal.classList.remove('show');
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...options,
    headers: {
      'Accept': 'application/json',
      ...(options.body ? {'Content-Type': 'application/json'} : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg || String(item)).join('; ')
      : (data.detail || data.error || 'That action could not be completed.');
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return data;
}

function combinedLoginCode(kidCode) {
  if (!familyState.familyCode || !kidCode) return '';
  const family = String(familyState.familyCode).replace(/^FAM-/, '');
  const kid = String(kidCode).replace(/^KID-/, '');
  return `${family}-${kid}`;
}

function metric(value, label) {
  const card = node('div', 'metric');
  card.append(node('strong', '', value), node('span', '', label));
  return card;
}

function scorePoint(item) {
  if (!item || item.score === null || item.score === undefined || !item.created_at) return null;
  const score = Number(item && item.score);
  const maxScore = Number(item && item.max_score);
  const date = new Date(item && item.created_at);
  if (!Number.isFinite(score) || !Number.isFinite(maxScore) || maxScore <= 0
      || Number.isNaN(date.getTime())) return null;
  const day = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  return {
    day,
    date,
    score: Math.max(0, Math.min(100, Math.round((score / maxScore) * 1000) / 10)),
  };
}

function scoreSeries(kid, index) {
  const days = new Map();
  const history = kid.progress && Array.isArray(kid.progress.score_history)
    ? kid.progress.score_history : [];
  history.forEach((item) => {
    const point = scorePoint(item);
    if (!point) return;
    const current = days.get(point.day) || {day: point.day, date: point.date, total: 0, count: 0};
    current.total += point.score;
    current.count += 1;
    if (point.date > current.date) current.date = point.date;
    days.set(point.day, current);
  });
  const points = Array.from(days.values())
    .map((item) => ({
      day: item.day,
      date: item.date,
      score: Math.round((item.total / item.count) * 10) / 10,
    }))
    .sort((a, b) => a.date - b.date);
  return {
    id: kid.id,
    name: kid.name || 'Child',
    colour: SCORE_TREND_COLOURS[index % SCORE_TREND_COLOURS.length],
    points,
  };
}

function formatTrendDate(date) {
  return date.toLocaleDateString('en-GB', {day: 'numeric', month: 'short'});
}

function destroyScoreTrendChart() {
  if (!familyState.scoreTrendChart) return;
  try { familyState.scoreTrendChart.destroy(); } catch (error) {
    console.debug('Score trend cleanup skipped:', error);
  }
  familyState.scoreTrendChart = null;
}

function renderScoreTrend() {
  const canvas = byId('family-score-trend-chart');
  const empty = byId('family-score-trend-empty');
  const legend = byId('family-score-trend-legend');
  const series = Array.from(familyState.kids.values()).map(scoreSeries);
  destroyScoreTrendChart();
  clearNode(legend);

  series.forEach((item) => {
    const entry = node('li');
    const swatch = node('span', 'score-trend-swatch');
    swatch.style.backgroundColor = item.colour;
    const latest = item.points[item.points.length - 1];
    const detail = latest
//          ? `${item.name}: latest ${latest.score}% on ${formatTrendDate(latest.date)}`
      ? `${item.name}`
      : `${item.name}: no marked scores yet`;
    entry.append(swatch, node('span', '', detail));
    legend.append(entry);
  });

  const scoredSeries = series.filter((item) => item.points.length > 0);
  if (!scoredSeries.length) {
    canvas.hidden = true;
    empty.hidden = false;
    empty.textContent = series.length
      ? 'No marked scores are available yet. The chart will appear after homework is reviewed.'
      : 'Add a Child profile to start tracking score trends.';
    canvas.setAttribute('aria-label', 'No marked scores are available for the family yet.');
    return;
  }
  if (typeof window.Chart !== 'function') {
    canvas.hidden = true;
    empty.hidden = false;
    empty.textContent = 'The score chart could not be displayed. Please refresh the page.';
    return;
  }

  const days = new Map();
  scoredSeries.forEach((item) => item.points.forEach((point) => {
    if (!days.has(point.day)) days.set(point.day, point.date);
  }));
  const timeline = Array.from(days, ([day, date]) => ({day, date}))
    .sort((a, b) => a.date - b.date);
  canvas.hidden = false;
  empty.hidden = true;
  const plot = canvas.parentElement;
  const maxLabels = Math.max(3, Math.floor((plot.clientWidth || window.innerWidth) / 90));
  const labelStep = Math.max(1, Math.ceil(timeline.length / maxLabels));
  const labels = timeline.map((item, index) => (
    index % labelStep === 0 || index === timeline.length - 1
      ? formatTrendDate(item.date) : ''
  ));
  const summaries = series.map((item) => {
    const latest = item.points[item.points.length - 1];
    return latest ? `${item.name}, latest ${latest.score}%` : `${item.name}, no marked scores`;
  });
  canvas.setAttribute('aria-label', `Score trend over time. ${summaries.join('; ')}.`);

  familyState.scoreTrendChart = new window.Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: scoredSeries.map((item) => {
        const values = new Map(item.points.map((point) => [point.day, point.score]));
        return {
          label: item.name,
          data: timeline.map((point) => values.has(point.day) ? values.get(point.day) : null),
          borderColor: item.colour,
          pointBackgroundColor: item.colour,
          borderWidth: 3,
          pointRadius: 4,
          spanGaps: true,
          fill: false,
        };
      }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {legend: {display: false}},
      scales: {y: {beginAtZero: true, max: 100}},
    },
  });
}

function scheduleScoreTrendResize() {
  if (!familyState.overviewLoaded) return;
  window.clearTimeout(familyState.scoreTrendResizeTimer);
  familyState.scoreTrendResizeTimer = window.setTimeout(renderScoreTrend, 180);
}

function renderKids() {
  const grid = byId('kids-grid');
  clearNode(grid);
  if (!familyState.kids.size) {
    grid.append(node('div', 'empty', 'No Child profiles yet.'));
    return;
  }

  familyState.kids.forEach((kid) => {
    const card = node('article', 'kid-card');
    const title = node('div', 'kid-title');
    title.append(node('h3', '', kid.name || 'Child'));
    if (kid.is_default) title.append(node('span', 'default-badge', 'Default'));
    const edit = node('button', 'btn btn-secondary', 'Edit profile');
    edit.type = 'button';
    edit.addEventListener('click', () => showProfileForm(kid));
    title.append(edit);
    card.append(title, node('p', 'muted', `Year ${kid.year_group}`));

    const codeValue = combinedLoginCode(kid.kid_code);
    const code = node('div', 'kid-code');
    const codeText = node('span', 'kid-code-value');
    codeText.append(node('span', '', 'Login code: '), node('strong', '', codeValue || 'Not assigned'));
    code.append(codeText);
    if (codeValue) {
      const copy = node('button', 'btn btn-secondary copy-code-button', 'Copy');
      copy.type = 'button';
      copy.setAttribute('aria-label', `Copy login code for ${kid.name || 'Child'}`);
      copy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(codeValue);
          copy.textContent = 'Copied';
          window.setTimeout(() => { copy.textContent = 'Copy'; }, 1500);
        } catch (error) {
          window.prompt('Copy this kid login code:', codeValue);
        }
      });
      code.append(copy);
    }
    const loginBtn = node('button', 'btn btn-primary copy-code-button', 'Child Login');
    loginBtn.type = 'button';
    loginBtn.setAttribute('aria-label', `Login as ${kid.name || 'Child'}`);
    loginBtn.addEventListener('click', () => {
      const loginUrl = `/kid-login${codeValue ? `?code=${encodeURIComponent(codeValue)}` : ''}`;
      window.open(loginUrl, '_blank');
    });
    code.append(loginBtn);
    card.append(code);

    const target = kid.learning_target || {};
    const targetBox = node('div', 'target-form');
    targetBox.append(node('strong', '', 'Learning target'));
    const row = node('div', 'form-row');
    const dailyField = node('div', 'field');
    const dailyLabel = node('label', '', 'Daily activities');
    const daily = node('input');
    daily.type = 'number'; daily.min = '1'; daily.max = '10'; daily.value = target.daily_goal || 1;
    dailyLabel.htmlFor = `daily-${kid.id}`; daily.id = `daily-${kid.id}`;
    dailyField.append(dailyLabel, daily);
    const weeklyField = node('div', 'field');
    const weeklyLabel = node('label', '', 'Weekly XP goal');
    const weekly = node('input');
    weekly.type = 'number'; weekly.min = '10'; weekly.max = '2000'; weekly.value = target.weekly_xp_goal || 100;
    weeklyLabel.htmlFor = `weekly-${kid.id}`; weekly.id = `weekly-${kid.id}`;
    weeklyField.append(weeklyLabel, weekly);
    const save = node('button', 'btn btn-primary', 'Save target');
    save.type = 'button';
    save.addEventListener('click', () => requestPassword(async (password) => {
      await api('/api/parent/learning-target', {
        method: 'POST',
        body: JSON.stringify({
          student_id: kid.id,
          daily_goal: Number(daily.value),
          weekly_xp_goal: Number(weekly.value),
          parent_password: password,
        }),
      });
      setStatus(`Learning target saved for ${kid.name}.`);
      await loadOverview();
    }));
    row.append(dailyField, weeklyField, save);
    targetBox.append(row);
    card.append(targetBox);

    const wallet = kid.wallet || {};
    const progress = kid.progress || {};
    const level = wallet.level || {};
    const metrics = node('div', 'metrics');
    metrics.append(
      metric(wallet.lifetime_xp || 0, 'Lifetime XP'),
      metric(wallet.gift_points || 0, 'Gift Points'),
      metric(progress.total_sessions || 0, 'Sessions'),
      metric(`${progress.average_accuracy || 0}%`, 'Accuracy'),
      metric(progress.current_streak || 0, 'Day streak'),
      metric(level.name || 'Starter', 'Level'),
    );
    card.append(metrics);

    const actions = node('div', 'card-actions');
    const progressLink = node('a', 'btn-link', 'Track Child Progress');
    progressLink.href = `/progress?student_id=${encodeURIComponent(kid.id)}`;
    const rewardLink = node('a', 'btn-link', 'Reward Child');
    rewardLink.href = `/rewards?student_id=${encodeURIComponent(kid.id)}`;
    rewardLink.style.marginLeft = 'auto';
    if (familyState.studyPlanEnabled) {
      const planButton = node('button', 'btn-link', '30-day 11+ plan');
      planButton.type = 'button';
      planButton.addEventListener('click', () => openStudyPlan(kid));
      actions.append(progressLink, planButton, rewardLink);
    } else {
      actions.append(progressLink, rewardLink);
    }
    if (Number(wallet.pending_rewards || 0) > 0) {
      actions.append(node('span', 'default-badge', `${wallet.pending_rewards} pending gift`));
    }
    card.append(actions);

    grid.append(card);
  });
}

async function loadOverview() {
  const data = await api('/api/parent/overview');
  familyState.familyCode = data.family_code || '';
  familyState.limit = Number(data.student_limit || 0);
  familyState.canAdd = data.can_add_student === true;
  familyState.studyPlanEnabled = data.study_plan_enabled === true;
  familyState.kids = new Map((data.kids || []).map((kid) => [kid.id, kid]));
  familyState.overviewLoaded = true;
  byId('family-limit-note').textContent = familyState.limit
    ? `${familyState.kids.size} of ${familyState.limit} student profiles used.` : '';
  byId('add-child-button').disabled = !familyState.canAdd;
  byId('add-child-button').title = familyState.canAdd ? '' : 'Your current plan has reached its user limit.';
  renderKids();
  renderScoreTrend();
}

function showProfileForm(kid = null) {
  if (!kid && !familyState.canAdd) return;
  familyState.editingId = kid ? kid.id : null;
  byId('profile-form-title').textContent = kid ? 'Edit Child profile' : 'Add a child';
  byId('save-profile-button').textContent = kid ? 'Save profile' : 'Add child';
  byId('profile-name').value = kid ? kid.name : '';
  byId('profile-year').value = String(kid ? kid.year_group : 3);
  byId('profile-form').classList.add('show');
  byId('profile-name').focus();
}

function hideProfileForm() {
  familyState.editingId = null;
  byId('profile-form').classList.remove('show');
  byId('profile-form').reset();
}

async function saveProfile(event) {
  event.preventDefault();
  const body = {
    name: byId('profile-name').value.trim(),
    year_group: Number(byId('profile-year').value),
    age: Number(byId('profile-year').value) + 5,
  };
  const editing = familyState.editingId;
  await api(editing ? `/api/students/${encodeURIComponent(editing)}` : '/api/students', {
    method: editing ? 'PUT' : 'POST',
    body: JSON.stringify(body),
  });
  hideProfileForm();
  setStatus(editing ? 'Child profile updated.' : 'Child profile added.');
  await loadOverview();
}

async function loadDigest() {
  const data = await api('/api/parent/xp-digest');
  const body = byId('digest-body');
  clearNode(body);
  const kids = data.digest && data.digest.kids ? data.digest.kids : [];
  if (!kids.length) {
    const row = node('tr'); const cell = node('td', '', 'No activity in the last 24 hours.');
    cell.colSpan = 4; row.append(cell); body.append(row); return;
  }
  kids.forEach((kid) => {
    const subjects = (kid.subjects || []).map((item) => `${item.subject} ${item.accuracy}%`).join(', ') || 'No subject data';
    const row = node('tr');
    row.append(node('td', '', kid.name), node('td', '', kid.total_xp || 0),
      node('td', '', kid.event_count || 0), node('td', '', subjects));
    body.append(row);
  });
}

async function loadSummaryPreferences() {
  const data = await api('/api/parent/learning-summary/preferences');
  const prefs = data.preferences || {};
  byId('summary-email-enabled').checked = prefs.enabled !== false;
  byId('summary-frequency').value = prefs.frequency || 'weekly';
  byId('summary-interval-days').value = String(prefs.interval_days || 7);
  toggleSummaryInterval();
}

function toggleSummaryInterval() {
  const custom = byId('summary-frequency').value === 'custom';
  byId('summary-interval-days').disabled = !custom;
}

async function saveSummaryPreferences(event) {
  event.preventDefault();
  const body = {
    enabled: byId('summary-email-enabled').checked,
    frequency: byId('summary-frequency').value,
    interval_days: Number(byId('summary-interval-days').value || 7),
  };
  await api('/api/parent/learning-summary/preferences', {method: 'PUT', body: JSON.stringify(body)});
  setStatus(body.enabled ? 'Learning summary email settings saved.' : 'Learning summary emails unsubscribed.');
  await loadSummaryPreferences();
}

async function loadCatalog() {
  const data = await api('/api/rewards/catalog');
  const list = byId('catalog-list');
  clearNode(list);
  if (!(data.items || []).length) { list.append(node('li', 'empty', 'No family rewards yet.')); return; }
  data.items.forEach((item) => {
    const entry = node('li', 'list-item');
    const main = node('div', 'item-main');
    const copy = node('div');
    copy.append(node('div', 'item-title', item.name), node('div', 'item-meta', `${item.xp_cost} Gift Points`));
    main.append(node('span', 'item-icon', item.icon || '🎁'), copy);
    const remove = node('button', 'btn btn-danger', 'Delete');
    remove.type = 'button';
    remove.addEventListener('click', () => {
      if (!window.confirm(`Delete “${item.name}”?`)) return;
      requestPassword(async (password) => {
        await api(`/api/rewards/catalog/${encodeURIComponent(item.id)}`, {
          method: 'DELETE', body: JSON.stringify({parent_password: password}),
        });
        setStatus('Reward deleted.');
        await loadCatalog();
      });
    });
    entry.append(main, remove); list.append(entry);
  });
}

async function loadGiftRequests() {
  const data = await api('/api/parent/gift-requests');
  const holder = byId('gift-requests');
  clearNode(holder);
  if (!(data.requests || []).length) { holder.append(node('div', 'empty', 'No pending gift requests.')); return; }
  const list = node('ul', 'list');
  data.requests.forEach((request) => {
    const entry = node('li', 'list-item');
    const main = node('div', 'item-main');
    const copy = node('div');
    copy.append(node('div', 'item-title', request.reward_name),
      node('div', 'item-meta', `${request.student_name} · ${request.points_cost} Gift Points`));
    main.append(node('span', 'item-icon', request.reward_icon || '🎁'), copy);
    const actions = node('div', 'card-actions');
    const approve = node('button', 'btn btn-primary', 'Approve'); approve.type = 'button';
    const decline = node('button', 'btn btn-danger', 'Decline'); decline.type = 'button';
    approve.addEventListener('click', () => decideGift(request, 'approve'));
    decline.addEventListener('click', () => decideGift(request, 'decline'));
    actions.append(approve, decline); entry.append(main, actions); list.append(entry);
  });
  holder.append(list);
}

function decideGift(request, decision) {
  if (decision === 'decline' && !window.confirm(`Decline ${request.student_name}'s gift request?`)) return;
  requestPassword(async (password) => {
    await api(`/api/parent/gift-requests/${encodeURIComponent(request.id)}/${decision}`, {
      method: 'POST', body: JSON.stringify({parent_password: password}),
    });
    setStatus(decision === 'approve' ? 'Gift request approved.' : 'Gift request declined.');
    await Promise.all([loadGiftRequests(), loadOverview()]);
  });
}

async function openStudyPlan(kid) {
  const modal = byId('study-plan-modal');
  const status = byId('study-plan-modal-status');
  const body = byId('study-plan-modal-body');
  modal.classList.add('show');
  status.textContent = `Loading ${kid.name || 'Child'}'s plan…`;
  clearNode(body);
  try {
    const data = await api(`/api/parent/11plus-study-plan/${encodeURIComponent(kid.id)}`);
    if (data.locked) {
      status.textContent = 'An active 11+ Premium plan is needed to view this study plan.';
      body.append(node('a', 'btn-link', 'View 11+ Premium plans'));
      body.firstChild.href = '/pricing';
      return;
    }
    if (!data.ready || !data.plan) {
      status.textContent = 'No completed paid mock has created a plan yet, or the plan is still being prepared.';
      return;
    }
    const plan = data.plan;
    status.textContent = `30 minutes a day for ${plan.duration_days || 30} days · focused on ${(
      plan.weaknesses || []).slice(0, 3).map((item) => item.topic).join(', ') || 'targeted practice'}.`;
    (plan.days || []).forEach((day) => {
      const card = node('article', 'study-plan-day');
      card.append(node('h3', '', `Day ${day.day} · ${day.minutes} minutes`));
      card.append(node('p', '', `Focus: ${day.focus_topic || 'Targeted practice'}`));
      const list = node('ol');
      (day.questions || []).forEach((question) => {
        const item = node('li');
        item.append(node('span', '', question.question));
        const options = node('ul');
        (question.options || []).forEach((option) => options.append(node('li', '', option)));
        item.append(options); list.append(item);
      });
      card.append(list); body.append(card);
    });
  } catch (error) {
    status.textContent = error.status === 402
      ? 'An active 11+ Premium plan is needed to view this study plan.'
      : (error.message || 'The study plan could not be loaded.');
  }
}

function requestPassword(action) {
  familyState.pendingPasswordAction = action;
  byId('parent-password').value = '';
  byId('password-modal').classList.add('show');
  byId('parent-password').focus();
}

function closePasswordModal() {
  familyState.pendingPasswordAction = null;
  byId('password-modal').classList.remove('show');
}

async function initialise() {
  try {
    const context = await window.HomeworkMagicSession.get(true);
    if (!context.authenticated || context.role !== 'parent' && context.role !== 'teacher') {
      window.location.replace(context.role === 'kid' ? '/app' : '/login?next=/parent-dashboard');
      return;
    }
    await Promise.all([loadOverview(), loadDigest(), loadCatalog(), loadGiftRequests(), loadSummaryPreferences()]);
  } catch (error) {
    if (error.status === 401) window.location.replace('/login?next=/parent-dashboard');
    else setStatus(error.message || 'The dashboard could not be loaded.', true);
  }
}

byId('add-child-button').addEventListener('click', () => showProfileForm());
byId('cancel-profile-button').addEventListener('click', hideProfileForm);
byId('profile-form').addEventListener('submit', (event) => {
  saveProfile(event).catch((error) => setStatus(error.message, true));
});
byId('catalog-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const reward = {
    name: byId('reward-name').value.trim(), icon: byId('reward-icon').value.trim() || '🎁',
    xp_cost: Number(byId('reward-cost').value),
  };
  requestPassword(async (password) => {
    await api('/api/rewards/catalog', {method: 'POST', body: JSON.stringify({...reward, parent_password: password})});
    byId('catalog-form').reset(); byId('reward-cost').value = '100'; setStatus('Reward added.'); await loadCatalog();
  });
});
byId('summary-frequency').addEventListener('change', toggleSummaryInterval);
byId('summary-email-form').addEventListener('submit', (event) => {
  saveSummaryPreferences(event).catch((error) => setStatus(error.message, true));
});
byId('send-digest-button').addEventListener('click', () => requestPassword(async (password) => {
  await api('/api/parent/xp-digest/send', {method: 'POST', body: JSON.stringify({parent_password: password})});
  setStatus('Learning summary email sent.');
}));
byId('cancel-password').addEventListener('click', closePasswordModal);
byId('close-notification').addEventListener('click', closeNotificationModal);
byId('notification-modal').addEventListener('click', (event) => {
  if (event.target === event.currentTarget) closeNotificationModal();
});
byId('close-study-plan').addEventListener('click', () => byId('study-plan-modal').classList.remove('show'));
byId('password-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!familyState.pendingPasswordAction) return;
  try {
    await familyState.pendingPasswordAction(byId('parent-password').value);
    closePasswordModal();
  } catch (error) {
    setStatus(error.message, true);
  }
});
byId('parent-logout').addEventListener('click', async (event) => {
  event.preventDefault();
  await fetch('/api/logout', {method: 'POST', credentials: 'same-origin'});
  localStorage.removeItem('auth_state');
  window.HomeworkMagicSession.clear();
  window.location.assign('/');
});

window.addEventListener('resize', scheduleScoreTrendResize, {passive: true});
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeNotificationModal();
});

initialise();
