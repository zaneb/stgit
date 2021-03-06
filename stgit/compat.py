import os

# PEP-540 (Add a new UTF-8 mode) makes a compelling argument for Python
# programs making special effort to work around misconfigured locale
# settings. This largely boils down to treating incoming byte sequences,
# i.e. command line arguments and environment variables, as UTF-8.
#
# This is specifically relevant when the POSIX (aka C) locale is in effect.
#
# https://www.python.org/dev/peps/pep-0540/
#
# The following functions help achieve this goal by using UTF-8 as a fallback
# encoding when the nominal encoding (sys.getfilesystemencoding()) fails.


def fsdecode_utf8(b):
    if isinstance(b, bytes):
        try:
            return os.fsdecode(b)
        except UnicodeDecodeError:
            return b.decode('utf-8')
    else:
        return os.fsencode(b).decode('utf-8')


def fsencode_utf8(s):
    try:
        return os.fsencode(s)
    except UnicodeEncodeError:
        return s.encode('utf-8')


def environ_get(key, default=None):
    s = os.environ.get(key, default)
    if s is default:
        return default
    else:
        return s.encode('utf-8', 'surrogateescape').decode('utf-8')


def decode_utf8_with_latin1(input, errors='strict'):
    """Decode utf-8 bytes with possible latin-1 encoded bytes.

    There are cases where encoded byte streams may nominally be utf-8 encoded,
    but contain stray latin-1 (iso8859-1) characters. The input bytes are
    decoded as utf-8, but with any non-utf-8 byte sequences decoded as latin-1.

    This is the decode strategy employed by git when decoding utf-8 email
    bodies.

    """
    s = ''
    while True:
        try:
            s += input.decode('utf-8', 'strict')
        except UnicodeDecodeError as e:
            _, _, start, end, _ = e.args
            s += input[:start].decode('utf-8')
            s += input[start:end].decode('latin1')
            input = input[end:]
        else:
            break
    return s
