# User Message Module

## End-to-end flow

1. A logged-in user opens `/messages`; their account email is used automatically.
2. An anonymous user supplies an email address.
3. `POST /api/messages` stores the message and returns a private access token.
4. The admin opens `/admin/messages`, checks the inbox and writes a reply.
5. The reply is saved first, so it is always visible in the user's system inbox.
6. If email sending is enabled, SMTP delivery is attempted and its result is stored.

## Production checklist

- Set `ADMIN_API_KEY` or integrate the routes with your existing admin authentication.
- Configure SMTP variables.
- Back up `data/user_messages.db`.
- Add a retention/deletion policy for support messages.
- Avoid putting confidential child information into support messages.
- Serve the site over HTTPS.

## Tests

```bash
pytest tests/unit/test_message_store.py \
       tests/unit/test_message_models.py \
       tests/unit/test_email_service.py \
       tests/e2e/test_message_api.py
```
