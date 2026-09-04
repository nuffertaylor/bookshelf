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
