"""The only place that talks to a BOINC client.

Everything above this module works with plain dicts and never sees that the vendored library is
asyncio-based, so the views and the refresher stay synchronous.
"""

import asyncio
import logging

from pyboinc import init_rpc_client
from pyboinc.rpc_client import Mode
from status import describe_activity, describe_mode

DEFAULT_PORT = 31416
# BOINC's own client gives up well before this; the point is only that a host which accepts the
# connection and then says nothing cannot hold the refresher forever.
TIMEOUT_SECONDS = 30
# Acting on a button press is allowed to touch the network, but not for as long as a poll may: this
# runs inside a request, with someone waiting for the page to come back.
ACTION_TIMEOUT_SECONDS = 5

# The mode names this app uses, and the request each one sends.
MODES = {'always': Mode.ALWAYS, 'auto': Mode.AUTO, 'never': Mode.NEVER}
# A duration of zero makes the change permanent: it survives a restart of the BOINC client, rather
# than reverting on its own after a while (`RUN_MODE::set`, client/client_types.cpp:1414).
PERMANENT = 0

# `active_task_state` when a task is actually executing (lib/common_defs.h: PROCESS_EXECUTING).
PROCESS_EXECUTING = 1


class BoincError(Exception):
    """Anything that stopped us reading a client's state, phrased for a user to read."""


class NotConfigured(BoincError):
    pass


class CannotConnect(BoincError):
    pass


class ConnectionRejected(BoincError):
    """The machine answered and then hung up, which means it is running but will not talk to us."""


class AuthenticationFailed(BoincError):
    pass


ERROR_KINDS = {
    NotConfigured: 'not_configured',
    CannotConnect: 'cannot_connect',
    ConnectionRejected: 'rejected',
    AuthenticationFailed: 'auth_failed',
}


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


def _url(value) -> str:
    """A project URL as text.

    The library parses every `project_url` into one of its own objects, which renders as the URL by
    accident of `__str__`. Joining tasks to projects needs a real string.
    """
    return '' if value is None else str(value)


def describe_client(client: dict) -> str:
    return client.get('name') or client.get('host') or 'BOINC client'


def _summarise(results: list, projects: list) -> dict:
    """Turn raw replies into what the page shows: the running tasks, and counts for the rest."""
    names = {_url(project.get('master_url')): project.get('project_name') for project in projects}

    running, queued, ready = [], 0, 0
    for result in results:
        url = _url(result.get('project_url'))
        active = result.get('active_task') or {}
        if active.get('active_task_state') == PROCESS_EXECUTING:
            running.append({
                # Kept for the row's `title`: BOINC's own identifiers say nothing to a reader, but
                # they are what you would search for in boinctui.
                'name': result.get('name'),
                'project': names.get(url) or url,
                'fraction_done': active.get('fraction_done'),
                'deadline': result.get('report_deadline'),
            })
        elif result.get('ready_to_report'):
            ready += 1
        else:
            queued += 1

    # Sorted by deadline, soonest first; anything without one goes last rather than breaking the
    # comparison. Deadlines are naive datetimes -- never compare them with an aware one.
    running.sort(key=lambda task: (task['deadline'] is None, task['deadline']))

    return {
        'running': running,
        'queued': queued,
        'ready_to_report': ready,
        'projects': [
            {'name': project.get('project_name') or _url(project.get('master_url')),
             'url': _url(project.get('master_url'))}
            for project in projects
        ],
    }


async def _open(host: str, port: int, password: str):
    """Connect, telling a machine that is not there apart from one that will not talk to us.

    BOINC checks the caller's address only after accepting the connection, and hangs up on anyone
    missing from its allowed list. Both failures look alike from the outside, so they are told apart
    by *when* they happen: anything after this function returned means we were let in and then cut
    off, which is a different problem with a different fix.
    """
    try:
        return await init_rpc_client(host, password, port)
    except (TimeoutError, OSError) as error:
        raise CannotConnect(f'Could not reach a BOINC client at {host}:{port}') from error


