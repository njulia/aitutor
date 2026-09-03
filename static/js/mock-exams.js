// 兼容旧版 iPad 上 Safari 12 缺失的 DOM 便捷方法，使用 ES5 语法以便先于页面逻辑运行。
(function installLegacySafariCompatibility() {
  function defineMethod(prototype, name, implementation) {
    if (!prototype || prototype[name]) return;
    try {
      Object.defineProperty(prototype, name, {
        configurable: true,
        writable: true,
        value: implementation
      });
    } catch (error) {
      prototype[name] = implementation;
    }
  }

  if (typeof NodeList !== 'undefined') {
    defineMethod(NodeList.prototype, 'forEach', function (callback, thisArg) {
      return Array.prototype.forEach.call(this, callback, thisArg);
    });
  }

  if (typeof Element !== 'undefined') {
    defineMethod(Element.prototype, 'replaceChildren', function () {
      while (this.firstChild) {
        this.removeChild(this.firstChild);
      }
      for (var index = 0; index < arguments.length; index += 1) {
        var child = arguments[index];
        this.appendChild(
          child && typeof child.nodeType === 'number'
            ? child
            : document.createTextNode(String(child))
        );
      }
    });
  }
}());

(function () {
  'use strict';

  const catalogueView = document.getElementById('catalogue-view');
  const examView = document.getElementById('exam-view');
  const resultsView = document.getElementById('results-view');
  const catalogueStatus = document.getElementById('catalogue-status');
  const commonGrid = document.getElementById('common-grid');
  const schoolGrid = document.getElementById('school-grid');
  const examTitle = document.getElementById('exam-title');
  const examSubtitle = document.getElementById('exam-subtitle');
  const examTimer = document.getElementById('exam-timer');
  const examClock = examTimer.closest('.exam-clock');
  const examProgressText = document.getElementById('exam-progress-text');
  const examProgressBar = document.getElementById('exam-progress-bar');
  const examAnsweredText = document.getElementById('exam-answered-text');
  const questionNumber = document.getElementById('question-number');
  const questionSubject = document.getElementById('question-subject');
  const questionContext = document.getElementById('question-context');
  const questionPrompt = document.getElementById('question-prompt');
  const answerOptions = document.getElementById('answer-options');
  const previousButton = document.getElementById('previous-question');
  const nextButton = document.getElementById('next-question');
  const finishButton = document.getElementById('finish-exam');
  const examStatus = document.getElementById('exam-status');
  const backToMocks = document.getElementById('back-to-mocks');

  const state = {
    catalogue: null,
    exam: null,
    questions: [],
    questionById: new Map(),
    currentIndex: 0,
    answers: {},
    attemptToken: '',
    deadline: 0,
    timerId: null,
    active: false,
    submitting: false,
    autoSubmitted: false
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function setStatus(node, message, isError) {
    node.textContent = message || '';
    node.classList.toggle('error', Boolean(isError));
  }

  function formatMarkdown(text) {
    const container = document.createElement('div');
    const lines = String(text || '').split(/\r?\n/);
    lines.forEach(function (line) {
      const paragraph = document.createElement('p');
      const clean = line.replace(/^#{1,6}\s*/, '').trim();
      if (!clean) return;
      const parts = clean.split(/(\*\*[^*]+\*\*)/g);
      parts.forEach(function (part) {
        if (/^\*\*[^*]+\*\*$/.test(part)) {
          const strong = document.createElement('strong');
          strong.textContent = part.slice(2, -2);
          paragraph.appendChild(strong);
        } else {
          paragraph.appendChild(document.createTextNode(part));
        }
      });
      container.appendChild(paragraph);
    });
    return container.innerHTML;
  }

  async function readJson(response) {
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const error = new Error(data.detail || data.error || 'The mock request did not work.');
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function safeSourceLink(source) {
    try {
      const url = new URL(source.url);
      if (url.protocol !== 'https:') return null;
      const link = element('a', '', source.title);
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      return link;
    } catch (_) {
      return null;
    }
  }

  function subjectSummary(subjectCounts) {
    return Object.keys(subjectCounts || {}).map(function (subject) {
      return subject + ' ' + subjectCounts[subject];
    }).join(' · ');
  }

  function renderMockCard(exam) {
    const card = element('article', 'mock-card');
    if (exam.is_free) card.classList.add('free');
    if (!exam.available) card.classList.add('locked');

    const top = element('div', 'mock-card-top');
    let badgeText = '11+ Premium';
    let badgeClass = '';
    if (exam.is_free) {
      badgeText = 'Free';
      badgeClass = ' free';
    } else if (!exam.available) {
      badgeClass = ' locked';
    }
    top.appendChild(element('span', 'mock-badge' + badgeClass, badgeText));
    top.appendChild(element('span', 'mock-badge', exam.stage));
    card.appendChild(top);

    card.appendChild(element('h3', '', exam.title));
    if (exam.school) card.appendChild(element('p', 'school-name', exam.school));
    card.appendChild(element('p', 'description', exam.description));

    const facts = element('div', 'mock-facts');
    facts.appendChild(element('span', '', exam.duration_minutes + ' minutes'));
    facts.appendChild(element('span', '', exam.question_count + ' questions'));
    card.appendChild(facts);
    card.appendChild(element('p', 'subject-list', subjectSummary(exam.subject_counts)));
    card.appendChild(element('p', 'format-note', exam.format_note));

    if (!exam.is_free) {
      card.appendChild(element(
        'p',
        'mock-access-note' + (exam.available ? ' available' : ''),
        exam.available
          ? 'Included with your active 11+ Premium subscription.'
          : 'Requires an active 11+ Premium subscription.'
      ));
    }

    const button = element('button', 'mock-button ' + (exam.available ? 'primary' : 'secondary'));
    button.type = 'button';
    if (exam.is_free) {
      button.textContent = 'Start free diagnostic';
    } else if (exam.available) {
      button.textContent = 'Start 11+ Premium mock';
    } else {
      button.textContent = 'Get 11+ Premium';
    }
    button.addEventListener('click', function () {
      if (!exam.available) {
        window.location.assign('/pricing');
        return;
      }
      startExam(exam.id, button);
    });
    card.appendChild(button);

    if (Array.isArray(exam.sources) && exam.sources.length) {
      const details = element('details', 'source-details');
      details.appendChild(element('summary', '', 'Public format sources'));
      const list = element('ul');
      exam.sources.forEach(function (source) {
        const link = safeSourceLink(source);
        if (!link) return;
        const item = element('li');
        item.appendChild(link);
        list.appendChild(item);
      });
      details.appendChild(list);
      card.appendChild(details);
    }
    return card;
  }

  function mockArea(exam) {
    const text = [exam.school, exam.title, exam.description].filter(Boolean).join(' ').toLowerCase();
    if (/essex|csse|colchester|southend|westcliff|chelmsford|cchs/.test(text)) return 'essex';
    if (/london|barnet|bexley|sutton|tiffin|wilson|st olave|newstead|henrietta barnett|north london|city of london|highgate|wimbledon|putney|habs/.test(text)) return 'london';
    if (/kent|medway|reading|berkshire|buckinghamshire|oxfordshire|surrey|sussex|brighton/.test(text)) return 'south-east';
    if (/bristol|devon|cornwall|somerset|gloucester/.test(text)) return 'south-west';
    if (/birmingham|warwick|warwickshire|nottingham|derby|leicester|lincoln|stafford/.test(text)) return 'midlands';
    if (/manchester|cheshire|lancashire|liverpool|cumbria|altrincham/.test(text)) return 'north-west';
    if (/york|yorkshire|newcastle|durham|sunderland|tees/.test(text)) return 'north-east';
    return 'other';
  }

  function mockMatches(exam, search, region, type) {
    if (type !== 'all' && exam.category !== type) return false;
    if (region !== 'all' && mockArea(exam) !== region) return false;
    if (!search) return true;
    const haystack = [exam.title, exam.school, exam.description, exam.stage, exam.format_note]
      .filter(Boolean).join(' ').toLowerCase();
    return search.split(/\s+/).every(function (term) { return haystack.indexOf(term) !== -1; });
  }

  function applyMockFilters() {
    if (!state.catalogue) return;
    const searchInput = document.getElementById('mock-search');
    const regionInput = document.getElementById('mock-region');
    const typeInput = document.getElementById('mock-type');
    const search = String(searchInput ? searchInput.value : '').trim().toLowerCase();
    const region = regionInput ? regionInput.value : 'all';
    const type = typeInput ? typeInput.value : 'all';
    commonGrid.replaceChildren();
    schoolGrid.replaceChildren();
    const exams = (state.catalogue.exams || []).filter(function (exam) {
      return mockMatches(exam, search, region, type);
    });
    exams.sort(function (a, b) {
      if (a.category === 'school_target' && b.category === 'school_target') {
        const nameA = String(a.school || a.title || '').toLowerCase();
        const nameB = String(b.school || b.title || '').toLowerCase();
        return nameA < nameB ? -1 : (nameA > nameB ? 1 : 0);
      }
      return 0;
    });
    exams.forEach(function (exam) {
      const target = exam.category === 'school_target' ? schoolGrid : commonGrid;
      target.appendChild(renderMockCard(exam));
    });
    const status = document.getElementById('mock-filter-status');
    if (status) {
      status.textContent = search || region !== 'all' || type !== 'all'
        ? exams.length + ' mock' + (exams.length === 1 ? '' : 's') + ' found.'
        : '';
    }
    document.getElementById('common-mocks').hidden = !exams.some(function (exam) { return exam.category === 'common'; });
    document.getElementById('school-mocks').hidden = !exams.some(function (exam) { return exam.category === 'school_target'; });
  }

  function renderCatalogue(data) {
    state.catalogue = data;
    applyMockFilters();
    setStatus(
      catalogueStatus,
      'Common 11+ Diagnostic is free. Every other mock requires 11+ Premium.',
      false
    );
  }

  async function loadCatalogue() {
    setStatus(catalogueStatus, 'Loading the mock room…', false);
    try {
      const response = await fetch('/api/elevenplus/mock-exams', {
        credentials: 'same-origin',
        headers: {'Accept': 'application/json'}
      });
      state.catalogue = await readJson(response);
      renderCatalogue(state.catalogue);
    } catch (error) {
      commonGrid.replaceChildren();
      schoolGrid.replaceChildren();
      setStatus(
        catalogueStatus,
        error.message || 'The mock room is taking a break. Please refresh and try again.',
        true
      );
    }
  }

  function resetAttemptState() {
    if (state.timerId) window.clearInterval(state.timerId);
    state.exam = null;
    state.questions = [];
    state.questionById = new Map();
    state.currentIndex = 0;
    state.answers = {};
    state.attemptToken = '';
    state.deadline = 0;
    state.timerId = null;
    state.active = false;
    state.submitting = false;
    state.autoSubmitted = false;
  }

  async function startExam(examId, button) {
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'Opening mock…';
    setStatus(catalogueStatus, '', false);
    try {
      const response = await fetch(
        '/api/elevenplus/mock-exams/' + encodeURIComponent(examId) + '/start',
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Accept': 'application/json'}
        }
      );
      const data = await readJson(response);
      resetAttemptState();
      state.exam = data.exam;
      state.questions = data.questions || [];
      state.questionById = new Map(state.questions.map(function (question) {
        return [question.id, question];
      }));
      state.attemptToken = data.attempt.token;
      state.deadline = Number(data.attempt.deadline);
      state.active = true;

      catalogueView.hidden = true;
      resultsView.hidden = true;
      examView.hidden = false;
      examTitle.textContent = state.exam.title;
      examSubtitle.textContent = state.exam.school
        ? state.exam.school + ' · ' + state.exam.stage
        : state.exam.stage;
      renderQuestion();
      updateTimer();
      state.timerId = window.setInterval(updateTimer, 1000);
      window.scrollTo({top: 0, behavior: 'smooth'});
      window.setTimeout(function () {
        const selected = answerOptions.querySelector('input');
        if (selected) selected.focus();
      }, 250);
    } catch (error) {
      button.disabled = false;
      button.textContent = originalLabel;
      if (error.status === 401 || error.status === 402) {
        setStatus(
          catalogueStatus,
          'A parent or guardian can unlock this mock from the plans page.',
          true
        );
        return;
      }
      setStatus(
        catalogueStatus,
        error.message || 'We could not start this mock just now. Please try again.',
        true
      );
    }
  }

  function selectedCount() {
    return Object.keys(state.answers).length;
  }

  function renderQuestion() {
    if (!state.questions.length) return;
    const question = state.questions[state.currentIndex];
    const total = state.questions.length;
    const answered = selectedCount();

    questionNumber.textContent = 'Question ' + (state.currentIndex + 1) + ' of ' + total;
    questionSubject.textContent = question.subject + ' · ' + question.topic;
    questionPrompt.textContent = question.prompt;
    questionContext.textContent = question.context || '';
    questionContext.hidden = !question.context;
    answerOptions.replaceChildren();

    (question.options || []).forEach(function (option) {
      const label = element('label', 'answer-option');
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'mock-answer-' + question.id;
      input.value = option.label;
      input.checked = state.answers[question.id] === option.label;
      input.addEventListener('change', function () {
        state.answers[question.id] = option.label;
        updateProgress();
      });
      const body = element('span', 'answer-option-body');
      body.appendChild(element('span', 'answer-letter', option.label));
      body.appendChild(element('span', 'answer-text', option.text));
      body.appendChild(element('span', 'answer-tick', '✓'));
      label.appendChild(input);
      label.appendChild(body);
      answerOptions.appendChild(label);
    });

    previousButton.disabled = state.currentIndex === 0;
    nextButton.textContent = state.currentIndex === total - 1 ? 'Finish →' : 'Next →';
    examProgressText.textContent = 'Question ' + (state.currentIndex + 1) + ' of ' + total;
    examAnsweredText.textContent = answered + ' answered';
    updateProgress();
    document.title = 'Question ' + (state.currentIndex + 1) + ' | ' + state.exam.title;
  }

  function updateProgress() {
    const answered = selectedCount();
    const total = state.questions.length || 1;
    examProgressBar.style.width = Math.round((answered / total) * 100) + '%';
    examAnsweredText.textContent = answered + ' answered';
  }

  function moveQuestion(offset) {
    const target = state.currentIndex + offset;
    if (target < 0 || target >= state.questions.length) return;
    state.currentIndex = target;
    renderQuestion();
    document.getElementById('question-card').focus({preventScroll: true});
    window.scrollTo({top: 100, behavior: 'smooth'});
  }

  function formatTime(seconds) {
    const safe = Math.max(0, seconds);
    const minutes = Math.floor(safe / 60);
    const remainder = safe % 60;
    return String(minutes).padStart(2, '0') + ':' + String(remainder).padStart(2, '0');
  }

  function updateTimer() {
    if (!state.active || !state.deadline) return;
    const remaining = Math.max(0, state.deadline - Math.floor(Date.now() / 1000));
    examTimer.textContent = formatTime(remaining);
    examClock.classList.toggle('warning', remaining <= 300 && remaining > 60);
    examClock.classList.toggle('urgent', remaining <= 60);
    if (remaining === 0 && !state.autoSubmitted) {
      state.autoSubmitted = true;
      if (state.timerId) window.clearInterval(state.timerId);
      setStatus(examStatus, 'Time is up. Marking the answers you completed…', false);
      submitExam(true);
    }
  }

  function setExamButtonsDisabled(disabled) {
    previousButton.disabled = disabled || state.currentIndex === 0;
    nextButton.disabled = disabled;
    finishButton.disabled = disabled;
    answerOptions.querySelectorAll('input').forEach(function (input) {
      input.disabled = disabled;
    });
  }

  async function submitExam(timedOut) {
    if (state.submitting || !state.active) return;
    const unanswered = state.questions.length - selectedCount();
    if (!timedOut && unanswered > 0) {
      const wording = unanswered === 1 ? '1 question is' : unanswered + ' questions are';
      if (!window.confirm(wording + ' unanswered. Finish and mark the mock now?')) return;
    }

    state.submitting = true;
    setExamButtonsDisabled(true);
    setStatus(examStatus, 'Marking your mock…', false);
    try {
      const response = await fetch(
        '/api/elevenplus/mock-exams/' + encodeURIComponent(state.exam.id) + '/submit',
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            attempt_token: state.attemptToken,
            answers: state.answers
          })
        }
      );
      const data = await readJson(response);
      state.active = false;
      if (state.timerId) window.clearInterval(state.timerId);
      state.timerId = null;
      renderResults(data);
    } catch (error) {
      state.submitting = false;
      setExamButtonsDisabled(false);
      setStatus(
        examStatus,
        error.message || 'We could not mark this mock just now. Please try Finish again.',
        true
      );
    }
  }

  function optionText(question, label) {
    const match = (question.options || []).find(function (option) {
      return option.label === label;
    });
    return match ? match.text : '';
  }

  async function loadStudyPlan() {
    const panel = document.getElementById('study-plan-panel');
    const status = document.getElementById('study-plan-status');
    const holder = document.getElementById('study-plan-days');
    if (!panel || !status || !holder || !state.exam || state.exam.id === 'common-diagnostic-1') return;
    panel.hidden = false;
    status.textContent = 'Preparing your plan… Your parent’s 11+ Premium unlocks the 30-day plan.';
    try {
      let data = await readJson(await fetch('/api/elevenplus/mock-exams/study-plan', {
        credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store'
      }));
      for (let attempt = 0; attempt < 5 && !data.ready; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1200));
        data = await readJson(await fetch('/api/elevenplus/mock-exams/study-plan', {
          credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store'
        }));
      }
      if (!data.ready || !data.plan) {
        status.textContent = 'Your plan is still being prepared. Your parent can open it from the 11+ Premium study plan area later.';
        return;
      }
      status.textContent = '30 minutes a day for 30 days, focused on the topics that need the most practice.';
      holder.replaceChildren();
      (data.plan.days || []).forEach((day) => {
        const card = element('article', 'study-plan-day');
        card.appendChild(element('h3', '', 'Day ' + day.day + ' · ' + day.minutes + ' minutes'));
        card.appendChild(element('p', '', 'Focus: ' + (day.focus_topic || 'Targeted practice')));
        const list = element('ol');
        (day.questions || []).forEach((question) => {
          const item = element('li');
          item.appendChild(element('span', '', question.question));
          const options = element('ul');
          (question.options || []).forEach((option) => options.appendChild(element('li', '', option)));
          item.appendChild(options);
          list.appendChild(item);
        });
        card.appendChild(list);
        holder.appendChild(card);
      });
    } catch (error) {
      if (error.status === 402) {
        status.textContent = 'Your parent needs an active 11+ Premium plan to open this 30-day study plan.';
        return;
      }
      status.textContent = 'Your plan is still being prepared. Please check again from the 11+ Premium area.';
    }
  }

  async function fetchExplanation(examId, questionId) {
    const response = await fetch(
      '/api/elevenplus/mock-exams/' + encodeURIComponent(examId) +
      '/questions/' + encodeURIComponent(questionId) + '/explanation',
      { method: 'POST', credentials: 'same-origin', headers: {'Accept': 'application/json'} }
    );
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      throw new Error(payload.detail || payload.error || 'Unable to load explanation');
    }
    return payload.explanation || '';
  }

  function attachDetailedExplanation(details, examId, questionId, target) {
    let loaded = false;
    let loading = false;
    details.addEventListener('toggle', function () {
      if (!details.open || loaded || loading) return;
      loading = true;
      target.replaceChildren(element('p', '', 'Working through this question…'));
      fetchExplanation(examId, questionId).then(function (text) {
        loaded = true;
        target.replaceChildren();
        const content = element('div', 'mock-detail-content');
        content.innerHTML = formatMarkdown(text || '');
        target.appendChild(content);
      }).catch(function (error) {
        loading = false;
        target.replaceChildren(element('p', '', error.message || 'Please try again.'));
      });
    });
  }

  function renderResults(data) {
    examView.hidden = true;
    catalogueView.hidden = true;
    resultsView.hidden = false;

    document.getElementById('score-percent').textContent = data.score.percent + '%';
    document.getElementById('score-fraction').textContent =
      data.score.correct + ' of ' + data.score.total;
    document.getElementById('score-band').textContent = data.score.band;
    document.getElementById('score-message').textContent = data.score.message;
    document.getElementById('score-disclaimer').textContent = data.disclaimer;

    const breakdown = document.getElementById('subject-breakdown');
    breakdown.replaceChildren();
    (data.subject_breakdown || []).forEach(function (subject) {
      const card = element('div', 'subject-score');
      card.appendChild(element('strong', '', subject.subject));
      card.appendChild(element(
        'span',
        '',
        subject.correct + '/' + subject.total + ' · ' + subject.percent + '%'
      ));
      breakdown.appendChild(card);
    });

    const topics = document.getElementById('topic-recommendations');
    topics.replaceChildren();
    if (data.recommended_topics && data.recommended_topics.length) {
      data.recommended_topics.forEach(function (topic) {
        // The result data contains the topic name; find the matching question so
        // we can carry the correct 11+ subject into Topic Mastery as well.
        let subject = '';
        for (const questionResult of (data.questions || [])) {
          const question = state.questionById.get(questionResult.id);
          if (question && question.topic === topic) {
            subject = question.subject || '';
            break;
          }
        }
        const link = element('a', 'topic-chip', topic);
        const params = new URLSearchParams();
        if (subject) params.set('subject', subject);
        params.set('topic', topic);
        link.href = '/elevenplus-topic-mastery?' + params.toString();
        link.target = '_blank';
        link.rel = 'noopener';
        link.title = 'Practise ' + topic + ' in 11+ Topic Mastery';
        topics.appendChild(link);
      });
    } else {
      topics.appendChild(element('span', 'topic-chip', 'Keep up your steady practice'));
    }

    const review = document.getElementById('question-review');
    review.replaceChildren();
    (data.questions || []).forEach(function (result) {
      const question = state.questionById.get(result.id);
      const details = element('details', 'review-item ' + (result.correct ? 'correct' : 'incorrect'));
      const summary = element('summary');
      const summaryText = question
        ? 'Question ' + result.number + ' · ' + question.subject
        : 'Question ' + result.number;
      summary.appendChild(element('span', '', summaryText));
      summary.appendChild(element(
        'span',
        'review-mark',
        result.correct ? '✓ Correct' : (result.selected_answer ? '✗ Check this' : '○ Not answered')
      ));
      details.appendChild(summary);

      const body = element('div', 'review-body');
      if (question) body.appendChild(element('p', '', question.prompt));
      const selectedText = result.selected_answer && question
        ? result.selected_answer + '. ' + optionText(question, result.selected_answer)
        : 'Not answered';
      const selectedRow = element('p');
      selectedRow.appendChild(element('strong', '', 'Your answer: '));
      selectedRow.appendChild(document.createTextNode(selectedText));
      body.appendChild(selectedRow);
      const correctRow = element('p');
      correctRow.appendChild(element('strong', '', 'Correct answer: '));
      correctRow.appendChild(document.createTextNode(
        result.correct_answer + '. ' + result.correct_answer_text
      ));
      body.appendChild(correctRow);
      const explanationRow = element('div', 'mock-why-row');
      const shortWhy = element('span', 'mock-why-short');
      shortWhy.appendChild(element('strong', '', 'Why: '));
      shortWhy.appendChild(document.createTextNode(result.explanation));
      explanationRow.appendChild(shortWhy);
      const whyContent = element('div', 'mock-detail-explanation');
      explanationRow.appendChild(whyContent);
      body.appendChild(explanationRow);
      attachDetailedExplanation(details, data.exam.id, result.id, whyContent);
      details.appendChild(body);
      review.appendChild(details);
    });

    document.title = data.exam.title + ' result | Homework Magic';
    window.scrollTo({top: 0, behavior: 'smooth'});
    if (data.study_plan && data.study_plan.status === 'preparing') loadStudyPlan();
  }

  previousButton.addEventListener('click', function () { moveQuestion(-1); });
  nextButton.addEventListener('click', function () {
    if (state.currentIndex === state.questions.length - 1) {
      submitExam(false);
    } else {
      moveQuestion(1);
    }
  });
  finishButton.addEventListener('click', function () { submitExam(false); });
  backToMocks.addEventListener('click', function () {
    resetAttemptState();
    resultsView.hidden = true;
    examView.hidden = true;
    catalogueView.hidden = false;
    document.title = '11+ Mock Exams | Homework Magic';
    loadCatalogue();
    window.scrollTo({top: 0, behavior: 'smooth'});
  });

  ['mock-search', 'mock-region', 'mock-type'].forEach(function (id) {
    const control = document.getElementById(id);
    if (!control) return;
    control.addEventListener(id === 'mock-search' ? 'input' : 'change', applyMockFilters);
  });

  document.querySelectorAll('[data-mock-chip]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      const value = chip.getAttribute('data-mock-chip') || '';
      const search = document.getElementById('mock-search');
      const region = document.getElementById('mock-region');
      if (value === 'essex' || value === 'london') {
        if (search) search.value = '';
        if (region) region.value = value;
      } else {
        if (search) search.value = value;
        if (region) region.value = 'all';
      }
      applyMockFilters();
      document.getElementById('finder-title').scrollIntoView({behavior: 'smooth', block: 'start'});
    });
  });

  window.addEventListener('beforeunload', function (event) {
    if (!state.active || state.submitting) return;
    event.preventDefault();
    event.returnValue = '';
  });

  loadCatalogue();
}());
