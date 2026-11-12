import pytest

from bookshelf.hardcover_accounts import AccountCreationError, create_account, sanitize_username
from tests.fakes import FakeDB


def test_clean_username_is_used_as_is():
    db = FakeDB()
    created = create_account(db, "alice", None)
    assert created["username"] == "alice"
    user = db.users["alice"]
    assert user["hashedPassword"] is None and user["salt"] is None and user["banned"] is False


def test_clash_with_legacy_user_is_case_insensitive_and_gets_suffix():
    db = FakeDB()
    db.add_legacy_user("Alice")
    assert create_account(db, "alice", None)["username"] == "alice-2"
    assert create_account(db, "ALICE", None)["username"] == "ALICE-3"


def test_many_clashes_walk_the_suffixes():
    db = FakeDB()
    db.add_legacy_user("bob")
    for n in range(2, 12):
        db.add_legacy_user(f"bob-{n}")
    assert create_account(db, "bob", None)["username"] == "bob-12"


def test_gives_up_after_bounded_attempts():
    db = FakeDB()
    db.add_legacy_user("x")
    for n in range(2, 60):
        db.add_legacy_user(f"x-{n}")
    with pytest.raises(AccountCreationError):
        create_account(db, "x", None)


def test_concurrent_insert_returning_false_retries_next_suffix():
    db = FakeDB()
    db.fail_create_for.add("carol")  # DAO swallowed a unique violation from a racing insert
    assert create_account(db, "carol", None)["username"] == "carol-2"


def test_illegal_characters_are_sanitised_and_length_capped():
    assert sanitize_username("a b/c@d") == "a_b_c_d"
    assert sanitize_username("ünï") == "_n_"
    assert sanitize_username("") == "hardcover_user"
    assert len(sanitize_username("x" * 80)) == 50


def test_suffix_still_fits_in_50_chars():
    db = FakeDB()
    db.add_legacy_user("y" * 50)
    name = create_account(db, "y" * 80, None)["username"]
    assert len(name) == 50 and name.endswith("-2")


def test_email_stored_only_when_unused():
    db = FakeDB()
    db.add_legacy_user("legacy", email="Taylor@Example.com")
    assert create_account(db, "t1", "taylor@example.com")["username"] == "t1"
    assert db.users["t1"]["email"] is None
    assert create_account(db, "t2", "fresh@example.com")["username"] == "t2"
    assert db.users["t2"]["email"] == "fresh@example.com"


def test_email_clash_on_racing_insert_drops_the_email_and_keeps_the_name():
    db = FakeDB()
    real_create = db.create_oauth_user

    def racing(username, email, authtoken, expiry):
        if email:
            db.add_legacy_user("someone", email=email)  # the email appears between check and insert
            return False
        return real_create(username, email, authtoken, expiry)

    db.create_oauth_user = racing
    assert create_account(db, "dana", "dana@example.com")["username"] == "dana"
    assert db.users["dana"]["email"] is None
