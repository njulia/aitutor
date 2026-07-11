"""Optional eager migration for existing authentication users.

The application already migrates users lazily. Use this script when
`src.progress_db.list_all_users()` is available and you want to prepare all
accounts before deployment.
"""
from src.webapp.account_store import ensure_account, ensure_default_student


def main() -> None:
    from src.progress_db import list_all_users
    migrated = 0
    for user in list_all_users(limit=100000, offset=0):
        email = (user.get("username") or user.get("email") or "").strip()
        if not email:
            continue
        account = ensure_account(email)
        ensure_default_student(account["id"])
        migrated += 1
    print(f"Migrated {migrated} accounts")


if __name__ == "__main__":
    main()
