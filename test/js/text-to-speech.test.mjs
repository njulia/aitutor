import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('../../static/js/text-to-speech.js', import.meta.url), 'utf8');

function speechWindow() {
  const spoken = [];
  class Utterance {
    constructor(text) { this.text = text; }
  }
  const synth = {
    speaking: false,
    pending: false,
    cancel() { this.speaking = false; this.pending = false; },
    resume() {},
    speak(utterance) {
      spoken.push(utterance.text);
      this.speaking = true;
      queueMicrotask(() => {
        if (utterance.onstart) utterance.onstart();
        this.speaking = false;
        if (utterance.onend) utterance.onend();
      });
    },
  };
  const window = {
    speechSynthesis: synth,
    SpeechSynthesisUtterance: Utterance,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    addEventListener() {},
  };
  vm.runInNewContext(source, {window, Boolean, Number, String}, {filename: 'text-to-speech.js'});
  return {window, spoken};
}

test('detects support only when the synthesiser and utterance constructor exist', () => {
  const unsupported = {setTimeout, clearTimeout, setInterval, clearInterval, addEventListener() {}};
  vm.runInNewContext(source, {window: unsupported, Boolean, Number, String});
  assert.equal(unsupported.HomeworkMagicSpeech.isSupported(), false);
  assert.equal(unsupported.HomeworkMagicSpeech.read('Hello'), false);
});

test('cleans markup and splits long text into browser-safe chunks', () => {
  const {window} = speechWindow();
  assert.equal(window.HomeworkMagicSpeech._cleanText('<b>Hello</b>  **there**'), 'Hello there');
  const chunks = window.HomeworkMagicSpeech._splitText('word '.repeat(120), 100);
  assert.ok(chunks.length > 1);
  assert.ok(chunks.every((chunk) => chunk.length <= 100));
});

test('starts device speech, retains chunks and reports the first audible start', async () => {
  const {window, spoken} = speechWindow();
  let starts = 0;
  let ended = 0;
  const text = `First ${'word '.repeat(18)}. Second ${'step '.repeat(18)}.`;
  assert.equal(window.HomeworkMagicSpeech.read(text, {
    maxLength: 80,
    onStart() { starts += 1; },
    onEnd() { ended += 1; },
  }), true);
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.ok(spoken.length >= 2);
  assert.match(spoken.join(' '), /First/);
  assert.match(spoken.join(' '), /Second/);
  assert.equal(starts, 1);
  assert.equal(ended, 1);
});