async def _authenticate(client, host: str, port: int) -> None:
    # init_rpc_client connects but does not authenticate, and the query methods do not check
    # authorisation: against an unauthorised session they return parsed nonsense rather than
    # failing. Checking the return value here is what turns a wrong password into an error the page
    # can explain instead of a silently empty screen.
    try:
        authorized = await client.authorize()
    except (asyncio.IncompleteReadError, EOFError, OSError) as error:
        raise ConnectionRejected(
            f'The BOINC client at {host}:{port} closed the connection without answering'
        ) from error
    if not authorized:
        raise AuthenticationFailed('The BOINC client rejected the password')


async def _read_state(client) -> dict:
    cc_status = await client.get_cc_status()
    projects = _as_list(await client.get_project_status())
    results = _as_list(await client.get_results())
    return {
        'activity': describe_activity(cc_status),
        'mode': describe_mode(cc_status),
        **_summarise(results, projects),
    }


async def _collect(host: str, port: int, password: str) -> dict:
    client = await _open(host, port, password)
    try:
        await _authenticate(client, host, port)
        return await _read_state(client)
    finally:
        await client.close()


async def _apply_mode(host: str, port: int, password: str, mode: str) -> dict:
    client = await _open(host, port, password)
    try:
        await _authenticate(client, host, port)
        if not await client.set_run_mode(MODES[mode], PERMANENT):
            raise AuthenticationFailed('The BOINC client refused to change the mode')
        # Read back over the same connection, so the page shows the new mode immediately rather
        # than looking unchanged until the next poll. The mode is already updated by the time this
        # returns; the suspend reason may not be, because the client recomputes that on its own
        # cycle -- verified against a running client.
        return await _read_state(client)
    finally:
        await client.close()


async def _safely(client: dict, action, timeout: int) -> dict:
    """Run one exchange with a client, turning every way it can fail into a message."""
    host, password = client.get('host'), client.get('password')
    port = client.get('port') or DEFAULT_PORT
    if not host or not password:
        return {'error': NotConfigured('This client is missing an address or a password')}

    try:
        return {'state': await asyncio.wait_for(action(host, port, password), timeout)}
    except BoincError as error:
        return {'error': error}
    except (TimeoutError, OSError) as error:
        return {'error': CannotConnect(f'Could not reach a BOINC client at {host}:{port}')}
    except Exception as error:
        # The library raises bare exceptions and assertion-style errors on malformed replies, so
        # anything unexpected still has to reach the page as a message rather than kill the poll.
        logging.debug(f'Unexpected failure talking to {host}:{port}: {error!r}')
        return {'error': BoincError(f'Unexpected reply from the BOINC client at {host}:{port}')}


def _machine(client: dict, outcome: dict) -> dict:
    """One machine as the page sees it: what it is doing, or what went wrong reaching it."""
    error = outcome.get('error')
    return {
        'name': describe_client(client),
        'host': client.get('host'),
        'state': outcome.get('state'),
        'error': str(error) if error else None,
        'error_kind': ERROR_KINDS.get(type(error), 'error') if error else None,
    }


async def _read_all(clients: list[dict]) -> list[dict]:
    # Every client is contacted at the same time, so a machine that is switched off delays only
    # itself: a cycle takes as long as the slowest one rather than the sum of all of them.
    return await asyncio.gather(
        *(_safely(client, _collect, TIMEOUT_SECONDS) for client in clients)
    )


def read_all(clients: list[dict]) -> list[dict]:
    """Read every configured client. A failure is reported per client, never raised."""
    if not clients:
        return []

    outcomes = asyncio.run(_read_all(clients))
    return [_machine(client, outcome) for client, outcome in zip(clients, outcomes)]


def set_mode(client: dict, mode: str) -> dict:
    """Change one machine's activity mode, and report how it looks afterwards.

    Returns the same shape as an entry of `read_all`, so the caller can drop it straight into the
    snapshot. Reaching the machine can fail in all the usual ways and that is reported, not raised;
    an unknown mode is a mistake in this program and does raise.
    """
    if mode not in MODES:
        raise ValueError(f'Unknown activity mode {mode!r}')

    logging.debug(f'Setting activity mode {mode} on {client.get("host")}')
    outcome = asyncio.run(_safely(
        client,
        lambda host, port, password: _apply_mode(host, port, password, mode),
        ACTION_TIMEOUT_SECONDS,
    ))
    return _machine(client, outcome)
