import os
from bookshelf.dao.cockroachdb_dao import CockroachDAO
from bookshelf.auth import gen_salt, hash_and_salt, get_7_days_from_now
from bookshelf.http import http_result

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = CockroachDAO(os.getenv('DATABASE_URL'))
    return _db


def lambda_handler(event, context):
    db = _get_db()
    if "requestType" not in event:
        return http_result(400, "No requestType provided")
    if "username" not in event:
        return http_result(403, "invalid input, missing username")
    if "password" not in event:
        return http_result(403, "invalid input, missing password")

    if event["requestType"] == "register":
        if "email" not in event:
            return http_result(403, "invalid input, missing email")
        if "ip" not in event:
            event["ip"] = ""
        return _handle_register(db, event["username"], event["password"], event["email"], event["ip"])
    elif event["requestType"] == "login":
        return _handle_login(db, event["username"], event["password"])
    else:
        return http_result(400, f"'{event['requestType']}' is an invalid requestType")


def _handle_register(db, username, password, email, ip):
    if db.get_user(username):
        return http_result(403, f"username '{username}' is already taken")
    salt = gen_salt()
    hashed_password = hash_and_salt(password, salt)
    authtoken = _register_user(db, username, hashed_password, salt, email, ip)
    return http_result(200, {"username": username, "authtoken": authtoken})


def _handle_login(db, username, password):
    user_data = db.get_user(username)
    if not user_data:
        return http_result(403, f"username '{username}' does not exist")
    if hash_and_salt(password, user_data["salt"]) != user_data["hashedPassword"]:
        return http_result(403, "invalid password")
    expiry = get_7_days_from_now()
    authtoken = gen_salt()
    res = db.update_user_authtoken(username, authtoken, expiry)
    if res:
        return http_result(200, {"username": res["username"], "authtoken": res["authtoken"], "goodreads_id": res["goodreads_id"]})
    return http_result(400, "something went wrong, please try again later.")


def _register_user(db, username, hashed_password, salt, email, ip):
    expiry = get_7_days_from_now()
    authtoken = gen_salt()
    if db.add_user({
        "username": username,
        "hashedPassword": hashed_password,
        "email": email,
        "authtoken": authtoken,
        "expiry": expiry,
        "salt": salt,
        "ip": ip,
    }):
        return authtoken
    return False
