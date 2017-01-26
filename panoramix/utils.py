import os
import hashlib
import locale
import itertools
import base64
import random

system_random = random.SystemRandom()

ENCODING = locale.getpreferredencoding() or 'UTF-8'


def hash_string(s):
    return hashlib.sha256(s).hexdigest()


def show_serial(serial):
    s = "" if serial is None else str(serial)
    s += "|"
    return s


def hash_message(text, sender, recipient, serial):
    hasher = hashlib.sha256()
    hasher.update(show_serial(serial))
    hasher.update(from_unicode(text))
    hasher.update(sender)
    hasher.update(recipient)
    return hasher.hexdigest()


def from_unicode(s):
    if type(s) is unicode:
        return s.encode(ENCODING)
    return s


def to_unicode(s):
    if type(s) is unicode:
        return s
    return unicode(s, ENCODING)


def int_to_unicode(i):
    return unicode('%x' % i)


def unicode_to_int(u):
    return int(u, base=16)


def unzip(lst):
    aa = []
    bb = []
    for a, b in lst:
        aa.append(a)
        bb.append(b)
    return aa, bb


def with_recipient(messages, default=None):
    return zip(itertools.repeat(default), messages)


def generate_random_key():
    s = os.urandom(32)
    return base64.urlsafe_b64encode(s).rstrip('=')


def secure_shuffle(lst):
    random.shuffle(lst, random=system_random.random)
