# Contact Me setup

## Files

Copy the files in this package into the same paths in the project. Existing files in this package are complete replacements; new files should be added.

## What users see

- **Contact Me** in the main navigation.
- A parent/guardian contact form at `/contact-me`.
- Their support message box at `/messages`.
- Replies appear in the message box even when email delivery is unavailable.

The form warns users not to include a child's full name, school, address, phone number, date of birth or other private details.

## What admins see

- A **User Messages** shortcut with an unread count on `/admin`.
- The inbox at `/admin/messages`.
- Status filters, message details, reply box, and optional email delivery.

Admin access uses the existing authenticated admin allowlist. Set `ADMIN_EMAILS` in the normal application environment.

## Email

Copy the required values from `.env.contact.example` into the application's environment. Keep SMTP passwords in the deployment secret store, not in source control.

When SMTP is missing or fails, the reply remains available in the user's message box and the dashboard displays the email result.

## Run

```bash
# Docker
# Rebuild because backend and static files changed.
docker compose up -d --build

# Local
python web_app.py
```

Then visit:

- `http://localhost:5000/contact-me`
- `http://localhost:5000/admin/messages`

## Tests

```bash
pytest -q test/unit/test_message_store.py
```
