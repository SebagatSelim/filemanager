"""One-time codes (OTP) for two-step sign-in and for checking the email address at sign-up.

How it works:
1. new_code() makes a random 6-digit code and keeps only its SHA-256 hash, with an expiry time.
2. The code is emailed to the user (services/mailer.py).
3. check_code() compares what the user typed. After OTP_MAX_ATTEMPTS wrong tries, or after
   OTP_EXPIRES_MIN minutes, the code stops working and the user has to ask for a new one.

Codes are kept in memory (like the failed-login counter in api/auth.py): they only live for a
few minutes, so nothing needs to be saved in the database.
"""
import hashlib
import hmac
import secrets
import threading
import time

from flask import current_app

from ..errors import APIError

_codes: dict[tuple[str, str], dict] = {}   # (purpose, email) -> {hash, expires, attempts, data}
_lock = threading.Lock()


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def new_code(purpose: str, email: str, data: dict | None = None) -> str:
    """Create (or replace) the code for this email. `data` is returned again by check_code()."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    with _lock:
        _codes[(purpose, email)] = {
            "hash": _hash(code),
            "expires": time.time() + current_app.config["OTP_EXPIRES_MIN"] * 60,
            "attempts": 0,
            "data": data or {},
        }
    return code


def pending_data(purpose: str, email: str) -> dict | None:
    """The data saved with a code that is still waiting to be used (None if there is none)."""
    with _lock:
        entry = _codes.get((purpose, email))
        return dict(entry["data"]) if entry else None


def check_code(purpose: str, email: str, code: str) -> dict:
    """Return the saved data if the code is correct, otherwise raise an APIError the UI can show."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    with _lock:
        entry = _codes.get((purpose, email))
        if entry is None:
            raise APIError(400, "CODE_NOT_FOUND", "This code is no longer valid. Please ask for a new code.")
        if time.time() > entry["expires"]:
            _codes.pop((purpose, email), None)
            raise APIError(400, "CODE_EXPIRED", "This code has expired. Please ask for a new code.")
        if not hmac.compare_digest(entry["hash"], _hash(code)):
            entry["attempts"] += 1
            if entry["attempts"] >= current_app.config["OTP_MAX_ATTEMPTS"]:
                _codes.pop((purpose, email), None)
                raise APIError(429, "TOO_MANY_ATTEMPTS", "Too many wrong codes. Please ask for a new code.")
            raise APIError(400, "WRONG_CODE", "That code is not correct. Please check the email and try again.",
                           {"code": "Incorrect code"})
        _codes.pop((purpose, email), None)  # a code works only once
        return entry["data"]


def clear() -> None:
    """Forget every code (used by the tests)."""
    with _lock:
        _codes.clear()
