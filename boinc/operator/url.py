import re


def canonicalize_url(url: str) -> str:
    """Reproduce BOINC's own `canonicalize_master_url` (`lib/url.cpp`), which the client applies
    to an account manager's URL before storing it (`client/acct_mgr.cpp`) — so what
    `boinccmd --acct_mgr info` reports back is already in this form. Comparing two URLs through
    this function is therefore comparing them exactly the way the client itself would.

    Rules, read from the C++: no scheme becomes `http`; any scheme that is not `https` also
    becomes `http`; repeated slashes collapse to one; a trailing slash is always appended; only
    the host is lower-cased, never the path.
    """
    scheme_end = url.find('://')
    if scheme_end == -1:
        is_https = False
        rest = url
    else:
        is_https = url[:scheme_end].lower() == 'https'
        rest = url[scheme_end + 3:]

    rest = re.sub(r'/{2,}', '/', rest)

    if not rest.endswith('/'):
        rest += '/'

    host, separator, remainder = rest.partition('/')
    rest = host.lower() + separator + remainder

    return f'http{"s" if is_https else ""}://{rest}'
