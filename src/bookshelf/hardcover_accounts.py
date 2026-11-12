"""Creating bookshelf accounts for new Hardcover users."""
import re

from bookshelf.auth import gen_authtoken, get_session_expiry

MAX_USERNAME_LEN = 50
MAX_ATTEMPTS = 50
MAX_EMAIL_LEN = 255


class AccountCreationError(Exception):
    pass


def sanitize_username(name):
    """Restrict to [A-Za-z0-9_.-] (anything else becomes '_') and at most 50 characters."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name or "").strip())[:MAX_USERNAME_LEN]
    return cleaned or "hardcover_user"


def _candidate(base, attempt):
    """attempt 1 -> base, 2 -> base-2, 3 -> base-3 ... always within MAX_USERNAME_LEN."""
    if attempt == 1:
        return base
    suffix = "-" + str(attempt)
    return base[:MAX_USERNAME_LEN - len(suffix)] + suffix


def _clean_email(email):
    if not isinstance(email, str):
        return None
    email = email.strip()
    if not email or len(email) > MAX_EMAIL_LEN:
        return None
    return email


def create_account(db, hardcover_username, email):
    """Create a password-less account named after the Hardcover username (case-insensitively unique,
    -2, -3 ... suffix on clash). The email is stored only if no existing account has it; accounts are
    NEVER matched or merged by username or email. Returns {username, authtoken, expiry}."""
    base = sanitize_username(hardcover_username)
    email = _clean_email(email)
    if email and db.email_taken(email):
        email = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        candidate = _candidate(base, attempt)
        for _ in range(2):
            if db.username_taken(candidate):
                break
            authtoken = gen_authtoken()
            expiry = get_session_expiry()
            if db.create_oauth_user(candidate, email, authtoken, expiry):
                return {"username": candidate, "authtoken": authtoken, "expiry": expiry}
            # The DAO swallows errors, so False means "taken by a concurrent insert" or an email
            # clash. Drop the email if that was the cause and retry this name once; else next suffix.
            if email and db.email_taken(email):
                email = None
                continue
            break
    raise AccountCreationError("could not find a free username")
