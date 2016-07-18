# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import sys
import collections
import json
import datetime
import codecs
import itertools
import keyword

try:
    import regex as re
    WHITESPACE_RE = re.compile(r'\p{IsPattern_White_Space}+', re.UNICODE)
except ImportError:
    import re
    WHITESPACE_RE = re.compile(r'\s+', re.UNICODE)
RE_FLAGS = re.UNICODE | re.MULTILINE


PY3 = sys.version_info[0] >= 3
PY33 = PY3 and sys.version_info[1] >= 3

if PY3:
    strtype = str
    basestring = None
    unicode = None
    if PY33:
        from collections import abc
        Mapping = abc.Mapping
    else:
        Mapping = collections.Mapping
    zip_longest = itertools.zip_longest
    import builtins
else:
    strtype = basestring  # noqa
    Mapping = collections.Mapping
    zip_longest = itertools.izip_longest
    import __builtin__ as builtins
assert builtins


def info(*args, **kwargs):
    kwargs['file'] = sys.stderr
    if PY3:
        print(*args, **kwargs)
    else:
        print(*(a.encode('utf-8') for a in args), **kwargs)


def debug(*args, **kwargs):
    kwargs['file'] = sys.stderr
    print(*args, **kwargs)


def warning(*args, **kwargs):
    kwargs['file'] = sys.stderr
    print('WARNING:', *args, **kwargs)


def is_list(o):
    return type(o) == list


def to_list(o):
    if o is None:
        return []
    elif isinstance(o, list):
        return o
    else:
        return [o]


def compress_seq(seq):
    seen = set()
    result = []
    for x in seq:
        if x not in seen:
            result.append(x)
            seen.add(x)
    return result


def ustr(s):
    if PY3:
        return str(s)
    elif isinstance(s, unicode):
        return s
    elif isinstance(s, str):
        return unicode(s, 'utf-8')
    else:
        return ustr(s.__str__())  # FIXME: last case resource!  We don't know unicode, period.


def urepr(obj):
    return ustr(repr(obj)).lstrip('u')


ESCAPE_SEQUENCE_RE = re.compile(
    r'''
    ( \\U........      # 8-digit Unicode escapes
    | \\u....          # 4-digit Unicode escapes
    | \\x..            # 2-digit Unicode escapes
    | \\[0-7]{1,3}     # Octal character escapes
    | \\N\{[^}]+\}     # Unicode characters by name
    | \\[\\'"abfnrtv]  # Single-character escapes
    )''',
    re.UNICODE | re.VERBOSE
)


def eval_escapes(s):
    """
    Given a string, evaluate escape sequences starting with backslashes as
    they would be evaluated in Python source code. For a list of these
    sequences, see: https://docs.python.org/3/reference/lexical_analysis.html

    This is not the same as decoding the whole string with the 'unicode-escape'
    codec, because that provides no way to handle non-ASCII characters that are
    literally present in the string.
    """
    # by Rob Speer

    def decode_match(match):
        return codecs.decode(match.group(0), 'unicode-escape')

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)


def simplify_list(x):
    if isinstance(x, list) and len(x) == 1:
        return simplify_list(x[0])
    return x


def isiter(value):
    return (
        isinstance(value, collections.Iterable) and
        not isinstance(value, strtype)
    )


def trim(text, tabwidth=4):
    """
    Trim text of common, leading whitespace.

    Based on the trim algorithm of PEP 257:
        http://www.python.org/dev/peps/pep-0257/
    """
    if not text:
        return ''
    lines = text.expandtabs(tabwidth).splitlines()
    maxindent = len(text)
    indent = maxindent
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    trimmed = [line[indent:].rstrip() for line in lines]
    i = 0
    while i < len(trimmed) and not trimmed[i]:
        i += 1
    return '\n'.join(trimmed[i:])


def indent(text, indent=1, multiplier=4):
    """ Indent the given block of text by indent*4 spaces
    """
    if text is None:
        return ''
    text = ustr(text)
    if indent >= 0:
        sindent = ' ' * multiplier * indent
        text = '\n'.join((sindent + t).rstrip() for t in text.splitlines())
    return text


def format_if(fmt, values):
    return fmt % values if values else ''


def notnone(value, default=None):
    return value if value is not None else default


def timestamp():
    return '.'.join('%2.2d' % t for t in datetime.datetime.utcnow().utctimetuple()[:-2])


def asjson(obj, seen=None):
    if isinstance(obj, collections.Mapping) or isiter(obj):
        # prevent traversal of recursive structures
        if seen is None:
            seen = set()
        elif id(obj) in seen:
            return '__RECURSIVE__'
        seen.add(id(obj))

    if hasattr(obj, '__json__') and type(obj) is not type:
        return obj.__json__()
    elif isinstance(obj, collections.Mapping):
        result = collections.OrderedDict()
        for k, v in obj.items():
            try:
                result[asjson(k, seen)] = asjson(v, seen)
            except TypeError:
                debug('Unhashable key?', type(k), str(k))
                raise
        return result
    elif isiter(obj):
        return [asjson(e, seen) for e in obj]
    else:
        return obj


def asjsons(obj):
    return json.dumps(asjson(obj), indent=2)


def prune_dict(d, predicate):
    """ Remove all items x where predicate(x, d[x]) """

    keys = [k for k, v in d.items() if predicate(k, v)]
    for k in keys:
        del d[k]


def safe_name(name):
    if keyword.iskeyword(name):
        return name + '_'
    return name


def chunks(iterable, size, fillvalue=None):
    return zip_longest(*[iter(iterable)] * size, fillvalue=fillvalue)


def extend_list(x, n, default=None):
    def _null():
        pass
    default = default or _null

    missing = max(0, 1 + n - len(x))
    x.extend(default() for _ in range(missing))


def generic_main(custom_main, ParserClass, name='Unknown'):
    import argparse
    import sys

    class ListRules(argparse.Action):
        def __call__(self, parser, namespace, values, option_string):
            print('Rules:')
            for r in ParserClass.rule_list():
                print(r)
            print()
            sys.exit(0)

    argp = argparse.ArgumentParser(description="Simple parser for %s." % name)
    addarg = argp.add_argument

    addarg('-c', '--color',
           help='use color in traces (requires the colorama library)',
           action='store_true'
           )
    addarg('-l', '--list', action=ListRules, nargs=0,
           help="list all rules and exit")
    addarg('-n', '--no-nameguard', action='store_true',
           dest='no_nameguard',
           help="disable the 'nameguard' feature")
    addarg('-t', '--trace', action='store_true',
           help="output trace information")
    addarg('-w', '--whitespace', type=str, default=None,
           help="whitespace specification")
    addarg('file',
           metavar="FILE",
           help="the input file to parse")
    addarg('startrule',
           metavar="STARTRULE",
           nargs='?',
           help="the start rule for parsing",
           default='start')

    args = argp.parse_args()
    try:
        return custom_main(
            args.file,
            args.startrule,
            trace=args.trace,
            whitespace=args.whitespace,
            nameguard=not args.no_nameguard,
            colorize=args.color
        )
    except KeyboardInterrupt:
        pass
