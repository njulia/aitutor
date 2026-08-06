(function (global) {
  'use strict';

  var synth = global.speechSynthesis;
  var Utterance = global.SpeechSynthesisUtterance || global.webkitSpeechSynthesisUtterance;
  var supported = Boolean(synth && Utterance);
  var playbackId = 0;
  var retainedUtterance = null;
  var activeButton = null;
  var startTimer = null;
  var heartbeat = null;

  function clearTimer(timer) {
    if (timer) global.clearTimeout(timer);
    return null;
  }

  function restoreButton() {
    if (!activeButton) return;
    activeButton.classList.remove('speaking');
    if (activeButton.getAttribute('data-original-text')) {
      activeButton.textContent = activeButton.getAttribute('data-original-text');
    }
    activeButton.removeAttribute('aria-pressed');
    activeButton = null;
  }

  function stop() {
    playbackId += 1;
    startTimer = clearTimer(startTimer);
    if (heartbeat) global.clearInterval(heartbeat);
    heartbeat = null;
    retainedUtterance = null;
    restoreButton();
    if (supported) {
      try { synth.cancel(); } catch (error) { /* Browser owns playback. */ }
    }
  }

  function cleanText(value) {
    return String(value || '')
      .replace(/<[^>]*>/g, ' ')
      .replace(/[#*_`~]/g, '')
      .replace(/^\d+\.\s*/gm, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function splitText(value, maxLength) {
    var text = cleanText(value);
    var limit = Math.max(80, Math.min(Number(maxLength) || 200, 240));
    if (!text) return [];
    var sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];
    var chunks = [];
    var current = '';
    sentences.forEach(function (sentence) {
      sentence.trim().split(/\s+/).forEach(function (word) {
        var candidate = current ? current + ' ' + word : word;
        if (candidate.length <= limit) {
          current = candidate;
        } else {
          if (current) chunks.push(current);
          current = word;
        }
      });
    });
    if (current) chunks.push(current);
    return chunks;
  }

  function read(value, options) {
    options = options || {};
    var button = options.button || null;
    var togglingCurrent = Boolean(
      button && activeButton === button && button.classList.contains('speaking')
    );

    if (!supported) {
      if (typeof options.onError === 'function') options.onError('unsupported');
      return false;
    }

    if (activeButton || synth.speaking || synth.pending) stop();
    if (togglingCurrent) return true;

    var chunks = splitText(value, options.maxLength);
    if (!chunks.length) return false;

    playbackId += 1;
    var ownPlaybackId = playbackId;
    var didStart = false;
    var didNotifyStart = false;
    var retryUsed = false;

    if (button) {
      if (!button.getAttribute('data-original-text')) {
        button.setAttribute('data-original-text', button.textContent);
      }
      activeButton = button;
      button.classList.add('speaking');
      button.setAttribute('aria-pressed', 'true');
      button.textContent = '⏹ Stop reading';
    }

    function finish(errorCode) {
      if (ownPlaybackId !== playbackId) return;
      startTimer = clearTimer(startTimer);
      if (heartbeat) global.clearInterval(heartbeat);
      heartbeat = null;
      retainedUtterance = null;
      restoreButton();
      if (errorCode && typeof options.onError === 'function') {
        options.onError(errorCode);
      } else if (!errorCode && typeof options.onEnd === 'function') {
        options.onEnd();
      }
    }

    function speakChunk(index, isRetry) {
      if (ownPlaybackId !== playbackId) return;
      if (index >= chunks.length) {
        finish();
        return;
      }

      var utterance;
      try {
        utterance = new Utterance(chunks[index]);
        retainedUtterance = utterance;
        utterance.lang = options.lang || 'en-GB';
        utterance.rate = Number(options.rate) || 0.9;
        utterance.pitch = 1;
        utterance.volume = 1;
        utterance.onstart = function () {
          if (ownPlaybackId !== playbackId) return;
          didStart = true;
          startTimer = clearTimer(startTimer);
          if (!didNotifyStart && typeof options.onStart === 'function') {
            didNotifyStart = true;
            options.onStart();
          }
        };
        utterance.onend = function () {
          if (ownPlaybackId !== playbackId) return;
          startTimer = clearTimer(startTimer);
          speakChunk(index + 1, false);
        };
        utterance.onerror = function (event) {
          if (ownPlaybackId !== playbackId) return;
          var code = event && event.error ? event.error : 'speech-error';
          if (code === 'canceled' || code === 'interrupted') return;
          finish(code);
        };
        synth.speak(utterance);
        // Safari can leave the queue paused after a previous navigation.
        global.setTimeout(function () {
          if (ownPlaybackId === playbackId) {
            try { synth.resume(); } catch (error) { /* No-op. */ }
          }
        }, 0);
      } catch (error) {
        finish('speech-error');
        return;
      }

      startTimer = global.setTimeout(function () {
        if (ownPlaybackId !== playbackId || didStart) return;
        if (!retryUsed && !isRetry) {
          retryUsed = true;
          try { synth.cancel(); } catch (error) { /* No-op. */ }
          global.setTimeout(function () {
            if (ownPlaybackId === playbackId) speakChunk(index, true);
          }, 180);
          return;
        }
        finish('not-started');
      }, 1800);
    }

    heartbeat = global.setInterval(function () {
      if (ownPlaybackId !== playbackId) return;
      try { synth.resume(); } catch (error) { /* No-op. */ }
    }, 5000);
    speakChunk(0, false);
    return true;
  }

  global.HomeworkMagicSpeech = {
    isSupported: function () { return supported; },
    read: read,
    stop: stop,
    _cleanText: cleanText,
    _splitText: splitText
  };

  if (global.addEventListener) {
    global.addEventListener('pagehide', stop);
  }
})(window);
