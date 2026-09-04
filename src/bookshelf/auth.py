import hashlib
import random
import time


def gen_salt():
    return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(32))


def hash_and_salt(password, salt):
    return hashlib.sha512(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()


def get_7_days_from_now():
    return str(int(time.time()) + (7 * 1000 * 60 * 24))
