'use strict';

const betaForm = document.getElementById('beta-form');
const betaCode = document.getElementById('beta-code');
const betaSubmit = document.getElementById('beta-submit');
const betaStatus = document.getElementById('beta-status');
const betaSuccessActions = document.getElementById('beta-success-actions');

function setBetaStatus(message, isError = false) {
  betaStatus.textContent = message;
  betaStatus.className = `beta-status${isError ? ' error' : ''}`;
}

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || data.error || 'That did not work. Please try again.');
    error.status = response.status;
    throw error;
  }
  return data;
}

betaForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const inviteCode = betaCode.value.trim();
  if (!inviteCode) {
    setBetaStatus('Please enter the invitation code.', true);
    return;
  }
  betaSubmit.disabled = true;
  betaSubmit.textContent = 'Checking invitation…';
  setBetaStatus('');
  try {
    const response = await fetch('/api/billing/beta/redeem', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({invite_code: inviteCode}),
    });
    const data = await readJson(response);
    const end = data.current_period_end ? new Date(data.current_period_end) : null;
    const endText = end && !Number.isNaN(end.getTime())
      ? ` until ${end.toLocaleDateString('en-GB')}`
      : '';
    setBetaStatus(`Your free beta access is ready${endText}. It will not renew and no payment was taken.`);
    betaCode.value = '';
    betaForm.hidden = true;
    betaSuccessActions.hidden = false;
  } catch (error) {
    if (error.status === 401) {
      const next = encodeURIComponent('/beta');
      setBetaStatus('A parent or guardian needs to sign in before using the invitation.', true);
      window.setTimeout(() => {
        window.location.assign(`/login?next=${next}`);
      }, 900);
    } else {
      setBetaStatus(error.message, true);
    }
  } finally {
    betaSubmit.disabled = false;
    betaSubmit.textContent = 'Start free beta access';
  }
});
