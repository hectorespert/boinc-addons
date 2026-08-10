"""The only place that talks to a BOINC client.

Everything above this module works with plain dicts and never sees that the vendored library is
asyncio-based, so the views and the refresher stay synchronous.
"""

import asyncio
import logging

from pyboinc import init_rpc_client

DEFAULT_PORT = 31416
# BOINC's own client gives up well before this; the point is only that a host which accepts the
# connection and then says nothing cannot hold the refresher forever.
TIMEOUT_SECONDS = 30


class BoincError(Exception):
    """Anything that stopped us reading the client's state, phrased for a user to read."""


class NotConfigured(BoincError):
    pass


class CannotConnect(BoincError):
    pass


class AuthenticationFailed(BoincError):
    pass


def _as_list(value):
    """Normalise a reply that should have been a list.

    The library returns the string "\\n" instead of an empty list when a request has no items --
    a quirk the only other consumer works around at each call site. Doing it once here keeps the
    rest of the code able to assume a list.

    Project replies come back as library objects rather than dicts; they are flattened here so that
    nothing above this module has to know the library exists.
    """
    if not isinstance(value, list):
        return []
    return [item if isinstance(item, dict) else vars(item) for item in value]


async def _collect(host: str, port: int, password: str):
    client = await init_rpc_client(host, password, port)
    try:
        # init_rpc_client connects but does not authenticate, and the query methods below do not
        # check authorisation: against an unauthorised session they return parsed nonsense rather
        # than failing. Checking the return value here is what turns a wrong password into an error
        # the page can explain instead of a silently empty screen.
        if not await client.authorize():
            raise AuthenticationFailed('The BOINC client rejected the password')
        return {
            'cc_status': await client.get_cc_status(),
            'projects': _as_list(await client.get_project_status()),
            'results': _as_list(await client.get_results()),
        }
    finally:
        await client.close()


def read_state(host: str | None, port: int | None, password: str | None) -> dict:
    """Connect, read the client's state and disconnect. Raises BoincError with a readable message."""
    if not host or not password:
        raise NotConfigured('No BOINC client has been configured yet')

    port = port or DEFAULT_PORT
    logging.debug(f'Reading state from {host}:{port}')
    try:
        return asyncio.run(asyncio.wait_for(_collect(host, port, password), TIMEOUT_SECONDS))
    except AuthenticationFailed:
        raise
    except (TimeoutError, OSError, ConnectionError) as error:
        raise CannotConnect(f'Could not reach a BOINC client at {host}:{port}') from error
    except Exception as error:
        # The library raises bare Exceptions and assertion-style errors on malformed replies, so
        # anything unexpected still has to reach the page as a message rather than kill the thread.
        raise BoincError(f'Unexpected reply from the BOINC client at {host}:{port}') from error
