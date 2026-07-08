#!/usr/bin/env python3
import os
import hmac
import hashlib
import time

SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")
MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(60*60*24*30)))  # 30 days


def generate_token(username: str) -> str:
    ts = str(int(time.time()))
    msg = f"{username}:{ts}".encode('utf-8')
    sig = hmac.new(SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()
    return f"{username}|{ts}|{sig}"


def verify_token(token: str) -> str:
    try:
        parts = token.split('|')
        if len(parts) != 3:
            return None
        username, ts, sig = parts
        msg = f"{username}:{ts}".encode('utf-8')
        expected = hmac.new(SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        if int(time.time()) - int(ts) > MAX_AGE:
            return None
        return username
    except Exception:
        return None
