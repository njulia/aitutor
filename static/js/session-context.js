(function (global) {
  'use strict';

  var cachedPromise = null;

  function requestContext(force) {
    if (!force && cachedPromise) return cachedPromise;
    cachedPromise = global.fetch('/api/session-context', {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {'Accept': 'application/json'}
    }).then(function (response) {
      if (!response.ok) throw new Error('Session status request failed.');
      return response.json();
    }).catch(function (error) {
      cachedPromise = null;
      throw error;
    });
    return cachedPromise;
  }

  global.HomeworkMagicSession = {
    get: requestContext,
    clear: function () { cachedPromise = null; }
  };
})(window);
