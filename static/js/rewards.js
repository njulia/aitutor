'use strict';

const rewardState = {
  account: null,
  studentId: null,
  dashboard: null,
};

const pageMessage = document.getElementById('page-message');
const rewardContent = document.getElementById('reward-content');
const loginCard = document.getElementById('login-card');
const learnerSelect = document.getElementById('learner-select');

function setMessage(message, kind = '') {
  pageMessage.textContent = message || '';
  pageMessage.className = `page-message${kind ? ` ${kind}` : ''}`;
}

function showToast(message) {
  const toast = document.getElementById('reward-toast');
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 4500);
}

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...(options.body ? {'Content-Type': 'application/json'} : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || data.error || 'That did not work. Please try again.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function clearNode(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function parentPassword() {
  return document.getElementById('parent-password').value;
}

function clearParentPassword() {
  document.getElementById('parent-password').value = '';
}

function requireParentPassword() {
  const password = parentPassword();
  if (!password) {
    setMessage('A grown-up needs to enter the parent account password first.', 'error');
    document.getElementById('parent-password').focus();
    return null;
  }
  return password;
}

function renderWallet(data) {
  const wallet = data.wallet;
  const level = wallet.level;
  const giftAccess = data.gift_access || {};
  document.getElementById('lifetime-xp').textContent = String(wallet.lifetime_xp);
  document.getElementById('gift-points').textContent = String(wallet.gift_points);
  const giftPointsNote = document.querySelector('.wallet-card.spendable small');
  giftPointsNote.textContent = giftAccess.eligible
    ? 'Gift Points are switched on by your grown-up'
    : 'A grown-up manages Gift Points and gifts';
  document.getElementById('level-icon').textContent = level.icon;
  document.getElementById('level-number').textContent = String(level.number);
  document.getElementById('level-name').textContent = level.name;
  const progress = document.getElementById('level-progress');
  progress.value = level.progress_percent;
  progress.textContent = `${level.progress_percent}%`;
  document.getElementById('level-next').textContent = level.next
    ? `${level.xp_to_next} XP to Level ${level.next.number}: ${level.next.name}`
    : 'Top level reached—what a learning legend!';
}

function renderGiftAccess(giftAccess) {
  const eligible = Boolean(giftAccess && giftAccess.eligible);
  const note = document.getElementById('gift-access-note');
  if (!note) return;
  const copy = note.querySelector('p');
  if (!copy) return;
  const parentPlanCopy = document.getElementById('parent-plan-copy');
  const legacyPlanLink = document.getElementById('gift-access-plan-link');
  if (legacyPlanLink) legacyPlanLink.remove();
  clearNode(copy);
  const heading = element('strong', '', 'Everyone can earn XP. ');
  copy.append(heading);
  copy.append(document.createTextNode('A grown-up manages Gift Points, gifts and plans.'));
  note.classList.toggle('eligible', eligible);
  if (parentPlanCopy) {
    parentPlanCopy.textContent = eligible
      ? 'This family’s eligible monthly plan earns Gift Points and allows parent-approved gift requests. '
      : 'Gift Points and gift approvals require an eligible monthly plan. The five-day pass and free beta access do not include physical gifts. ';
  }
}

function renderQuests(quests) {
  const grid = document.getElementById('quest-grid');
  clearNode(grid);
  quests.forEach((quest) => {
    const card = element('article', `quest-card${quest.completed ? ' completed' : ''}`);
    const top = element('div', 'quest-top');
    const icon = element('span', 'quest-icon', quest.completed ? '✅' : quest.icon);
    icon.setAttribute('aria-hidden', 'true');
    top.append(icon, element('span', 'quest-xp', `+${quest.bonus_xp} XP`));

    const heading = element('h3', '', quest.name);
    const description = element('p', '', quest.description);
    const progressCopy = element('div', 'quest-progress-copy');
    progressCopy.append(
      element('span', '', quest.period),
      element(
        'span',
        quest.completed ? 'quest-done' : '',
        quest.completed ? 'Quest complete!' : `${quest.progress}/${quest.target}`,
      ),
    );
    const track = element('div', 'quest-track');
    track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-label', `${quest.name} progress`);
    track.setAttribute('aria-valuemin', '0');
    track.setAttribute('aria-valuemax', String(quest.target));
    track.setAttribute('aria-valuenow', String(quest.progress));
    const fill = element('span');
    fill.style.width = `${Math.round((quest.progress / quest.target) * 100)}%`;
    track.append(fill);
    card.append(top, heading, description, progressCopy, track);
    grid.append(card);
  });
}

