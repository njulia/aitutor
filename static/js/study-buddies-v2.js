'use strict';

(function initStudyBuddies() {
  const main = document.querySelector('main');
  if (!main) return;

  function loadHeaderScript(source) {
    if (document.querySelector(`script[src="${source}"]`)) return Promise.resolve();
    return new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = source;
      script.onload = script.onerror = () => resolve();
      document.head.append(script);
    });
  }

  function loadHeaderStyle(source) {
    if (document.querySelector(`link[href="${source}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = source;
    document.head.append(link);
  }

  function addProgressHeader() {
    if (document.querySelector('.header .header-content')) return;
    loadHeaderStyle('/static/css/theme.css?v=20260905-kid-header-1');
    loadHeaderStyle('/static/css/site-consistency.css?v=20260905-kid-header-1');

    const header = document.createElement('div');
    header.className = 'header';
    const content = element('div', undefined, 'header-content');
    const brand = element('a', undefined, 'logo');
    brand.href = '/';
    brand.setAttribute('aria-label', 'Homework Magic home');
    brand.append(element('span', '✨'), document.createTextNode(' Homework Magic'));
    const nav = element('nav', undefined, 'nav-links');
    nav.setAttribute('aria-label', 'Main navigation');
    [
      ['/ks1-homework', 'KS1'],
      ['/ks2-homework', 'KS2'],
      ['/elevenplus-practice', '11+'],
      ['/rewards', 'Rewards'],
      ['/parent-dashboard', 'Parent dashboard', 'parent-dashboard-link'],
      ['/login', 'Login', 'home-login-link'],
      ['/register', 'Register'],
      ['#', 'Logout', 'home-logout-link'],
    ].forEach(([href, label, id]) => {
      const link = element('a', label);
      link.href = href;
      if (id) link.id = id;
      nav.append(link);
    });
    content.append(brand, nav);
    header.append(content);
    main.before(header);

    // These are the same small header helpers used by Progress. They show a
    // signed-in child's character menu and hide grown-up-only links.
    [
      '/static/js/session-context.js?v=20260905-kid-header-1',
      '/static/js/avatar-data.js?v=20260905-kid-header-1',
      '/static/js/avatar-character.js?v=20260905-kid-header-1',
      '/static/js/avatar-pet.js?v=20260905-kid-header-1',
      '/static/js/auth-nav.js?v=20260905-kid-header-1',
    ].reduce(
      (ready, source) => ready.then(() => loadHeaderScript(source)),
      Promise.resolve(),
    );
  }

  addProgressHeader();
  document.body.classList.add('hm-app', 'study-buddies-page');
  main.classList.add('study-buddies-shell');

  main.innerHTML = `
    <header class="buddy-hero">
      <div><p class="buddy-kicker">✨ FRIENDS WHO LEARN TOGETHER</p><h1>Study Buddies</h1><p class="buddy-hero-copy">Cheer on a friend you know with learning challenges and kind emojis. There are no messages to type.</p></div>
      <div class="buddy-hero-friends" aria-hidden="true"><span>🐻</span><span>🌈</span><span>🦊</span><span>⭐</span></div>
    </header>
    <a class="buddy-back-to-app" href="/app">← Back to my learning</a>
    <div class="notice buddy-safety-note"><span aria-hidden="true">🛡️</span><div>Be kind, have fun and take turns. Buddies from different families need a grown-up from each family to say yes.</div></div>
    <div class="buddy-get-started">
      <section class="card buddy-code-card"><h2>✨ My Buddy Code</h2><p class="muted">Show this code to a grown-up before sharing it with a friend.</p><p class="buddy-code-display" id="my-buddy-code">Loading…</p></section>
      <section class="card buddy-find-card"><h2>Find a buddy</h2><label for="buddy-code">Friend's Buddy Code</label><div class="buddy-search-controls"><input id="buddy-code" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="20" pattern="[A-Za-z0-9]{1,10}[0-9]{4}" placeholder="e.g. ALEX4821"><button class="btn primary" type="button" id="buddy-search">Find my friend</button></div><p class="muted"><small>Ask a grown-up for the code. Do not type a name, email, address or school.</small></p><div id="buddy-results" class="status" role="status" aria-live="polite"></div></section>
    </div>
    <div class="grid buddy-list-grid">
      <section class="card"><h2>My buddies</h2><div id="buddy-list">Loading…</div></section>
    </div>
    <section class="card"><h2>🎯 Challenges</h2><p class="muted">Pick a ready-made learning challenge. When a buddy sends you one, tap Start challenge to begin.</p><div id="buddy-challenges">Loading…</div></section>
    <section class="card"><h2>💌 Kind emojis for you</h2><p class="muted">Little friendly signals from approved buddies. They disappear after a week.</p><div id="emoji-reactions">Loading…</div></section>
    <section class="card buddy-ranking-card"><h2>🏆 Buddy ranking</h2><p class="muted">Only you and approved buddies. This shows learning XP, not marks.</p><div class="buddy-ranking-columns"><section class="buddy-ranking-panel" aria-labelledby="weekly-ranking-title"><h3 id="weekly-ranking-title">This week</h3><div id="weekly-ranking">Loading…</div></section><section class="buddy-ranking-panel" aria-labelledby="all-time-ranking-title"><h3 id="all-time-ranking-title">All time</h3><div id="ranking">Loading…</div></section></div></section>`;

  const defaultChallengeTypes = [
    {key: 'maths', label: '➗ Maths', subject: 'Maths', practice_tab: 'homework', group: 'primary'},
    {key: 'english', label: '📖 English', subject: 'English', practice_tab: 'homework', group: 'primary'},
    {key: 'eleven_plus_maths', label: '➕ 11+ Maths', subject: 'Maths', practice_tab: 'eleven', group: 'eleven_plus'},
    {key: 'eleven_plus_english', label: '📚 11+ English', subject: 'English', practice_tab: 'eleven', group: 'eleven_plus'},
    {key: 'verbal_reasoning', label: '🗣️ 11+ Verbal Reasoning', subject: 'Verbal Reasoning', practice_tab: 'eleven', group: 'eleven_plus'},
    {key: 'non_verbal_reasoning', label: '🧩 11+ Non-Verbal Reasoning', subject: 'Non-Verbal Reasoning', practice_tab: 'eleven', group: 'eleven_plus'},
  ];
  const primarySubjectsByKey = Object.freeze({
    maths: 'Maths', math: 'Maths', mathematics: 'Maths',
    english: 'English', science: 'Science', history: 'History', geography: 'Geography',
    designandtechnology: 'Design and Technology', designtechnology: 'Design and Technology', dt: 'Design and Technology',
    artanddesign: 'Art and Design', artdesign: 'Art and Design', art: 'Art and Design', computing: 'Computing',
    music: 'Music', physicaleducation: 'Physical Education', pe: 'Physical Education',
    religiouseducation: 'Religious Education', re: 'Religious Education', pshe: 'PSHE',
    french: 'French', german: 'German', spanish: 'Spanish', italian: 'Italian',
    polish: 'Polish', arabic: 'Arabic', latin: 'Latin', chinese: 'Chinese',
  });
  const elevenPlusSubjectsByKey = Object.freeze({
    reasoning: 'Verbal Reasoning', verbalreasoning: 'Verbal Reasoning',
    nonverbalreasoning: 'Non-Verbal Reasoning', elevenplus: 'Maths', '11plus': 'Maths',
    elevenplusmaths: 'Maths', '11plusmaths': 'Maths',
    elevenplusenglish: 'English', '11plusenglish': 'English',
    elevenplusverbalreasoning: 'Verbal Reasoning', '11plusverbalreasoning': 'Verbal Reasoning',
    elevenplusnonverbalreasoning: 'Non-Verbal Reasoning', '11plusnonverbalreasoning': 'Non-Verbal Reasoning',
  });
  let state = {buddies: [], emoji_options: [], student_id: ''};
  const byId = (id) => document.getElementById(id);

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {'Accept': 'application/json', 'Content-Type': 'application/json', ...(options.headers || {})},
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || 'Something went wrong.');
    return data;
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function actionButton(text, onClick, className, label) {
    const button = element('button', text, className || 'btn');
    button.type = 'button';
    if (label) button.setAttribute('aria-label', label);
    button.addEventListener('click', onClick);
    return button;
  }

  function normaliseChallengeKey(value) {
    return String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  function isElevenPlusTab(value) {
    return ['eleven', 'elevenplus', '11plus', '11'].includes(normaliseChallengeKey(value));
  }

  function normaliseChallengeOption(value, fallbackKey = '') {
    if (!value || typeof value !== 'object') return null;
    const key = String(value.key || value.challenge_type || fallbackKey || '').trim();
    if (!key) return null;
    const label = String(value.label || value.title || key).trim();
    return {
      key,
      label: label || key,
      subject: String(value.practice_subject || value.subject || '').trim(),
      practice_tab: String(value.practice_tab || value.tab || '').trim(),
      group: String(value.group || '').trim(),
    };
  }

  function availableChallengeTypes() {
    const supplied = state.challenge_options || state.challenge_types || state.challenge_catalog;
    let options = [];
    if (Array.isArray(supplied)) {
      options = supplied.map((item) => normaliseChallengeOption(item)).filter(Boolean);
    } else if (supplied && typeof supplied === 'object') {
      options = Object.entries(supplied)
        .map(([key, item]) => normaliseChallengeOption(item, key))
        .filter(Boolean);
    }
    return options.length ? options : defaultChallengeTypes;
  }

  function practiceDestinationFor(challenge) {
    const metadataTab = String(challenge.practice_tab || challenge.tab || '').trim();
    const candidates = [
      challenge.practice_subject,
      challenge.subject,
      challenge.challenge_subject,
      challenge.challenge_type,
    ];
    let subject = '';
    let tab = isElevenPlusTab(metadataTab) ? 'eleven' : metadataTab === 'homework' ? 'homework' : '';
    for (const candidate of candidates) {
      const key = normaliseChallengeKey(candidate);
      if (!key) continue;
      if (elevenPlusSubjectsByKey[key]) {
        subject = elevenPlusSubjectsByKey[key];
        tab = tab || 'eleven';
        break;
      }
      if (primarySubjectsByKey[key]) {
        subject = primarySubjectsByKey[key];
        tab = tab || 'homework';
        break;
      }
    }
    if (!tab) {
      // A mixed challenge can be completed in any supported primary subject.
      tab = 'homework';
    }
    const requestedYear = Number(challenge.target_year_group || challenge.year_group);
    const validYear = tab === 'eleven'
      ? [3, 4, 5, 6].includes(requestedYear)
      : [1, 2, 3, 4, 5, 6].includes(requestedYear);
    const subjectQuery = subject ? `&subject=${encodeURIComponent(subject)}` : '';
    const yearQuery = validYear ? `&year=${encodeURIComponent(requestedYear)}` : '';
    const challengeId = String(challenge.id || '').trim();
    const challengeQuery = challengeId ? `&buddy_challenge=${encodeURIComponent(challengeId)}` : '';
    return {
      href: `/app?tab=${encodeURIComponent(tab)}${subjectQuery}${yearQuery}${challengeQuery}`,
      label: subject ? `Start ${validYear ? `Year ${requestedYear} ` : ''}${tab === 'eleven' ? '11+ ' : ''}${subject}` : 'Choose an activity',
      subject,
      yearGroup: validYear ? requestedYear : null,
    };
  }

  function challengePracticeLink(challenge) {
    const destination = practiceDestinationFor(challenge);
    const link = element('a', `▶ ${destination.label}`, 'btn primary buddy-challenge-start');
    link.href = destination.href;
    link.setAttribute('aria-label', `Start ${challenge.title || 'this challenge'}${destination.subject ? ` with ${destination.subject}` : ''}`);
    return link;
  }

  function showEmpty(container, text) {
    container.replaceChildren(element('p', text, 'muted'));
  }

  function showKidSignInPrompt(parentSignedIn) {
    main.replaceChildren();
    const card = element('section', undefined, 'card buddy-kid-sign-in');
    const heading = parentSignedIn ? 'A child needs to sign in with their code' : 'Sign in as a child';
    const copy = parentSignedIn
      ? 'Study Buddies is part of a child’s learning space. Your child signs in with their own Child login code, not your parent email or password.'
      : 'Study Buddies is part of a child’s learning space. Please sign in with a child login code.';
    card.append(element('span', '🧒', 'buddy-kid-sign-in-icon'), element('h1', heading), element('p', copy, 'muted'));
    const actions = element('div', undefined, 'buddy-kid-sign-in-actions');
    if (parentSignedIn) {
      const guide = element('div', undefined, 'buddy-kid-sign-in-guide');
      guide.append(
        element('strong', 'Sign in as your child'),
        element('p', '1. Click Open Parent Dashboard below. 2. On your child’s card, click “Open child sign-in” next to their Child login code. 3. The code will be ready on the next page, so your child only needs to tap Start Learning.'),
        element('p', 'Child sign-in switches this browser to your child’s learning space.', 'buddy-kid-sign-in-note'),
      );
      card.append(guide);
      const dashboard = element('a', 'Open Parent Dashboard', 'btn');
      dashboard.href = '/parent-dashboard#family-title';
      actions.append(dashboard);
    }
    const signIn = element('a', 'Sign in as a child', 'btn primary');
    signIn.href = '/kid-login?next=/study-buddies';
    actions.append(signIn);
    card.append(actions);
    main.append(card);
  }

  async function hasKidSession() {
    try {
      const response = await fetch('/api/session-context', {
        credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'},
      });
      const session = await response.json().catch(() => ({}));
      if (response.ok && session.authenticated && session.role === 'kid') return true;
      showKidSignInPrompt(Boolean(session.authenticated && (session.role === 'parent' || session.role === 'teacher')));
    } catch (_) {
      showKidSignInPrompt(false);
    }
    return false;
  }

  function renderBuddies() {
    const container = byId('buddy-list');
    container.replaceChildren();
    if (!state.buddies.length) return showEmpty(container, 'No approved buddies yet.');
    state.buddies.forEach((buddy) => {
      const card = element('article', undefined, 'buddy');
      const details = element('div');
      details.append(element('strong', `👤 ${buddy.nickname}`), element('small', `Year ${buddy.year_group}`));
      const actionArea = element('div', undefined, 'buddy-action-area');
      const actions = element('div', undefined, 'buddy-actions');
      actions.append(actionButton('Challenge', () => showChallengePicker(buddy.student_id, actionArea), 'btn primary', `Send a learning challenge to ${buddy.nickname}`));
      const emojiActions = element('div', undefined, 'buddy-emoji-actions');
      state.emoji_options.forEach((option) => {
        const emojiButton = actionButton(option.emoji, () => sendEmoji(buddy.student_id, option.key, emojiButton), 'btn', `Send ${option.label} to ${buddy.nickname}`);
        emojiActions.append(emojiButton);
      });
      actions.append(emojiActions);
      actionArea.append(actions);
      card.append(details, actionArea);
      container.append(card);
    });
  }

  function renderReactions(reactions) {
    const container = byId('emoji-reactions');
    container.replaceChildren();
    if (!reactions.length) return showEmpty(container, 'No kind emojis yet.');
    reactions.forEach((reaction) => {
      const row = element('div', undefined, 'buddy-reaction');
      row.append(element('span', reaction.emoji, 'buddy-reaction-emoji'), element('span', `${reaction.sender_nickname} sent you a ${reaction.label.toLowerCase()}.`));
      container.append(row);
    });
  }

  function renderChallenges(challenges) {
    const container = byId('buddy-challenges');
    container.replaceChildren();
    if (!challenges.length) return showEmpty(container, 'No challenges yet.');
    challenges.forEach((challenge) => {
      const card = element('article', undefined, 'buddy buddy-challenge-row');
      const sentByMe = challenge.requester_student_id === state.student_id;
      const direction = sentByMe
        ? `You sent this to ${challenge.target_nickname || 'your buddy'}.`
        : `${challenge.requester_nickname || 'A buddy'} sent this to you.`;
      card.append(
        element('strong', `🎯 ${challenge.title}`),
        element('span', direction, 'challenge-direction'),
        element('span', `${challenge.target_count} activity · you both earn +${challenge.xp_reward} XP and +${challenge.gift_points_reward} Gift Points`, 'challenge-progress'),
      );
      if (challenge.status === 'open' && challenge.target_student_id === state.student_id) {
        const actions = element('div', undefined, 'buddy-challenge-actions');
        actions.append(challengePracticeLink(challenge));
        if (challenge.ready_to_complete) actions.append(actionButton('Claim reward', () => completeChallenge(challenge.id), 'btn primary'));
        else actions.append(element('span', `Your turn — ${challenge.remaining_activity_count} more to go.`, 'challenge-status'));
        card.append(actions);
      } else if (challenge.status === 'open') {
        card.append(element('span', `Waiting for ${challenge.target_nickname || 'your buddy'}.`, 'challenge-status'));
      } else card.append(element('span', `Completed 🎉 You both earned +${challenge.xp_reward} XP and +${challenge.gift_points_reward} Gift Points.`, 'challenge-status'));
      container.append(card);
    });
  }

  function renderRanking(items, id) {
    const container = byId(id);
    container.replaceChildren();
    if (!items.length) return showEmpty(container, 'Add a buddy to start your ranking.');
    items.forEach((item) => {
      const isCurrentLearner = Boolean(
        item.is_current_learner || item.student_id === state.student_id
      );
      const row = element('article', undefined, 'buddy buddy-ranking-row');
      if (isCurrentLearner) row.classList.add('is-current-learner');

      const details = element('div', undefined, 'buddy-ranking-details');
      const nameLine = element('div', undefined, 'buddy-ranking-name-line');
      nameLine.append(
        element('span', `#${item.rank}${item.rank === 1 ? ' 🏆' : ''}`, 'buddy-ranking-place'),
        element('strong', item.nickname || 'Learner'),
      );
      if (isCurrentLearner) {
        nameLine.append(element('span', 'Me', 'buddy-ranking-me-label'));
      }

      const badgeRow = element('div', undefined, 'buddy-ranking-badges');
      (Array.isArray(item.badges) ? item.badges : []).forEach((badge) => {
        const badgeName = String(badge.title || 'Badge');
        const chip = element('span', badge.icon || '🏅', 'buddy-ranking-badge');
        chip.title = badge.description ? `${badgeName}: ${badge.description}` : badgeName;
        chip.setAttribute('aria-label', badgeName);
        badgeRow.append(chip);
      });
      details.append(nameLine);
      if (badgeRow.childElementCount) details.append(badgeRow);
      row.append(details, element('strong', `${item.xp || 0} XP`, 'buddy-ranking-xp'));
      container.append(row);
    });
  }

  function animateSentEmoji(sourceButton, emoji) {
    if (!sourceButton) return;
    const source = sourceButton.getBoundingClientRect();
    const buddyLabel = sourceButton.closest('.buddy')?.querySelector('strong');
    const target = buddyLabel?.getBoundingClientRect();
    const flight = element('span', emoji, 'buddy-emoji-flight');
    const x = target ? target.left + (target.width / 2) - (source.left + (source.width / 2)) : 110;
    const y = target ? target.top + (target.height / 2) - (source.top + (source.height / 2)) : -115;
    flight.setAttribute('aria-hidden', 'true');
    flight.style.setProperty('--emoji-flight-x', `${Math.max(-180, Math.min(180, x))}px`);
    flight.style.setProperty('--emoji-flight-y', `${Math.max(-150, Math.min(-70, y))}px`);
    flight.style.left = `${source.left + (source.width / 2)}px`;
    flight.style.top = `${source.top + (source.height / 2)}px`;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) flight.classList.add('buddy-emoji-flight-reduced');
    document.body.append(flight);
    window.setTimeout(() => flight.remove(), 950);
  }

  async function sendEmoji(studentId, emoji, sourceButton) {
    if (sourceButton) {
      sourceButton.disabled = true;
      sourceButton.classList.add('is-sending');
    }
    try {
      await api('/api/study-buddies/emoji', {method: 'POST', body: JSON.stringify({target_student_id: studentId, emoji})});
      animateSentEmoji(sourceButton, emoji);
      const sent = element('span', 'Sent!', 'buddy-emoji-sent');
      sent.setAttribute('role', 'status');
      sourceButton?.after(sent);
      window.setTimeout(load, 650);
    } catch (error) {
      sourceButton?.classList.remove('is-sending');
      if (sourceButton) sourceButton.disabled = false;
      window.alert(error.message);
    }
  }

  function showChallengePicker(studentId, actionArea) {
    const old = byId('challenge-picker');
    if (old) old.remove();
    const picker = element('div', undefined, 'challenge-picker');
    picker.id = 'challenge-picker';
    picker.setAttribute('role', 'group');
    picker.setAttribute('aria-label', 'Choose a challenge');
    picker.append(element('span', 'Choose a challenge', 'challenge-picker-label'));
    const options = availableChallengeTypes();
    const groups = [
      ['primary', 'Homework subjects'],
      ['eleven_plus', '11+ subjects'],
    ];
    groups.forEach(([groupKey, heading]) => {
      const groupOptions = options.filter((challenge) => (challenge.group || 'primary') === groupKey);
      if (!groupOptions.length) return;
      const group = element('div', undefined, 'challenge-picker-group');
      group.append(element('strong', heading, 'challenge-picker-heading'));
      groupOptions.forEach((challenge) => {
        const button = actionButton(challenge.label, () => sendChallenge(studentId, challenge.key));
        button.dataset.challengeType = challenge.key;
        group.append(button);
      });
      picker.append(group);
    });
    actionArea.append(picker);
  }

  async function sendChallenge(studentId, type) {
    try { await api('/api/study-buddies/challenge', {method: 'POST', body: JSON.stringify({target_student_id: studentId, challenge_type: type})}); window.alert('Challenge sent!'); load(); }
    catch (error) { window.alert(error.message); }
  }

  function showCompletionDialog(notification, {sentByBuddy = false} = {}) {
    if (document.querySelector('.buddy-completion-dialog-backdrop')) return;
    const backdrop = element('div', undefined, 'buddy-completion-dialog-backdrop');
    const dialog = element('section', undefined, 'buddy-completion-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'buddy-completion-title');
    const title = sentByBuddy
      ? `🎉 ${notification.buddy_nickname || 'Your buddy'} finished a challenge!`
      : '🎉 Challenge completed!';
    dialog.append(
      element('span', '🏆', 'buddy-completion-dialog-icon'),
      element('h2', title),
      element('p', sentByBuddy
        ? `You both earned a reward for “${notification.title}”.`
        : 'Amazing learning — your buddy gets the same reward too.'),
      element('strong', `+${notification.awarded_xp || 0} XP and +${notification.awarded_gift_points || 0} Gift Points each`, 'buddy-completion-dialog-reward'),
    );
    const close = actionButton('Hooray!', async () => {
      close.disabled = true;
      if (sentByBuddy && notification.id) {
        try { await api(`/api/study-buddies/challenge-notifications/${encodeURIComponent(notification.id)}/seen`, {method: 'POST'}); }
        catch (_) { /* The celebration can still safely close. */ }
      }
      backdrop.remove();
      if (sentByBuddy) load();
    }, 'btn primary');
    dialog.append(close);
    backdrop.append(dialog);
    document.body.append(backdrop);
    close.focus();
  }

  async function completeChallenge(id) {
    try {
      const completed = await api(`/api/study-buddies/challenge/${encodeURIComponent(id)}/complete`, {method: 'POST'});
      showCompletionDialog({
        title: completed.title,
        awarded_xp: completed.reward?.awarded_xp,
        awarded_gift_points: completed.reward?.awarded_gift_points,
      });
      load();
    }
    catch (error) { window.alert(error.message); }
  }

  function renderSearchResult(student) {
    const results = byId('buddy-results');
    const card = element('div', undefined, 'buddy');
    card.append(element('strong', `👤 ${student.nickname}`), actionButton('Send buddy request', () => requestBuddy(student.student_id), 'btn primary', `Send a buddy request to ${student.nickname}`));
    results.replaceChildren(card);
  }

  async function searchBuddy() {
    const input = byId('buddy-code');
    const code = input.value.trim().toUpperCase();
    const results = byId('buddy-results');
    if (!/^[A-Z0-9]{1,10}\d{4}$/.test(code)) { results.textContent = 'Please type the Buddy Code like ALEX4821.'; input.focus(); return; }
    try { const data = await api('/api/study-buddies/search', {method: 'POST', body: JSON.stringify({query: code})}); data.students?.length ? renderSearchResult(data.students[0]) : results.textContent = 'No buddy found. Ask a grown-up to check the Buddy Code.'; }
    catch (error) { results.textContent = error.message; }
  }

  async function requestBuddy(studentId) {
    try {
      const request = await api('/api/study-buddies/request', {method: 'POST', body: JSON.stringify({target_student_id: studentId})});
      byId('buddy-results').textContent = request.status === 'active'
        ? 'You are Study Buddies now! 🎉'
        : 'Request sent! Both families need to say yes.';
      load();
    }
    catch (error) { byId('buddy-results').textContent = error.message; }
  }

  async function load() {
    try {
      const data = await api('/api/study-buddies');
      state = data;
      byId('my-buddy-code').textContent = data.buddy_code || 'Ask a grown-up for help.';
      renderBuddies(); renderReactions(data.emoji_reactions || []); renderChallenges(data.challenges || []);
      renderRanking(data.ranking?.weekly || [], 'weekly-ranking'); renderRanking(data.ranking?.all_time || [], 'ranking');
      const [notice] = Array.isArray(data.buddy_completion_notifications) ? data.buddy_completion_notifications : [];
      if (notice) showCompletionDialog(notice, {sentByBuddy: true});
    } catch (error) { showEmpty(byId('buddy-list'), error.message); }
  }

  async function initialise() {
    if (!await hasKidSession()) return;
    byId('buddy-search').addEventListener('click', searchBuddy);
    byId('buddy-code').addEventListener('keydown', (event) => { if (event.key === 'Enter') searchBuddy(); });
    load();
  }

  initialise();
}());
