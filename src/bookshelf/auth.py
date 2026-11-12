import hashlib
import secrets
import time

# Lifetime of a site session (username + authtoken pair), for password AND OAuth logins.
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def gen_salt():
    """32 random alphanumeric characters from a cryptographic RNG."""
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ''.join(secrets.choice(alphabet) for _ in range(32))


def gen_authtoken():
    """URL-safe session token (43 chars, fits the VARCHAR(100) column)."""
    return secrets.token_urlsafe(32)


def hash_and_salt(password, salt):
    return hashlib.sha512(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()


def get_session_expiry():
    """Unix timestamp (int, matching the INT `expiry` column) at which a new session expires."""
    return int(time.time()) + SESSION_TTL_SECONDS


def get_7_days_from_now():
    """Deprecated name kept for compatibility. The old formula was wrong (about 116 days); it now
    returns the real session expiry (SESSION_TTL_SECONDS, 30 days) as an int."""
    return get_session_expiry()


def mint_session(db, username):
    """Create a fresh authtoken + expiry for `username` and store it. Returns
    {username, authtoken, expiry, goodreads_id} or None if the update failed."""
    authtoken = gen_authtoken()
    expiry = get_session_expiry()
    user = db.update_user_authtoken(username, authtoken, expiry)
    if not user:
        return None
    return {
        "username": user["username"],
        "authtoken": authtoken,
        "expiry": expiry,
        "goodreads_id": user.get("goodreads_id"),
    }
