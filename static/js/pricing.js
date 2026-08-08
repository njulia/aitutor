(function () {
  'use strict';

  var statusEl = document.getElementById('status');
  var planSummary = document.getElementById('public-plan-summary');
  var pricingLoginButton = document.getElementById('pricing-login-button');
  var checkoutButtons = Array.prototype.slice.call(
    document.querySelectorAll('.checkout-button[data-plan]')
  );
  var accountActions = document.getElementById('account-actions');
  var subscriptionSummary = document.getElementById('subscription-summary');
  var subscriptionDetail = document.getElementById('subscription-detail');
  var changePlanButton = document.getElementById('change-plan-button');
  var cancelPlanButton = document.getElementById('cancel-plan-button');
  var portalButton = document.getElementById('portal-button');
  var existingBillingActions = document.getElementById('existing-billing-actions');
  var existingPortalButton = document.getElementById('existing-portal-button');
  var checkoutHelp = document.getElementById('checkout-help');
  var navLogin = document.getElementById('pricing-nav-login');
  var navLearning = document.getElementById('pricing-nav-learning');
  var navLogout = document.getElementById('pricing-nav-logout');
  var navRegister = document.getElementById('pricing-nav-register');
  var billingButtons = [changePlanButton, cancelPlanButton, portalButton];
  var billingHelp = accountActions.querySelector('.billing-help');
  var pricingTableSection = document.getElementById('stripe-pricing-table-section');
  var pricingTableContainer = document.getElementById('stripe-pricing-table-container');
  var pricingTableLoaded = false;

  function setStatus(message, isError) {
    statusEl.textContent = message;
    statusEl.style.color = isError ? '#a52b3a' : '#245d3a';
  }

  function readJson(response) {
    return response.json().catch(function () { return {}; }).then(function (data) {
      if (!response.ok) {
        var error = new Error(data.detail || data.error || 'The billing request failed.');
        error.status = response.status;
        throw error;
      }
      return data;
    });
  }

  function renderSignedInNavigation(signedIn) {
    checkoutHelp.hidden = signedIn;
    navLogin.hidden = signedIn;
    navRegister.hidden = signedIn;
    navLearning.hidden = !signedIn;
    navLogout.hidden = !signedIn;
    pricingLoginButton.hidden = signedIn;
  }

  function billingStatus(refresh) {
    var endpoint = refresh ? '/api/billing/status?refresh=true' : '/api/billing/status';
    return fetch(endpoint, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {'Accept': 'application/json'}
    }).then(readJson);
  }

  function formatDate(raw) {
    if (!raw) return '';
    var value = new Date(raw);
    return Number.isNaN(value.getTime()) ? '' : value.toLocaleDateString('en-GB');
  }

  function showActiveSubscription(data) {
    var planNames = {
      homework_monthly: 'Homework Premium',
      elevenplus_monthly: '11+ Premium',
      family_monthly: 'Family Premium',
      trial_5day: 'Five-day access',
      beta_year3: 'Free Year 3 parent beta'
    };
    var subscription = data.subscription || {};
    var management = data.management || {};
    var planName = planNames[subscription.plan] || 'Homework Magic';
    var endDate = formatDate(subscription.current_period_end);
    var cancellationScheduled = subscription.cancel_at_period_end === true;

    planSummary.hidden = true;
    accountActions.hidden = false;
    existingBillingActions.hidden = true;
    billingHelp.hidden = false;
    subscriptionSummary.textContent = planName;
    subscriptionDetail.textContent = cancellationScheduled
      ? 'Cancellation scheduled' + (endDate ? ' · access continues until ' + endDate : '')
      : 'Active' + (endDate ? ' · current paid month runs to ' + endDate : '');
    changePlanButton.hidden = management.can_change !== true;
    changePlanButton.disabled = false;
    cancelPlanButton.hidden = !(management.can_cancel === true || cancellationScheduled);
    cancelPlanButton.disabled = cancellationScheduled;
    cancelPlanButton.textContent = cancellationScheduled
      ? 'Cancellation scheduled'
      : 'Manage or cancel subscription';
    portalButton.hidden = management.can_manage !== true;
    setStatus(cancellationScheduled
      ? 'Your ' + planName + ' plan will not renew.' + (endDate ? ' Access continues until ' + endDate + '.' : '')
      : 'Your ' + planName + ' plan is active.' + (endDate ? ' Your current paid month runs to ' + endDate + '.' : ''));
  }

  function showBetaAccess(data) {
    var subscription = data.subscription || {};
    var endDate = formatDate(subscription.current_period_end);
    accountActions.hidden = false;
    subscriptionSummary.textContent = 'Free Year 3 parent beta';
    subscriptionDetail.textContent = 'Active' + (endDate ? ' until ' + endDate : '') + ' · no payment and no renewal';
    billingButtons.forEach(function (button) { button.hidden = true; });
    billingHelp.hidden = true;
  }

  function configureCheckoutButtons(data) {
    var availability = data.plan_availability || {};
    var unavailableCount = 0;
    checkoutButtons.forEach(function (button) {
      var plan = button.getAttribute('data-plan');
      var ready = availability[plan] === true;
      button.dataset.checkoutReady = 'true';
      button.textContent = button.getAttribute('data-checkout-label');
      button.href = '#';
      button.removeAttribute('aria-disabled');
      if (!ready) {
        unavailableCount += 1;
      }
    });
    if (unavailableCount >= checkoutButtons.length) {
      setStatus('Stripe billing may not be configured. You can still try to choose a plan.', true);
    } else if (unavailableCount > 0) {
      setStatus('Some plans may be temporarily unavailable.', true);
    }
  }

  function loadStripePricingTable() {
    if (pricingTableLoaded || !pricingTableSection || !pricingTableContainer) {
      return;
    }
    fetch('/api/billing/pricing-table-session', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Accept': 'application/json'}
    }).then(readJson).then(function (data) {
      if (!data.client_secret || !data.pricing_table_id || !data.publishable_key) {
        return;
      }
      var script = document.createElement('script');
      script.src = 'https://js.stripe.com/v3/pricing-table.js';
      script.async = true;
      script.onload = function () {
        var el = document.createElement('stripe-pricing-table');
        el.setAttribute('client-reference-id', data.client_reference_id || '');
        el.setAttribute('customer-session-client-secret', data.client_secret);
        el.setAttribute('pricing-table-id', data.pricing_table_id);
        el.setAttribute('publishable-key', data.publishable_key);
        pricingTableContainer.appendChild(el);
        pricingTableSection.hidden = false;
        pricingTableLoaded = true;
      };
      document.head.appendChild(script);
    }).catch(function () {
      // 自定义卡片仍然是主要的结账方式，加载失败不影响页面功能
    });
  }

  function checkoutUrlIsSafe(rawUrl) {
    try {
      var target = new URL(rawUrl);
      return target.protocol === 'https:' && target.hostname === 'checkout.stripe.com';
    } catch (_) {
      return false;
    }
  }

  function startCheckout(plan, button) {
    button.setAttribute('aria-disabled', 'true');
    setStatus('Opening Stripe’s secure payment page…');
    return fetch('/api/billing/checkout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
      body: JSON.stringify({plan: plan})
    }).then(readJson).then(function (data) {
      if (!checkoutUrlIsSafe(data.checkout_url)) {
        throw new Error('Stripe returned an invalid checkout link.');
      }
      window.location.assign(data.checkout_url);
    }).catch(function (error) {
      button.removeAttribute('aria-disabled');
      setStatus(error.message || 'Checkout is temporarily unavailable.', true);
    });
  }

  checkoutButtons.forEach(function (button) {
    button.addEventListener('click', function (event) {
      if (button.dataset.checkoutReady !== 'true') return;
      event.preventDefault();
      startCheckout(button.getAttribute('data-plan'), button);
    });
  });

  function initialiseBilling() {
    return billingStatus(true).then(function (data) {
      renderSignedInNavigation(true);
      if (data.has_subscription && !(data.management && data.management.is_beta)) {
        showActiveSubscription(data);
        return;
      }
      configureCheckoutButtons(data);
      if (data.has_subscription) {
        showBetaAccess(data);
        var trial = document.getElementById('trial-checkout-button');
        trial.removeAttribute('href');
        trial.setAttribute('aria-disabled', 'true');
        trial.textContent = 'Five-day access unavailable';
        loadStripePricingTable();
        setStatus('Your free beta access is active. You can upgrade to a monthly plan below.');
        return;
      }
      accountActions.hidden = true;
      existingBillingActions.hidden = !(data.management && data.management.can_manage === true);
      loadStripePricingTable();
      if (data.refresh && data.refresh.attempted && !data.refresh.succeeded) {
        setStatus('We could not refresh Stripe just now. You can still choose an available plan.', true);
      } else {
        setStatus("Choose a plan above to continue to Stripe's secure checkout.");
      }
    }).catch(function (error) {
      if (error.status === 401) {
        renderSignedInNavigation(false);
        setStatus('A parent or guardian needs to sign in before choosing a plan.');
        return;
      }
      if (error.status === 409) {
        accountActions.hidden = false;
        setStatus(error.message);
        return;
      }
      // 非 401 错误：假设用户已登录（否则会返回 401），配置 UI 为已登录状态
      renderSignedInNavigation(true);
      configureCheckoutButtons({plan_availability: {}});
      loadStripePricingTable();
      setStatus(error.message || 'We could not verify plan details. You can still try — we will confirm at checkout.', true);
    });
  }

  function portalUrlIsSafe(rawUrl) {
    try {
      var target = new URL(rawUrl);
      return target.protocol === 'https:' && (
        target.hostname === 'billing.stripe.com' || target.hostname.endsWith('.stripe.com')
      );
    } catch (_) {
      return false;
    }
  }

  function openPortal(action) {
    var allowed = {change: 'change', cancel: 'cancel', manage: ''};
    var selected = Object.prototype.hasOwnProperty.call(allowed, action) ? action : 'manage';
    var previousState = billingButtons.map(function (button) { return button.disabled; });
    billingButtons.forEach(function (button) { button.disabled = true; });
    setStatus(selected === 'change'
      ? 'Opening Stripe to change your plan…'
      : selected === 'cancel'
        ? 'Opening Stripe to cancel your subscription…'
        : 'Opening your secure Stripe billing details…');
    var suffix = allowed[selected] ? '/' + allowed[selected] : '';
    return fetch('/api/billing/portal' + suffix, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Accept': 'application/json'}
    }).then(readJson).then(function (data) {
      if (!portalUrlIsSafe(data.portal_url)) {
        throw new Error('Stripe returned an invalid billing link.');
      }
      window.location.assign(data.portal_url);
    }).catch(function (error) {
      billingButtons.forEach(function (button, index) { button.disabled = previousState[index]; });
      setStatus(error.message || 'The billing portal is temporarily unavailable.', true);
    });
  }

  changePlanButton.addEventListener('click', function () { openPortal('change'); });
  cancelPlanButton.addEventListener('click', function () { openPortal('cancel'); });
  portalButton.addEventListener('click', function () { openPortal('manage'); });
  existingPortalButton.addEventListener('click', function () { openPortal('manage'); });

  navLogout.addEventListener('click', function (event) {
    event.preventDefault();
    navLogout.textContent = 'Logging out…';
    navLogout.setAttribute('aria-disabled', 'true');
    fetch('/api/logout', {
      method: 'POST', credentials: 'same-origin', headers: {'Accept': 'application/json'}
    }).then(function (response) {
      if (!response.ok) throw new Error('Logout failed.');
      localStorage.removeItem('auth_state');
      localStorage.removeItem('student_id');
      localStorage.removeItem('student_email');
      window.location.assign('/');
    }).catch(function () {
      navLogout.textContent = 'Log out';
      navLogout.removeAttribute('aria-disabled');
      setStatus('We could not log you out just now. Please try again.', true);
    });
  });

  function pollForAccess() {
    var attempt = 0;
    function poll() {
      if (attempt >= 8) {
        setStatus('Thank you. Stripe is still confirming your plan. Please refresh this page in a moment.');
        return;
      }
      attempt += 1;
      billingStatus(attempt === 3 || attempt === 6).then(function (data) {
        if (data.has_subscription) {
          renderSignedInNavigation(true);
          showActiveSubscription(data);
          return;
        }
        window.setTimeout(poll, 1500);
      }).catch(function () {
        setStatus('Stripe is still confirming your plan. Please refresh this page in a moment.');
      });
    }
    poll();
  }

  var params = new URLSearchParams(window.location.search);
  if (params.get('checkout') === 'success') {
    setStatus('Thank you. Stripe is confirming your plan…');
    pollForAccess();
  } else {
    if (params.get('checkout') === 'cancelled') {
      setStatus('Checkout was cancelled. No changes were made.', true);
    } else if (params.get('billing') === 'changed') {
      setStatus('Your plan change was submitted securely. Stripe is confirming it…');
    } else if (params.get('billing') === 'cancelled') {
      setStatus('Your cancellation was submitted securely. Stripe is confirming it…');
    }
    initialiseBilling();
  }
}());
