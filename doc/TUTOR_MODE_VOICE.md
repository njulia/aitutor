# Tutor Mode: Voice Add-On (Sketch)

**Scope:** Tutor Mode only (one question at a time). Homework Mode (all questions at once) stays as-is — voice makes most sense when a child is focused on a single question, not scanning a whole page.

**Guiding idea:** don't touch the backend or the answer-submission logic at all. Voice input just *types into the existing textarea* (`#tutor-answer-input`), so `reviewCurrentQuestion()` and the RAG/answer-index pipeline stay completely untouched. Voice output just reads `hw.content` aloud before the child even starts typing/speaking.

---

## Two tiers, pick your starting point

**Tier 0 — Browser-native (Web Speech API). Ship this first.**
- Zero backend changes. Zero API cost. Works today.
- `speechSynthesis` reads the question aloud (Text-to-Speech).
- `SpeechRecognition` (aka `webkitSpeechRecognition`) transcribes the child's spoken answer straight into the textarea (Speech-to-Text).
- Catch: Chrome/Edge support is solid; **Safari/iOS support for `SpeechRecognition` is poor or missing**, which matters a lot for a UK primary-school audience where a large share of home devices are iPads. Needs a feature-detect + graceful fallback (hide the mic button, keep typing).
- Privacy note: Chrome's on-device speech recognition for `webkitSpeechRecognition` actually sends audio to Google's servers to transcribe it. For a product aimed at under-13s, that's worth a line in your privacy policy and worth knowing before you badge this as "AI teacher listens to you" — it's not local/on-device.

**Tier 1 — Server-side STT (e.g. Whisper via API), only if Tier 0's reliability/coverage isn't good enough.**
- New `/api/transcribe-answer` endpoint: browser records audio (`MediaRecorder`), uploads a blob, backend transcribes, returns text, frontend drops it into the same textarea.
- Costs money per request, adds latency, but works uniformly across browsers and you control data handling end-to-end (relevant for child-data compliance).
- Only worth building once you know from Tier 0 usage data whether voice mode actually gets used and where it breaks.

Start with Tier 0. It's a genuinely small, low-risk addition that plugs into your existing `displayTutorQuestion()` flow.

---

## Frontend changes (Tier 0)

### 1. New controls in the tutor question block

Add a speaker button next to the question, and a mic button next to the answer box. Only render them if the browser supports the relevant API.

```js
// Feature detection — run once
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
const ttsSupported = 'speechSynthesis' in window;
const sttSupported = !!SpeechRec;
```

### 2. Modify `displayTutorQuestion(index)`

Add the two optional buttons into the existing template, conditionally:

```js
function displayTutorQuestion(index) {
    if (index >= currentHomework.length) {
        alert('You have completed all questions!');
        clearResults();
        return;
    }

    const hw = currentHomework[index];
    const container = document.getElementById('homework-results');
    container.innerHTML = `
        <div class="homework-block">
            <h3 class="subject-header">${hw.subject} (Question ${index + 1} of ${currentHomework.length}) ${hw.from_rag ? '(Free - from library)' : ''}</h3>
            <div class="homework-content">
                <div class="question-column">
                    ${ttsSupported ? `
                        <button class="voice-btn" id="speak-question-btn" onclick="speakQuestion()" title="Read question aloud">
                            🔊 Read it to me
                        </button>` : ''}
                    ${formatQuestions(marked.parse(hw.content))}
                </div>
                <div class="answer-column">
                    <h4>Your Answer:</h4>
                    ${sttSupported ? `
                        <button class="voice-btn" id="voice-answer-btn" onclick="toggleVoiceAnswer()" title="Answer by speaking">
                            🎤 Answer by voice
                        </button>` : ''}
                    <textarea class="answer-input-inline"
                              id="tutor-answer-input"
                              placeholder="Write your answer here..."
                              data-subject="${hw.subject}"></textarea>
                </div>
            </div>
        </div>
    `;

    const savedAnswer = currentQuestionAnswers[index] || '';
    document.getElementById('tutor-answer-input').value = savedAnswer;

    showResults();
    document.getElementById('homework-buttons').style.display = 'none';
    document.getElementById('tutor-mode-buttons').style.display = 'block';
    document.getElementById('review-result').innerHTML = '';
}
```

### 3. New JS functions

```js
// --- Text to speech: read the current question aloud ---
function speakQuestion() {
    if (!ttsSupported) return;
    window.speechSynthesis.cancel(); // stop any previous utterance
    const hw = currentHomework[currentQuestionIndex];

    // Strip markdown/numbering noise so it reads naturally
    const plainText = hw.content
        .replace(/[#*_`]/g, '')
        .replace(/^\d+\.\s*/gm, '');

    const utterance = new SpeechSynthesisUtterance(plainText);
    utterance.lang = 'en-GB';
    utterance.rate = 0.9; // slightly slower for a young reader
    window.speechSynthesis.speak(utterance);
}

// --- Speech to text: dictate the answer into the textarea ---
let recognizer = null;
let isListening = false;

function toggleVoiceAnswer() {
    if (!sttSupported) return;
    const btn = document.getElementById('voice-answer-btn');
    const input = document.getElementById('tutor-answer-input');

    if (isListening) {
        recognizer.stop();
        return;
    }

    recognizer = new SpeechRec();
    recognizer.lang = 'en-GB';
    recognizer.interimResults = true;
    recognizer.continuous = false;

    recognizer.onstart = () => {
        isListening = true;
        btn.textContent = '🔴 Listening... (tap to stop)';
        btn.classList.add('listening');
    };

    recognizer.onresult = (event) => {
        const transcript = Array.from(event.results)
            .map(r => r[0].transcript)
            .join('');
        input.value = transcript;
    };

    recognizer.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        // Fall back silently — child can still type
    };

    recognizer.onend = () => {
        isListening = false;
        btn.textContent = '🎤 Answer by voice';
        btn.classList.remove('listening');
    };

    recognizer.start();
}
```

### 4. Small CSS addition

```css
.voice-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    margin-bottom: 12px;
    border: 2px solid #667eea;
    background: white;
    color: #667eea;
    border-radius: 50px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s;
}

.voice-btn:hover {
    background: #f8f9ff;
}

.voice-btn.listening {
    background: #fdecea;
    border-color: #e53935;
    color: #e53935;
    animation: pulse 1.2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
```

---

## What stays completely unchanged

- `reviewCurrentQuestion()` — still reads from `#tutor-answer-input`, has no idea whether the text got there by typing or by voice.
- `web_app.py` — no new routes needed for Tier 0.
- `homework_rag.py` / the answer-index fix — untouched, since this only affects how the *child's* answer gets into the textbox, not how it's evaluated.
- Homework Mode — unaffected; voice stays scoped to Tutor Mode.

## Rollout suggestion

1. Ship Tier 0 behind a simple `localStorage`-free toggle (just feature-detected, on by default where supported) for Year 1–3 accounts only first, since that's where typing is the real bottleneck.
2. Add one line to the privacy policy noting that voice answers are processed by the browser's speech service (Google's, in Chrome) rather than sent to your own servers, for Tier 0.
3. Watch usage: does the mic button get used at all on iPad (likely your most common device for this age group)? That tells you whether Tier 1 (paid, cross-browser STT) is worth building.
4. If you later want a fuller "AI teacher talks to me" experience (the child asks the AI teacher for help out loud, not just dictating an answer), that's a materially bigger feature — real-time conversational voice, turn-taking, cost-per-minute — and deserves its own scoping rather than an extension of this sketch.