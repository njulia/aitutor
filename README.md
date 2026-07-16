# Langfuse tracing for Homework Magic

## What was added

- One Langfuse trace for each important FastAPI API request.
- Descriptive trace names such as `homework-generation`, `homework-review`,
  `deep-explanation`, and `targeted-practice`.
- Nested `generation` observations around the custom `LLMClient` methods.
- Nested `retriever` observations around Chroma homework storage and search.
- Pseudonymous user/session identifiers, feature tags, HTTP status and app version.
- The trace ID is returned in the `X-Langfuse-Trace-Id` response header.
- Review feedback buttons create a `user-thumbs` BOOLEAN score on the trace.
- Graceful flush during FastAPI shutdown.

## Privacy defaults

This is a child-facing education service, so raw homework, answers, prompts,
model output, names, email addresses, tokens and uploaded content are not sent to
Langfuse by default. Text is represented by character count and a short SHA-256
fingerprint. Identifiers are salted and hashed.

Set `LANGFUSE_CAPTURE_CONTENT=true` only after completing a UK GDPR data
protection review, updating the privacy notice, defining retention, and ensuring
parent/guardian consent and lawful processing where required.

## Install

```bash
pip install -r requirements-langfuse.txt
```

Copy the variables from `.env.langfuse.example` into your normal `.env`. Do not
put real API keys in source control.

For the self-hosted Docker deployment, `LANGFUSE_BASE_URL` must be the URL that
the Python application can reach. When the Python process runs on the host and
Langfuse exposes port 3000, use `http://localhost:3000`. When both run in Docker,
use the Langfuse service name and internal port instead.

## Files

Place these files in the application repository:

- `src/observability.py`
- patched `web_app.py` (or the patched `web_app(7).py` if that is your entrypoint)
- patched `homework_rag.py` at `src/homework_rag.py`
- patched `app.html` at `static/app.html`
- `requirements-langfuse.txt`

## Verify

1. Start Langfuse and the tutor application.
2. Open `/api/health`; `langfuse.enabled` should be `true`.
3. Generate homework, review an answer, and open Langfuse **Traces**.
4. Confirm the trace contains a request span and nested generation/retriever spans.
5. Click a review thumbs button and confirm `user-thumbs` appears in the trace's Scores tab.

## Useful environment switches

```dotenv
# Disable tracing without changing code
LANGFUSE_TRACING_ENABLED=false

# Development-only content capture; keep false in production unless approved
LANGFUSE_CAPTURE_CONTENT=false

# Optional text feedback comments; kept off by default
LANGFUSE_CAPTURE_FEEDBACK_COMMENTS=false
```

## Which web app file to use

`web_app.py` is the patched version of the uploaded `web_app(7).py` and is the
recommended replacement. The same file is also kept under `source-names/`.
`alternatives/web_app_legacy.py` contains the matching patch for the other
legacy application variant supplied with the project; do not install both.

## Agent Skill copy

The archive includes the mirrored Langfuse Agent Skill under
`.agent-skills/skills/langfuse`. For a normal connected development machine,
run `./install_langfuse_skill.sh` to use the official installer and receive
future updates.
