from cStringIO import StringIO


def to_canonical(obj, out=None):
    toplevel = 0
    if out is None:
        toplevel = 1
        out = StringIO()
    if isinstance(obj, basestring):
        if isinstance(obj, unicode):
            obj = obj.encode('utf-8')
        z = len(obj)
        x = "%x" % z
        w = ("%02x" % len(x))[:2]
        out.write("%s%s_" % (w, x))
        out.write(obj)
    elif isinstance(obj, int) or isinstance(obj, long):
        s = "%x" % obj
        z = len(s)
        x = "%x" % z
        w = ("%02x" % len(x))[:2]
        out.write("%s%s0%s" % (w, x, s))
    elif isinstance(obj, dict):
        out.write('{\x0a')
        cobj = {}
        for k, v in obj.iteritems():
            if not isinstance(k, str):
                if isinstance(k, unicode):
                    k = k.encode('utf-8')
                elif isinstance(k, int) or isinstance(k, long):
                    k = str(k)
                else:
                    m = "Unsupported dict key type '%s'" % (type(k),)
            cobj[k] = v
        del obj
        keys = cobj.keys()
        keys.sort()
        prev = None
        for k in keys:
            if prev is not None:
                out.write(',\x0a')
            if k == prev:
                tail = '...' if len(k) > 64 else ''
                m = "duplicate key '%s' in dict" % (k[:64] + tail,)
                raise AssertionError(m)
            to_canonical(k, out=out)
            out.write(': ')
            to_canonical(cobj[k], out=out)
            prev = k
        out.write('}\x0a')
    elif isinstance(obj, list) or isinstance(obj, tuple):
        out.write('[\x0a')
        iterobj = iter(obj)
        for o in iterobj:
            to_canonical(o, out=out)
            break
        for o in iterobj:
            out.write(',\x0a')
            to_canonical(o, out=out)
        out.write(']\x0a')
    elif obj is None:
        out.write('null')
    else:
        m = "to_canonical: invalid object type '%s'" % (type(obj),)
        raise AssertionError(m)

    if toplevel:
        out.seek(0)
        return out.read()


def from_canonical(inp, unicode_strings=0, s=''):
    if isinstance(inp, str):
        inp = StringIO(inp)

    read = inp.read
    if not s:
        s = read(2)

    if s == 'nu':
        s += read(2)
        if s == 'null':
            return None
        else:
            m = ("byte %d: invalid token '%s' instead of 'null'"
                % (inp.tell(), s))
            raise ValueError(m)

    if s == '[\x0a':
        obj = []
        append = obj.append
        while 1:
            s = read(2)
            if not s:
                m = "byte %d: eof within a list" % inp.tell()
                raise ValueError(m)

            if s == ']\x0a':
                return obj

            item = from_canonical(inp, unicode_strings=unicode_strings, s=s)
            append(item)

            s = read(2)
            if s == ']\x0a':
                return obj

            if s != ',\x0a':
                m = ("byte %d: in list: illegal token '%s' instead of ',\\n'"
                    % (inp.tell(), s))
                raise ValueError(m)

    if s == '{\x0a':
        obj = {}
        while 1:
            s = read(2)
            if not s:
                m = "byte %d: eof within dict" % inp.tell()
                raise ValueError(m)

            if s == '}\x0a':
                return obj

            key = from_canonical(inp, unicode_strings=unicode_strings, s=s)
            s = read(2)
            if s != ': ':
                m = ("byte %d: invalid token '%s' instead of ': '"
                    % (inp.tell(), s))
                raise ValueError(m)

            value = from_canonical(inp, unicode_strings=unicode_strings)
            obj[key] = value  # allow key TypeError rise through

            s = read(2)
            if not s:
                m = "byte %d: eof inside dict" % inp.tell()
                raise ValueError(m)

            if s == '}\x0a':
                return obj

            if s != ',\x0a':
                m = ("byte %d: illegal token '%s' in dict instead of ',\\n'"
                    % (inp.tell(), s))
                raise ValueError(m)

    w = int(s, 16)
    s = read(w)
    if len(s) != w:
        m = "byte %d: eof while reading header size %d" % (inp.tell(), w)
        raise ValueError(m)

    z = int(s, 16)
    c = read(1)
    if not c:
        m = "byte %d: eof while reading object tag" % inp.tell()
        raise ValueError(m)

    s = read(z)
    if len(s) != z:
        m = "byte %d: eof while reading object size %d" % (inp.tell(), z)
        raise ValueError(m)

    if c == '_':
        if unicode_strings:
            try:
                s = s.decode('utf-8')
            except UnicodeDecodeError:
                pass
        return s
    elif c == '0':
        num = int(s, 16)
        return num
    else:
        m = "byte %d: invalid object tag '%d'" % (inp.tell()-z, c)
        raise ValueError(m)


def from_unicode_canonical(inp):
    if isinstance(inp, unicode):
        inp = inp.encode('utf-8')
    return from_canonical(inp, unicode_strings=True)
