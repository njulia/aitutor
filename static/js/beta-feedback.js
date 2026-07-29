'use strict';

const feedbackForm = document.getElementById('beta-feedback-form');
const feedbackSubmit = document.getElementById('feedback-submit');
const feedbackStatus = document.getElementById('feedback-status');
const feedbackSuccessActions = document.getElementById('feedback-success-actions');

function setFeedbackStatus(message, isError = false) {
  feedbackStatus.textContent = message;
  feedbackStatus.className = `beta-status${isError ? ' error' : ''}`;
}

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.error || 'That did not work. Please try again.');
  }
  return data;
}

async function prefillParentEmail() {
  try {
    const response = await fetch('/api/account', {
      credentials: 'same-origin',
      headers: {'Accept': 'application/json'},
    });
    if (!response.ok) return;
    const data = await response.json();
    const email = data && data.account && data.account.email;
    if (typeof email === 'string' && email.includes('@')) {
      document.getElementById('feedback-email').value = email;
    }
  } catch (_) {
    // Parents can type their email if account lookup is unavailable.
  }
}

feedbackForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  feedbackSubmit.disabled = true;
  feedbackSubmit.textContent = 'Sending…';
  setFeedbackStatus('');
  const start = document.getElementById('feedback-start').value;
  const independence = document.getElementById('feedback-independence').value;
  const useful = document.getElementById('feedback-useful').value;
  const confusing = document.getElementById('feedback-confusing').value.trim();
  const weekly = document.getElementById('feedback-weekly').value;
  const message = [
    `Ease of starting (1–5): ${start}`,
    `Learner understood the steps (1–5): ${independence}`,
    `Usefulness of questions and feedback (1–5): ${useful}`,
    `Most confusing or frustrating part: ${confusing}`,
    `Would use a short activity weekly: ${weekly}`,
  ].join('\n');
  try {
    await readJson(await fetch('/api/messages', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contact_email: document.getElementById('feedback-email').value.trim(),
        category: 'beta_feedback',
        subject: 'Year 3 parent beta feedback',
        message,
      }),
    }));
    feedbackForm.hidden = true;
    feedbackSuccessActions.hidden = false;
    setFeedbackStatus('Thank you. Your feedback was sent to Homework Magic.');
  } catch (error) {
    setFeedbackStatus(error.message, true);
  } finally {
    feedbackSubmit.disabled = false;
    feedbackSubmit.textContent = 'Send parent feedback';
  }
});

prefillParentEmail();
