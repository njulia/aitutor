# Voice Feature Integration Guide

**Scope:** Add optional voice input/output (Text-to-Speech for questions, Speech-to-Text for answers) to Tutor Mode only. Tier 0: Browser-native APIs (no backend changes needed except logging endpoints).

**Files Modified:**
1. `app.js` — global state, voice functions, logging calls
2. `app.html` — CSS styles for voice buttons
3. `web_app.py` — two new endpoints for logging and stats retrieval
4. `homework_rag.py` — ChromaDB collection + methods for voice events

---

## Step 1: Update `app.js`

### 1a. Add global state after line ~21 (after `elevenPlusSubjects` array)

```javascript
// ===== Voice Feature Detection & State (Tier 0: Browser-native) =====
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
const ttsSupported = 'speechSynthesis' in window;
const sttSupported = !!SpeechRec;
let recognizer = null;
let isListening = false;
```

**Location:** After the line defining `elevenPlusSubjects`, around line 21–25.

### 1b. Modify `displayTutorQuestion()` function (line ~1780)

**Current code (text-only branch):**
```javascript
} else {
    const tutorQuestion = stripStandaloneAnswerLabels(splitQuestionOnlyHomework(hw)[0] || hw.content || '');
    // ...
    container.innerHTML = `
        <div class="homework-block tutor-question-only-block">
            <h3 class="subject-header">${escapeHomeworkText(hw.subject || 'Homework')} (Question ${index + 1} of ${currentHomework.length}) ${hw.from_rag ? '(Free - from library)' : ''}</h3>
            <section class="single-question-card">
                <div class="${bodyClass}">
                    <div class="single-question-text">${formatQuestions(renderSafeMarkdown(tutorQuestion))}</div>
                    ${renderQuestionAnswerControl({...})}
                </div>
            </section>
        </div>
    `;
}
```

**Replace with:**
```javascript
} else {
    const tutorQuestion = stripStandaloneAnswerLabels(splitQuestionOnlyHomework(hw)[0] || hw.content || '');
    // ...
    container.innerHTML = `
        <div class="homework-block tutor-question-only-block">
            <h3 class="subject-header">${escapeHomeworkText(hw.subject || 'Homework')} (Question ${index + 1} of ${currentHomework.length}) ${hw.from_rag ? '(Free - from library)' : ''}</h3>
            <section class="single-question-card">
                <div class="${bodyClass}">
                    <div class="voice-controls-tutor">
                        ${ttsSupported ? `<button class="voice-btn" id="speak-question-btn" onclick="speakQuestion()" title="Read question aloud">🔊 Read it to me</button>` : ''}
                    </div>
                    <div class="single-question-text">${formatQuestions(renderSafeMarkdown(tutorQuestion))}</div>
                    ${renderQuestionAnswerControl({...})}
                    <div class="voice-controls-answer">
                        ${sttSupported ? `<button class="voice-btn" id="voice-answer-btn" onclick="toggleVoiceAnswer()" title="Answer by speaking">🎤 Answer by voice</button>` : ''}
                    </div>
                </div>
            </section>
        </div>
    `;
}
```

**Key changes:** Added two `<div>` blocks wrapping voice buttons (🔊 and 🎤), conditional on `ttsSupported` and `sttSupported`.

### 1c. Add these four functions at the end of the file (before the last closing brace `}`)

```javascript
// ===== VOICE FEATURE FUNCTIONS (Tier 0: Browser-native) =====

function getYearGroupForLogging() {
    // Extract year_group from currentProfile if available
    return (currentProfile && currentProfile.year_group) || null;
}

function logVoiceUsage(eventType) {
    const yearGroup = getYearGroupForLogging();
    const subject = currentHomework[currentQuestionIndex]?.subject;
    if (!yearGroup || !subject) return; // skip if context is unknown — never guess

    fetch('/api/log-voice-usage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            event_type: eventType,
            year_group: yearGroup,
            subject: subject,
            student_id: currentStudentId || null,
        })
    }).catch(() => {}); // never surface a logging failure to the child
}

// Text to speech: read the current question aloud
function speakQuestion() {
    if (!ttsSupported) return;
    logVoiceUsage('tts_used');
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

// Speech to text: dictate the answer into the textarea
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
        logVoiceUsage('stt_used');  // Log once when actual listening starts
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

---

## Step 2: Update `app.html`

### 2a. Add CSS before `</style>` tag (around line 995)

Find the closing `</style>` tag and add this before it:

```css
/* ===== Voice Feature Styles (Tier 0) ===== */
.voice-controls-tutor,
.voice-controls-answer {
    margin: 10px 0;
}

.voice-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    margin-right: 8px;
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
    transform: translateY(-1px);
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

/* Ensure voice controls don't break mobile layout */
@media (max-width: 768px) {
    .voice-btn {
        font-size: 13px;
        padding: 6px 12px;
        margin-right: 6px;
    }
}
```

---

## Step 3: Update `web_app.py`

### 3a. Add two new endpoints before `if __name__ == "__main__":`

Find the line `if __name__ == "__main__":` (should be around line 2233) and add this just before it:

```python
# ===== VOICE FEATURE ENDPOINTS (Tier 0: Browser-native) =====

