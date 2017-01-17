import hashlib
import locale
import itertools

ENCODING = locale.getpreferredencoding() or 'UTF-8'


def hash_string(s):
    return hashlib.sha256(s).hexdigest()


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
