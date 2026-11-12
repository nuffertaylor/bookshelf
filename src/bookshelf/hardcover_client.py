"""Hardcover OAuth + GraphQL client (stdlib urllib only).

All network traffic goes through `_request`, the single function tests patch.

Refresh tokens rotate on every use and a double use revokes the whole chain, so:
  - refresh only under a row lock in a real transaction (get_valid_access_token),
  - persist the rotated refresh token before the new access token is used,
  - never retry a refresh; any failure marks the connection needs_reauth.

Env: HARDCOVER_CLIENT_ID, HARDCOVER_REDIRECT_URI, and the client secret from either
HARDCOVER_CLIENT_SECRET (local dev) or HARDCOVER_SECRET_ARN (Secrets Manager, prod).
"""
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from bookshelf import token_crypto

ISSUER = "https://api.hardcover.app"
DEFAULT_ENDPOINTS = {
    "authorization_endpoint": "https://hardcover.app/oauth2/authorize",
    "token_endpoint": ISSUER + "/oauth2/token",
    "revocation_endpoint": ISSUER + "/oauth2/revoke",
}
DISCOVERY_URL = ISSUER + "/.well-known/oauth-authorization-server"
GRAPHQL_URL = ISSUER + "/v1/graphql"
_ALLOWED_ENDPOINT_PREFIXES = ("https://api.hardcover.app/", "https://hardcover.app/")

# User sign-in scopes (Phase 0 spike, plan section 3b). read:catalog is only for the backfill script.
USER_SCOPE = "read:me:email read:library read:lists openid"

STATE_TTL_SECONDS = 600
REFRESH_SKEW_SECONDS = 60
TOKEN_TIMEOUT = 15
GRAPHQL_TIMEOUT = 25

_endpoints = None
_client_secret = None


class HardcoverError(Exception):
    def __init__(self, message, status=None, error=None):
        super().__init__(message)
        self.status = status
        self.error = error


class HardcoverUnauthorized(HardcoverError):
    """GraphQL returned 401: token revoked or reset (the API is in beta)."""


class HardcoverRateLimited(HardcoverError):
    def __init__(self, message, retry_after=None):
        super().__init__(message, status=429)
        self.retry_after = retry_after


class HardcoverReauthRequired(Exception):
    """The user must run the OAuth flow again. The site session stays valid."""


# ---- low-level HTTP --------------------------------------------------------------------------