@app.post("/api/log-voice-usage")
async def log_voice_usage(request: Request):
    """Log voice feature usage events (TTS or STT activation).
    
    POST body: {
        event_type: 'tts_used' | 'stt_used',
        year_group: int (1-6),
        subject: str,
        student_id: Optional[str]
    }
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.warning("[Voice] Failed to parse JSON: %s", e)
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    event_type = data.get("event_type")
    year_group = data.get("year_group")
    subject = data.get("subject")
    student_id = data.get("student_id")

    if event_type not in ("tts_used", "stt_used") or year_group is None or not subject:
        return JSONResponse(
            {"success": False, "error": "Missing or invalid fields"},
            status_code=400
        )

    try:
        from src.homework_rag import log_voice_event
        log_voice_event(
            event_type=event_type,
            year_group=int(year_group),
            subject=subject,
            student_id=student_id
        )
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[Voice] Failed to log event: %s", e)
        return JSONResponse(
            {"success": False, "error": "Failed to log event"},
            status_code=500
        )


@app.get("/api/admin/voice-usage-stats")
async def voice_usage_stats(request: Request):
    """Get aggregated voice feature usage stats by age and subject.
    
    Access: admin/dev-mode only (gate via existing auth checks if applicable)
    """
    try:
        from src.homework_rag import get_voice_usage_stats
        stats = get_voice_usage_stats()
        return JSONResponse({"success": True, "stats": stats})
    except Exception as e:
        logger.error("[Voice] Failed to fetch stats: %s", e)
        return JSONResponse(
            {"success": False, "error": "Failed to fetch stats"},
            status_code=500
        )
```

---

## Step 4: Update `homework_rag.py`

### 4a. In `HomeworkRAGStore.__init__` method, add this line after `self.collection` is initialized:

```python
self.voice_events_collection = self.client.get_or_create_collection(
    name="voice_usage_events",
    embedding_function=self.embedding_function,
    metadata={"hnsw:space": "cosine"},
)
```

**Location:** Around line ~100–120, in the `__init__` method, after the line defining `self.collection`.

### 4b. Add these methods to the `HomeworkRAGStore` class

Insert after the `get_stats()` method:

```python
def log_voice_event(
    self,
    event_type: str,       # 'tts_used' or 'stt_used'
    year_group: int,
    subject: str,
    student_id: str = None,
) -> str:
    """Log a single voice-feature usage event."""
    now = datetime.now()
    event_id = f"voice_{int(now.timestamp() * 1000)}"
    metadata = {
        "event_type": event_type,
        "year_group": year_group,
        "age": year_group + 4,  # Convention: age = 5 + (year_group - 1)
        "subject": subject,
        "student_id": student_id,
        "created_at": now.isoformat(),
    }
    sanitized = self._sanitize_metadata(metadata)
    self.voice_events_collection.add(
        documents=[f"{event_type} | year {year_group} | {subject}"],
        metadatas=[sanitized],
        ids=[event_id],
    )
    logger.info(f"[RAG] Logged voice event: {event_type} (Y{year_group}, {subject})")
    return event_id


def get_voice_usage_stats(self) -> Dict[str, Any]:
    """Aggregate voice usage by age and subject."""
    all_events = self.voice_events_collection.get()
    total = len(all_events["ids"]) if all_events.get("ids") else 0

    by_age: Dict[Any, int] = {}
    by_subject: Dict[str, int] = {}
    by_event_type: Dict[str, int] = {}

    for meta in (all_events.get("metadatas") or []):
        age = meta.get("age", "Unknown")
        subject = meta.get("subject", "Unknown")
        event_type = meta.get("event_type", "Unknown")
        by_age[age] = by_age.get(age, 0) + 1
        by_subject[subject] = by_subject.get(subject, 0) + 1
        by_event_type[event_type] = by_event_type.get(event_type, 0) + 1

    return {
        "total_events": total,
        "by_age": by_age,
        "by_subject": by_subject,
        "by_event_type": by_event_type,
    }
```

### 4c. Add these module-level functions at the end of `homework_rag.py`

After the existing convenience functions like `search_homework_answers()`:

```python
def log_voice_event(event_type: str, year_group: int, subject: str, student_id: str = None) -> str:
    """Convenience function: log a voice usage event."""
    store = get_homework_rag_store()
    return store.log_voice_event(event_type, year_group, subject, student_id)


def get_voice_usage_stats() -> Dict[str, Any]:
    """Convenience function: get aggregated voice usage statistics."""
    store = get_homework_rag_store()
    return store.get_voice_usage_stats()
```

---

## Testing Checklist

- [ ] **TTS (🔊 Read it to me):** Click button in Tutor Mode; should hear the question read aloud in en-GB accent, slightly slower (0.9x speed).
- [ ] **STT (🎤 Answer by voice):** Click button; should show "🔴 Listening... (tap to stop)". Speak an answer; should appear in the textarea. Click again to stop listening.
- [ ] **Safari/iOS:** Both buttons should be hidden (feature detection fails gracefully); typing should still work.
- [ ] **Logging:** Open browser DevTools → Network, click either voice button, should see POST to `/api/log-voice-usage` with status 200.
- [ ] **Stats:** In Admin Tools, click "Refresh Stats"; should see JSON with `total_events`, `by_age`, `by_subject`, `by_event_type` (initially empty if no events yet).

---

## Caveat: Privacy Note

The browser's `SpeechRecognition` API (Chrome/Edge/Android) sends audio to **Google's servers** for transcription — not on-device. Add a line to your privacy policy:

> "When using voice input in Tutor Mode, your speech is processed by the browser's speech recognition service (typically Google's services in Chrome), and is subject to Google's privacy policies."

---

## Tier 1 Future: If browser-native STT isn't reliable enough

Build a `/api/transcribe-answer` endpoint using a real speech-to-text service (e.g. OpenAI Whisper, Google Speech-to-Text, AWS Transcribe). This requires:

1. Frontend: `MediaRecorder` to capture audio blob, POST blob to backend
2. Backend: receive blob, send to STT API, return text
3. Add cost (~$0.01–$0.05 per transcription)

Only build if usage data shows voice mode is actively used and browser-native STT fails too often.