function renderCertificates(certificates) {
  const grid = document.getElementById('certificate-grid');
  clearNode(grid);
  certificates.forEach((certificate) => {
    const card = element(
      'article',
      `certificate-card ${certificate.unlocked ? 'unlocked' : 'locked'}`,
    );
    const icon = element('span', 'certificate-icon', certificate.unlocked ? certificate.icon : '🔒');
    icon.setAttribute('aria-hidden', 'true');
    card.append(
      icon,
      element('h3', '', certificate.title),
      element(
        'p',
        '',
        certificate.unlocked
          ? `Unlocked at ${certificate.threshold} lifetime XP`
          : `Unlocks at ${certificate.threshold} lifetime XP`,
      ),
    );
    if (certificate.unlocked) {
      const link = element('a', 'reward-button secondary', 'Print');
      link.href = certificate.print_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      card.append(link);
    }
    grid.append(card);
  });
}

function pendingRewardCodes(redemptions) {
  return new Set(
    redemptions
      .filter((item) => ['pending', 'approved'].includes(item.status))
      .map((item) => item.reward_code),
  );
}

async function requestReward(code) {
  try {
    const data = await jsonFetch('/api/rewards/redemptions', {
      method: 'POST',
      body: JSON.stringify({student_id: rewardState.studentId, reward_code: code}),
    });
    showToast(data.message || 'Your reward request is waiting for a grown-up.');
    setMessage(
      'Great choice! Your XP stays forever. A grown-up will check the gift request.',
      'success',
    );
    await loadDashboard();
  } catch (error) {
    setMessage(error.message, 'error');
  }
}

function renderCatalog(data) {
  const grid = document.getElementById('catalog-grid');
  if (!grid) return;
  clearNode(grid);
  const pendingCodes = pendingRewardCodes(data.redemptions);
  const giftAccessEligible = Boolean(data.gift_access && data.gift_access.eligible);
  data.catalog.forEach((item) => {
    const card = element(
      'article',
      `catalog-card${giftAccessEligible ? '' : ' subscription-locked'}`,
    );
    const icon = element('span', 'catalog-icon', item.icon);
    icon.setAttribute('aria-hidden', 'true');
    card.append(icon, element('h3', '', item.name));
    card.append(
      element('span', 'branded-tag', 'Homework Magic logo'),
      element('p', 'catalog-description', item.description),
      element('p', 'catalog-cost', `${item.points_cost} Gift Points`),
    );

    const button = element('button', 'reward-button');
    button.type = 'button';
    const shortfall = Math.max(0, item.points_cost - data.wallet.gift_points);
    if (!giftAccessEligible) {
      button.textContent = 'Ask a grown-up';
      button.disabled = true;
    } else if (pendingCodes.has(item.code)) {
      button.textContent = 'Request in progress';
      button.disabled = true;
    } else if (shortfall > 0) {
      button.textContent = `Need ${shortfall} more Gift Points`;
      button.disabled = true;
    } else {
      button.textContent = 'Ask for this gift';
      button.addEventListener('click', () => requestReward(item.code));
    }
    card.append(button);
    grid.append(card);
  });
}

function formatDate(isoValue) {
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-GB', {day: 'numeric', month: 'short'}).format(date);
}

function renderRecent(items) {
  const list = document.getElementById('recent-activity');
  clearNode(list);
  if (!items.length) {
    list.append(element('p', 'empty-state', 'Complete and check an activity to collect your first XP.'));
    return;
  }
  items.forEach((item) => {
    const row = element('div', 'recent-row');
    const label = element('span', '', `${item.label} · ${formatDate(item.created_at)}`);
    const delta = Number(item.xp_delta || 0);
    const giftPoints = Number(item.gift_points_delta || 0);
    const xp = element(
      'span',
      'recent-xp',
      giftPoints > 0
        ? `+${delta} XP · +${giftPoints} Gift Points`
        : `+${delta} XP`,
    );
    row.append(label, xp);
    list.append(row);
  });
}

