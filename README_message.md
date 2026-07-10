# Homework Magic refactor

This package reduces the size of the two largest files without changing API paths.

## Backend
- `web_app.py`: FastAPI composition and routes only.
- `src/webapp/question_utils.py`: question splitting, numbering and fallback matching.
- `src/webapp/review_service.py`: review, detailed explanation and improvement practice.
- `src/webapp/models.py`: Pydantic request models.

## Frontend
- `static/app.html`: page markup only.
- `static/css/app.css`: extracted styles.
- `static/js/app.js`: extracted application logic.

Copy these files into the same relative paths in your project. Keep your existing `homework_rag.py`; it is not changed.

## User message module

New pages:

- `/messages` — user contact form and in-system message inbox
- `/admin/messages` — admin inbox, message detail and reply screen

New API endpoints:

- `POST /api/messages`
- `GET /api/messages`
- `GET /api/messages/{message_id}`
- `GET /api/admin/messages`
- `GET /api/admin/messages/{message_id}`
- `POST /api/admin/messages/{message_id}/reply`
- `PATCH /api/admin/messages/{message_id}/status`

Replies are always stored in SQLite. Email delivery is attempted when requested and the result (`sent`, `failed`, `skipped`, or `not_requested`) is stored with the reply.

### Environment variables

```env
MESSAGE_DB_PATH=data/user_messages.db

# Optional protection for the admin message API.
ADMIN_API_KEY=replace-with-a-long-random-secret

# SMTP settings for reply emails.
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=support@example.com
SMTP_USE_TLS=true
```

When `ADMIN_API_KEY` is set, the admin dashboard sends it through the `X-Admin-Key` header. When SMTP is not configured, the reply remains available in the system and its email status is recorded as `skipped`.

### Privacy

The module stores only data needed to handle the support request: email, message, replies, category, status and timestamps. Database access is separated by account email or an anonymous access token. Configure retention and deletion rules appropriate for your UK GDPR policy before production deployment.