def _request(url, data=None, headers=None, method="POST", timeout=TOKEN_TIMEOUT):
    """The only function that touches the network. Returns (status, headers_dict, body_text) for
    ANY HTTP status (including 4xx/5xx). Raises HardcoverError(status=None) on timeouts and
    connection failures."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()), e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise HardcoverError("network error talking to Hardcover: " + type(e).__name__) from e


def _json_or_empty(text):
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


# ---- configuration ---------------------------------------------------------------------------

def get_client_id():
    return os.getenv("HARDCOVER_CLIENT_ID", "")


def get_redirect_uri():
    return os.getenv("HARDCOVER_REDIRECT_URI", "")


def get_client_secret():
    """Local dev: HARDCOVER_CLIENT_SECRET. Prod: fetched once per cold start from Secrets Manager
    (HARDCOVER_SECRET_ARN). The value is never logged."""
    global _client_secret
    if _client_secret:
        return _client_secret
    secret = os.getenv("HARDCOVER_CLIENT_SECRET")
    if not secret:
        arn = os.getenv("HARDCOVER_SECRET_ARN")
        if not arn:
            raise RuntimeError("Hardcover client secret is not configured")
        import boto3
        raw = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
        secret = raw
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("client_secret"):
                secret = parsed["client_secret"]
        except ValueError:
            pass
    _client_secret = secret
    return _client_secret


def get_endpoints():
    """OAuth endpoints from the discovery document (cached per container), falling back to the
    hardcoded constants if discovery fails. Discovered URLs must stay on Hardcover's hosts so the
    client secret can never be sent elsewhere."""
    global _endpoints
    if _endpoints is not None:
        return _endpoints
    endpoints = dict(DEFAULT_ENDPOINTS)
    try:
        status, _, body = _request(DISCOVERY_URL, method="GET", timeout=5)
        doc = _json_or_empty(body) if status == 200 else {}
        if doc.get("issuer") == ISSUER:
            for key in DEFAULT_ENDPOINTS:
                value = doc.get(key)
                if isinstance(value, str) and value.startswith(_ALLOWED_ENDPOINT_PREFIXES):
                    endpoints[key] = value
    except HardcoverError:
        pass
    _endpoints = endpoints
    return _endpoints


def _basic_auth_header():
    raw = (get_client_id() + ":" + get_client_secret()).encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


# ---- PKCE / authorize URL --------------------------------------------------------------------

def code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_pkce():
    """(verifier, challenge). 32 random bytes -> 43 base64url chars (RFC 7636 allows 43-128)."""
    verifier = secrets.token_urlsafe(32)
    return verifier, code_challenge(verifier)


def generate_state():
    return secrets.token_urlsafe(24)


def build_authorize_url(state, challenge, scope=USER_SCOPE):
    params = {
        "response_type": "code",
        "client_id": get_client_id(),
        "redirect_uri": get_redirect_uri(),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": scope,
    }
    return get_endpoints()["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)


# ---- token endpoint --------------------------------------------------------------------------

def _token_call(form):
    status, _, body = _request(
        get_endpoints()["token_endpoint"],
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=TOKEN_TIMEOUT,
    )
    doc = _json_or_empty(body)
    if status != 200:
        raise HardcoverError("token endpoint returned HTTP " + str(status), status=status, error=doc.get("error"))
    if not doc.get("access_token"):
        raise HardcoverError("token endpoint response had no access_token", status=status)
    return doc


def exchange_code(code, code_verifier):
    """Authorization-code exchange. redirect_uri must exactly match the one sent to /authorize."""
    return _token_call({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": get_redirect_uri(),
        "code_verifier": code_verifier,
    })


def refresh(refresh_token):
    """One refresh attempt. NEVER retry this call: the token is single-use. No scope is passed,
    so the original scopes are reused."""
    return _token_call({"grant_type": "refresh_token", "refresh_token": refresh_token})


def revoke(token, token_type_hint="refresh_token"):
    """Best-effort revoke. Returns True on HTTP 200."""
    status, _, _ = _request(
        get_endpoints()["revocation_endpoint"],
        data=urllib.parse.urlencode({"token": token, "token_type_hint": token_type_hint}).encode("utf-8"),
        headers={"Authorization": _basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"},
        timeout=TOKEN_TIMEOUT,
    )
    return status == 200


def token_expiry(token_response, now=None):
    now = int(time.time()) if now is None else now
    return now + int(token_response.get("expires_in") or 604800)


# ---- GraphQL ---------------------------------------------------------------------------------

def graphql(query, variables, access_token):
    """POST a GraphQL query. Returns the `data` dict. Raises HardcoverUnauthorized on 401,
    HardcoverRateLimited on 429, HardcoverError otherwise."""
    status, headers, body = _request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=GRAPHQL_TIMEOUT,
    )
    if status == 401:
        raise HardcoverUnauthorized("Hardcover rejected the access token", status=401)
    if status == 429:
        lowered = {k.lower(): v for k, v in headers.items()}
        raise HardcoverRateLimited("Hardcover rate limit reached", retry_after=lowered.get("retry-after"))
    doc = _json_or_empty(body)
    if status != 200:
        raise HardcoverError("GraphQL returned HTTP " + str(status), status=status)
    if doc.get("errors"):
        first = doc["errors"][0] if isinstance(doc["errors"], list) and doc["errors"] else {}
        message = first.get("message", "GraphQL error") if isinstance(first, dict) else "GraphQL error"
        raise HardcoverError(message, status=status)
    return doc.get("data") or {}


def first_me(data):
    """`me` returns an ARRAY. Returns me[0] (also tolerates a bare object), or None if empty."""
    me = data.get("me") if isinstance(data, dict) else None
    if isinstance(me, list):
        return me[0] if me else None
    return me or None


ME_QUERY = "query { me { id username name email } }"


def fetch_me(access_token):
    me = first_me(graphql(ME_QUERY, {}, access_token))
    if not me or me.get("id") is None:
        raise HardcoverError("Hardcover returned no profile for this token")
    return me


# ---- stored-token lifecycle ------------------------------------------------------------------

def get_valid_access_token(db, username, now=None):
    """Plaintext access token for `username`, refreshing under a row lock if it expires within 60 s.
    Raises HardcoverReauthRequired if the account is not linked, needs re-auth, or the refresh fails."""
    now = int(time.time()) if now is None else now
    conn = db.get_hardcover_connection(username)
    if not conn or conn["needs_reauth"]:
        raise HardcoverReauthRequired("hardcover not linked or needs re-authorization")
    if conn["access_expires_at"] - now > REFRESH_SKEW_SECONDS:
        return token_crypto.decrypt(username, conn["access_token_enc"])

    reauth = False
    access_token = None
    with db.transaction() as cur:
        # A concurrent caller blocks on this lock, then sees the already-refreshed token below.
        locked = db.lock_hardcover_connection(cur, username)
        if not locked or locked["needs_reauth"]:
            raise HardcoverReauthRequired("hardcover not linked or needs re-authorization")
        if locked["access_expires_at"] - now > REFRESH_SKEW_SECONDS:
            return token_crypto.decrypt(username, locked["access_token_enc"])

        refresh_token = token_crypto.decrypt(username, locked["refresh_token_enc"])
        try:
            tokens = refresh(refresh_token)
            new_refresh = tokens.get("refresh_token")
            if not new_refresh:
                raise HardcoverError("refresh response had no refresh_token")
        except HardcoverError as e:
            # invalid_grant / 401 / timeout / 5xx: the old token may or may not be spent. Never retry.
            print("hardcover refresh failed for a user: status=" + str(e.status) + " error=" + str(e.error))
            db.set_hardcover_needs_reauth(cur, username)
            reauth = True
        else:
            access_token = tokens["access_token"]
            db.save_hardcover_tokens(
                cur, username,
                token_crypto.encrypt(username, access_token),
                token_crypto.encrypt(username, new_refresh),
                token_expiry(tokens, now),
                tokens.get("scope") or locked["scopes"],
            )
    # The transaction has committed (new refresh token persisted) before the access token is used.
    if reauth:
        raise HardcoverReauthRequired("hardcover refresh failed")
    return access_token


def user_graphql(db, username, query, variables):
    """Run a GraphQL query as `username`. A 401 marks the connection needs_reauth and raises
    HardcoverReauthRequired."""
    token = get_valid_access_token(db, username)
    try:
        return graphql(query, variables, token)
    except HardcoverUnauthorized:
        db.mark_hardcover_needs_reauth(username)
        raise HardcoverReauthRequired("hardcover rejected the access token") from None