function actionButton(label, className, handler) {
  const button = element('button', `reward-button ${className || ''}`.trim(), label);
  button.type = 'button';
  button.addEventListener('click', handler);
  return button;
}

function deliveryAddress() {
  const fields = [
    ['delivery-recipient', 'Please enter the adult recipient’s name.'],
    ['delivery-line-1', 'Please enter the first line of the UK delivery address.'],
    ['delivery-town', 'Please enter the town or city.'],
    ['delivery-postcode', 'Please enter the UK postcode.'],
  ];
  for (const [id, message] of fields) {
    const input = document.getElementById(id);
    if (!input.value.trim()) {
      setMessage(message, 'error');
      input.focus();
      return null;
    }
  }
  const confirmed = document.getElementById('adult-recipient-confirmed');
  if (!confirmed.checked) {
    setMessage('Please confirm that the named delivery recipient is an adult.', 'error');
    confirmed.focus();
    return null;
  }
  return {
    recipient_name: document.getElementById('delivery-recipient').value.trim(),
    address_line1: document.getElementById('delivery-line-1').value.trim(),
    address_line2: document.getElementById('delivery-line-2').value.trim(),
    town_city: document.getElementById('delivery-town').value.trim(),
    postcode: document.getElementById('delivery-postcode').value.trim(),
    country: 'GB',
    adult_recipient_confirmed: true,
  };
}

function clearDeliveryAddress() {
  [
    'delivery-recipient',
    'delivery-line-1',
    'delivery-line-2',
    'delivery-town',
    'delivery-postcode',
  ].forEach((id) => {
    document.getElementById(id).value = '';
  });
  document.getElementById('adult-recipient-confirmed').checked = false;
}

