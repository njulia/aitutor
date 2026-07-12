# Forgot-password setup

## Files

Copy the files in this patch into the same paths in the project. The supplied `web_app.py` is based on the latest Contact Me and multiple-choice version.

## Email

Set `PUBLIC_BASE_URL` and the `SMTP_*` values shown in `.env.password-reset.example`. The reset request always shows the same public message, so visitors cannot test whether an email has an account.

## Password database compatibility

The reset module first looks for one of these functions in `src/progress_db.py`:

```python
set_user_password(username, new_password)
update_user_password(username, new_password)
reset_user_password(username, new_password)
change_user_password(username, new_password)
```

If none exists, it supports the current SQLite `users` table by finding its email and password-hash columns and reusing the password hasher from `progress_db.py`.

For the clearest long-term design, add an explicit function to `progress_db.py` that uses exactly the same password hasher as `create_user()` and updates one matching user inside a transaction.

## Security behaviour

- Links expire after 30 minutes by default.
- Tokens are random, stored only as SHA-256 hashes, and work once.
- A new request invalidates previous links for that account.
- Requests are rate-limited by hashed email and hashed client address.
- The API does not reveal whether an account exists.
- Reset records are cleaned after expiry/use.
- Existing sessions are revoked when the current `auth_tokens` module provides a per-user revocation function.

## Local test

For local development only:

```env
DEV_MODE=true
PASSWORD_RESET_DEV_SHOW_LINK=true
```

The generic success response will then include a development reset link. Keep this disabled in production.
