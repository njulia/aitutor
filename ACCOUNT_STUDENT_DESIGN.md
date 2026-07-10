# Account, Student and Subscription Design

## Relationships

- One parent/account owns one or more students.
- A subscription belongs to the account, not to a student.
- Homework, tutor sessions and progress continue to use `student_id`.
- Messages and billing use the account email/account ID; a message may optionally refer to a student.

## New API

- `GET /api/account` — account, students and active subscription.
- `GET /api/students` — list the signed-in account's students.
- `POST /api/students` — create a student.
- `PUT /api/students/{student_id}` — update an owned student.
- `GET /api/admin/accounts/{email}` — admin account overview.
- `POST /api/admin/account-subscriptions` — create an account-level subscription.

For learning requests, select a child with the `X-Student-Id` request header. The server verifies that the selected student belongs to the authenticated account. When the header is absent, the account's first active student is used.

## Backward compatibility

Existing registered users are migrated lazily. On their first authenticated request, the system creates:

1. an account using their login email;
2. one default student;
3. future subscriptions in `account_subscriptions`.

Old development subscriptions stored by email remain readable as a temporary fallback.

## Environment

Set `ACCOUNT_DB_PATH` to override the default SQLite database path (`data/accounts.db`).