async function decideRedemption(id, decision) {
  const password = requireParentPassword();
  if (!password) return;
  const address = decision === 'approve' ? deliveryAddress() : null;
  if (decision === 'approve' && !address) return;
  try {
    await jsonFetch(`/api/rewards/redemptions/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        parent_password: password,
        ...(address ? {delivery_address: address} : {}),
      }),
    });
    clearParentPassword();
    if (decision === 'approve') clearDeliveryAddress();
    const messages = {
      approve: 'Gift approved! XP is unchanged and the Gift Points have been used.',
      decline: 'The request was declined. XP and Gift Points are unchanged.',
      cancel: 'The request was cancelled. Gift Points were returned; XP is unchanged.',
    };
    setMessage(messages[decision], 'success');
    await loadDashboard();
  } catch (error) {
    clearParentPassword();
    setMessage(error.message, 'error');
  }
}

function renderRedemptions(items) {
  const list = document.getElementById('redemption-list');
  if (!list) return;
  clearNode(list);
  if (!items.length) {
    list.append(element('p', 'empty-state', 'No reward requests yet.'));
    return;
  }
  items.forEach((item) => {
    const card = element('article', 'redemption-card');
    const main = element('div', 'redemption-main');
    const copy = element('div');
    copy.append(
      element('div', 'redemption-name', `${item.reward_icon} ${item.reward_name}`),
      element(
        'small',
        '',
        `${item.points_cost} Gift Points · requested ${formatDate(item.requested_at)}`,
      ),
    );
    main.append(copy, element('span', `redemption-status ${item.status}`, item.status));
    card.append(main);

    const actions = element('div', 'redemption-actions');
    if (item.status === 'pending') {
      const canApprove = Boolean(
        rewardState.dashboard
        && rewardState.dashboard.gift_access
        && rewardState.dashboard.gift_access.eligible
      );
      const approveButton = actionButton(
        canApprove ? 'Approve' : 'Active plan needed to approve',
        'good',
        () => decideRedemption(item.id, 'approve'),
      );
      approveButton.disabled = !canApprove;
      actions.append(
        approveButton,
        actionButton('Decline', 'danger', () => decideRedemption(item.id, 'decline')),
      );
    } else if (item.status === 'approved') {
      actions.append(
        element('span', 'shipping-note', 'Homework Magic is preparing this gift.'),
        actionButton(
          'Cancel & return Gift Points',
          'secondary',
          () => decideRedemption(item.id, 'cancel'),
        ),
      );
    } else if (item.status === 'dispatched') {
      actions.append(element('span', 'shipping-note', 'The gift has been dispatched.'));
    }
    if (actions.childElementCount) card.append(actions);
    list.append(card);
  });
}

function renderSummary(summary) {
  document.getElementById('active-days').textContent = String(summary.active_days);
  document.getElementById('subjects-explored').textContent = String(summary.subjects_explored);
  document.getElementById('quests-completed').textContent = String(summary.quests_completed);
}

function renderDashboard(data) {
  rewardState.dashboard = data;
  document.getElementById('reward-title').textContent = `${data.learner.name}'s reward quest`;
  document.getElementById('reward-cheer').textContent = data.learner.age <= 7
    ? 'Have a go, check your work, and watch your forever XP grow!'
    : 'Build permanent XP with steady effort—your marks do not decide your reward.';
  renderWallet(data);
  renderGiftAccess(data.gift_access);
  renderQuests(data.quests);
  renderCertificates(data.certificates);
  renderCatalog(data);
  renderRecent(data.recent_activity);
  renderRedemptions(data.redemptions);
  renderSummary(data.week_summary);
}

async function loadDashboard() {
  if (!rewardState.studentId) return;
  setMessage('Loading reward quests…');
  try {
    const data = await jsonFetch(`/api/rewards?student_id=${encodeURIComponent(rewardState.studentId)}`);
    renderDashboard(data);
    setMessage('');
  } catch (error) {
    if (error.status === 401 && localStorage.getItem('kid_session_token')) {
      setMessage('Your login has expired. Please ask a grown-up for your login code.', 'error');
      rewardContent.hidden = true;
      loginCard.hidden = false;
      return;
    }
    setMessage(error.message, 'error');
  }
}

// 渲染"我的请求"列表
function renderMyRequests(redemptions) {
  const list = document.getElementById('my-requests-list');
  if (!list) return;

  clearNode(list);

  // 只显示自定义请求（reward_code 以 "custom:" 开头）
  const customRequests = redemptions.filter(item =>
    item.reward_code && item.reward_code.startsWith('custom:')
  );

  if (!customRequests.length) {
    list.append(element('p', 'empty-state', 'No requests yet. Send your first request above!'));
    return;
  }

  customRequests.forEach((item) => {
    const card = element('article', 'my-request-card');
    const statusClass = `status-${item.status}`;

    // 创建信息容器
    const infoDiv = element('div', 'my-request-info');
    infoDiv.append(
      element('div', 'my-request-name', item.reward_name),
      element('div', 'my-request-meta', `${item.points_cost} Gift Points · ${formatDate(item.requested_at)}`),
    );

    card.append(
      element('div', 'my-request-icon', item.reward_icon || '🎁'),
      infoDiv,
      element('span', `my-request-status ${statusClass}`, item.status),
    );
    list.append(card);
  });
}

// 加载"我的请求"列表
async function loadMyRequests() {
  if (!rewardState.studentId) return;
  try {
    const data = await jsonFetch(`/api/rewards?student_id=${encodeURIComponent(rewardState.studentId)}`);
    renderMyRequests(data.redemptions || []);
  } catch (error) {
    console.error('Failed to load my requests:', error);
  }
}

async function initialiseRewardPage() {
  // 孩子登录会话：直接使用已知的学生 ID，不需要调用 /api/account
  const kidStudentId = localStorage.getItem('kid_student_id');
  const kidSessionToken = localStorage.getItem('kid_session_token');
  const isKidSession = Boolean(kidStudentId && kidSessionToken);

  if (isKidSession) {
    rewardState.studentId = kidStudentId;
    // 孩子只能看自己的，隐藏选择器
    const picker = learnerSelect.closest('.learner-picker');
    if (picker) picker.style.display = 'none';

    // 隐藏家长专属区域（礼物审批、配送地址等）
    const parentZone = document.querySelector('.parent-zone');
    if (parentZone) parentZone.hidden = true;

    // 隐藏家长仪表盘入口
    const parentDashboardLink = document.getElementById('parent-dashboard-link');
    if (parentDashboardLink) parentDashboardLink.style.display = 'none';

    rewardContent.hidden = false;
    loginCard.hidden = true;
    await loadDashboard();
    await loadMyRequests();
    return;
  }

  try {
    const account = await jsonFetch('/api/account');
    rewardState.account = account;
    clearNode(learnerSelect);
    (account.students || []).filter((student) => student.is_active).forEach((student) => {
      const option = element('option', '', student.name || 'Learner');
      option.value = student.id;
      learnerSelect.append(option);
    });
    if (!learnerSelect.options.length) throw new Error('No learner profile was found.');
    rewardState.studentId = account.default_student_id || learnerSelect.value;
    const requested = new URLSearchParams(window.location.search).get('student_id');
    if (requested && Array.from(learnerSelect.options).some((item) => item.value === requested)) {
      rewardState.studentId = requested;
    }
    learnerSelect.value = rewardState.studentId;
    learnerSelect.addEventListener('change', async () => {
      rewardState.studentId = learnerSelect.value;
      const url = new URL(window.location.href);
      url.searchParams.set('student_id', rewardState.studentId);
      window.history.replaceState({}, '', url);
      await loadDashboard();
      await loadMyRequests();
    });

    rewardContent.hidden = false;
    loginCard.hidden = true;
    await loadDashboard();
    await loadMyRequests();
  } catch (error) {
    setMessage('');
    if (error.status === 401) {
      rewardContent.hidden = true;
      loginCard.hidden = false;
    } else {
      setMessage(error.message, 'error');
    }
  }
}

// 自定义礼物请求表单
const customRequestForm = document.getElementById('custom-request-form');
const customRequestStatus = document.getElementById('custom-request-status');

function showCustomRequestStatus(message, isError = false) {
  customRequestStatus.textContent = message;
  customRequestStatus.className = `custom-request-status show ${isError ? 'error' : 'success'}`;
  window.clearTimeout(showCustomRequestStatus.timer);
  showCustomRequestStatus.timer = window.setTimeout(() => {
    customRequestStatus.className = 'custom-request-status';
  }, 5000);
}

if (customRequestForm) {
  customRequestForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nameInput = document.getElementById('custom-reward-name');
    const iconInput = document.getElementById('custom-reward-icon');
    const costInput = document.getElementById('custom-reward-cost');

    const rewardName = nameInput.value.trim();
    const rewardIcon = iconInput ? (iconInput.value.trim() || '🎁') : '🎁';
    const xpCost = parseInt(costInput.value, 10);

    if (!rewardName) {
      showCustomRequestStatus('Please enter a gift name.', true);
      nameInput.focus();
      return;
    }
    if (!xpCost || xpCost < 10) {
      showCustomRequestStatus('Gift Points must be at least 10.', true);
      costInput.focus();
      return;
    }

    try {
      const data = await jsonFetch('/api/rewards/custom-request', {
        method: 'POST',
        body: JSON.stringify({
          student_id: rewardState.studentId,
          reward_name: rewardName,
          reward_icon: rewardIcon,
          xp_cost: xpCost,
        }),
      });
      showCustomRequestStatus(data.message || 'Your gift request has been sent!');
      customRequestForm.reset();
      // 刷新仪表盘以更新 Gift Points 显示
      await loadDashboard();
      // 刷新"我的请求"列表
      await loadMyRequests();
    } catch (error) {
      showCustomRequestStatus(error.message || 'Could not send request. Please try again.', true);
    }
  });
}

document.getElementById('reward-logout').addEventListener('click', async (event) => {
  event.preventDefault();
  // 根据登录类型选择不同的登出接口
  const isKid = Boolean(localStorage.getItem('kid_session_token'));
  const logoutUrl = isKid ? '/api/kid-logout' : '/api/logout';
  await fetch(logoutUrl, {method: 'POST', credentials: 'same-origin'});
  // 清除孩子登录信息
  localStorage.removeItem('kid_session_token');
  localStorage.removeItem('kid_student_id');
  localStorage.removeItem('kid_student_name');
  window.location.assign('/');
});

initialiseRewardPage();
