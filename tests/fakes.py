"""In-memory stand-in for CockroachDAO covering the methods the Hardcover code uses."""
import json
import time
from contextlib import contextmanager


class FakeDB:
    def __init__(self):
        self.users = {}          # username -> dict (same keys as get_user)
        self.connections = {}    # username -> dict
        self.states = {}         # state -> dict
        self.fail_create_for = set()   # usernames for which create_oauth_user returns False (race)
        self.spines = []
        self.reauth_marked = []

    # users
    def add_legacy_user(self, username, email=None, banned=False, password=None, salt="salt", authtoken="tok"):
        from bookshelf.auth import hash_and_salt
        self.users[username] = {
            "username": username,
            "hashedPassword": hash_and_salt(password, salt) if password else None,
            "email": email, "authtoken": authtoken, "expiry": int(time.time()) + 1000,
            "salt": salt if password else None, "ip": None, "banned": banned, "goodreads_id": None,
        }

    def get_user(self, username):
        return self.users.get(username, False)

    def validate_username_authtoken(self, username, authtoken):
        u = self.users.get(username)
        return bool(u and u["authtoken"] == authtoken and int(time.time()) <= int(u["expiry"]) and not u["banned"])

    def update_user_authtoken(self, username, authtoken, expiry):
        if username not in self.users:
            return False
        self.users[username].update(authtoken=authtoken, expiry=expiry)
        return self.users[username]

    def username_taken(self, username):
        return any(u.lower() == username.lower() for u in self.users)

    def email_taken(self, email):
        return any((u["email"] or "").lower() == email.lower() for u in self.users.values())

    def create_oauth_user(self, username, email, authtoken, expiry):
        if username in self.fail_create_for or username in self.users:
            self.fail_create_for.discard(username)
            return False
        self.users[username] = {
            "username": username, "hashedPassword": None, "email": email, "authtoken": authtoken,
            "expiry": expiry, "salt": None, "ip": None, "banned": False, "goodreads_id": None,
        }
        return True

    def delete_user(self, username):
        self.users.pop(username, None)
        self.connections.pop(username, None)
        return True

    # connections
    def get_hardcover_connection(self, username):
        c = self.connections.get(username)
        return dict(c) if c else False

    def get_user_by_hardcover_id(self, hardcover_id):
        for c in self.connections.values():
            if c["hardcover_id"] == hardcover_id:
                return self.users.get(c["username"], False)
        return False

    def upsert_hardcover_connection(self, username, hardcover_id, hardcover_username, access_token_enc,
                                    refresh_token_enc, access_expires_at, scopes):
        for c in self.connections.values():
            if c["hardcover_id"] == hardcover_id and c["username"] != username:
                return False
        self.connections[username] = {
            "username": username, "hardcover_id": hardcover_id, "hardcover_username": hardcover_username,
            "access_token_enc": access_token_enc, "refresh_token_enc": refresh_token_enc,
            "access_expires_at": access_expires_at, "scopes": scopes, "needs_reauth": False,
        }
        return True

    def mark_hardcover_needs_reauth(self, username):
        self.connections[username]["needs_reauth"] = True
        self.reauth_marked.append(username)
        return True

    @contextmanager
    def transaction(self):
        yield object()

    def lock_hardcover_connection(self, cur, username):
        return self.get_hardcover_connection(username)

    def save_hardcover_tokens(self, cur, username, access_token_enc, refresh_token_enc, access_expires_at, scopes):
        self.connections[username].update(
            access_token_enc=access_token_enc, refresh_token_enc=refresh_token_enc,
            access_expires_at=access_expires_at, scopes=scopes, needs_reauth=False)

    def set_hardcover_needs_reauth(self, cur, username):
        self.connections[username]["needs_reauth"] = True

    # oauth state
    def delete_expired_oauth_states(self, now):
        self.states = {k: v for k, v in self.states.items() if v["expires_at"] >= now}
        return True

    def create_oauth_state(self, state, code_verifier, mode, username, created_at, expires_at):
        self.states[state] = {"code_verifier": code_verifier, "mode": mode, "username": username,
                              "expires_at": expires_at, "used": False}
        return True

    def consume_oauth_state(self, state, now):
        s = self.states.get(state)
        if not s or s["used"] or s["expires_at"] <= now:
            return None
        s["used"] = True
        return {"code_verifier": s["code_verifier"], "mode": s["mode"], "username": s["username"]}

    # spines
    def get_spines_batch_by_title_author(self, book_list):
        return self.spines


class FakeHardcover:
    """Replacement for hardcover_client._request. Queue responses per endpoint as
    (status, body_dict[, headers]); the last queued response repeats if the queue runs out."""

    def __init__(self):
        self.calls = []
        self.token = []
        self.graphql = []
        self.revoke = [(200, {})]

    @staticmethod
    def _next(queue):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        status, body = item[0], item[1]
        headers = item[2] if len(item) > 2 else {}
        return status, headers, body if isinstance(body, str) else json.dumps(body)

    def __call__(self, url, data=None, headers=None, method="POST", timeout=15):
        self.calls.append({"url": url, "data": data, "headers": headers or {}, "method": method})
        if url.endswith("/oauth2/token"):
            return self._next(self.token)
        if url.endswith("/oauth2/revoke"):
            return self._next(self.revoke)
        if url.endswith("/v1/graphql"):
            return self._next(self.graphql)
        raise AssertionError("unexpected URL " + url)

    def calls_to(self, suffix):
        return [c for c in self.calls if c["url"].endswith(suffix)]


def token_response(access="hc_at_new", refresh="hc_rt_new", expires_in=604800, scope="read:me:email read:library"):
    return {"access_token": access, "refresh_token": refresh, "expires_in": expires_in,
            "scope": scope, "token_type": "Bearer"}
