from bookshelf.auth import gen_salt, hash_and_salt


def test_hash_and_salt_is_deterministic():
    password = "my_password"
    salt = "fixed_salt"
    assert hash_and_salt(password, salt) == hash_and_salt(password, salt)


def test_different_salts_produce_different_hashes():
    password = "my_password"
    salt1 = gen_salt()
    salt2 = gen_salt()
    assert salt1 != salt2
    assert hash_and_salt(password, salt1) != hash_and_salt(password, salt2)


def test_gen_salt_length():
    salt = gen_salt()
    assert len(salt) == 32


def test_gen_salt_alphanumeric():
    salt = gen_salt()
    assert salt.isalnum()


def test_session_ttl_is_30_days():
    import time

    from bookshelf.auth import SESSION_TTL_SECONDS, get_session_expiry
    assert SESSION_TTL_SECONDS == 30 * 24 * 60 * 60
    assert abs(get_session_expiry() - (int(time.time()) + SESSION_TTL_SECONDS)) <= 2
    assert isinstance(get_session_expiry(), int)


def test_old_name_uses_real_ttl():
    import time

    from bookshelf.auth import SESSION_TTL_SECONDS, get_7_days_from_now
    assert int(get_7_days_from_now()) - int(time.time()) <= SESSION_TTL_SECONDS + 2


def test_gen_authtoken_is_random_and_fits_column():
    from bookshelf.auth import gen_authtoken
    a, b = gen_authtoken(), gen_authtoken()
    assert a != b
    assert len(a) <= 100


def test_mint_session():
    from unittest.mock import MagicMock

    from bookshelf.auth import mint_session
    db = MagicMock()
    db.update_user_authtoken.return_value = {"username": "alice", "goodreads_id": "7"}
    session = mint_session(db, "alice")
    assert session["username"] == "alice" and session["goodreads_id"] == "7"
    _, token, expiry = db.update_user_authtoken.call_args[0]
    assert token == session["authtoken"] and expiry == session["expiry"]
    db.update_user_authtoken.return_value = False
    assert mint_session(db, "alice") is None
