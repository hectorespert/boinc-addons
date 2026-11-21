"""The only place that talks to a BOINC client.

Everything above this module works with plain dicts and never sees that aioboinc is
asyncio-based, so the views and the refresher stay synchronous.
"""

import asyncio
import logging

from aioboinc import ActiveTaskState, BOINCAuthError, BOINCConnectionError, Mode, init_rpc_client
from status import describe_activity, describe_gpus, describe_mode, describe_processor

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
        if active.get('active_task_state') == ActiveTaskState.EXECUTING:
            running.append({
                # Kept for the row's `title`: BOINC's own identifiers say nothing to a reader, but
                # they are what you would search for in boinctui.
                'name': result.get('name'),
                'project': names.get(url) or url,
                'fraction_done': active.get('fraction_done'),
                'deadline': result.get('report_deadline'),
                # BOINC's own estimate, the one BOINC Manager shows as "Remaining (estimated)". It is
                # computing time still needed, not a time of day: a machine that pauses finishes later.
                'remaining': result.get('estimated_cpu_time_remaining'),
            })
        elif result.get('ready_to_report'):
            ready += 1
        else:
            queued += 1

    # Sorted by deadline, soonest first; anything without one goes last rather than breaking the
    # comparison. Deadlines are aware datetimes in UTC -- never compare them with a naive one.
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
        # The deadline is ours, set by `_safely` around the whole exchange. The library's own, per
        # reply, is switched off so that a host which stops answering half way is always told apart
        # by that one deadline, never by whichever of the two happens to run out first.
        return await init_rpc_client(host, password, port, timeout=None)
    except BOINCConnectionError as error:
        raise CannotConnect(f'Could not reach a BOINC client at {host}:{port}') from error


async def _authenticate(client, host: str, port: int) -> None:
    # init_rpc_client connects but does not authenticate. Doing it before anything else means a wrong
    # password is reported as such, rather than as whichever query happened to be refused first.
    try:
        await client.authorize()
    except BOINCAuthError as error:
        raise AuthenticationFailed('The BOINC client rejected the password') from error
    except BOINCConnectionError as error:
        raise ConnectionRejected(
            f'The BOINC client at {host}:{port} closed the connection without answering'
        ) from error


async def _read_state(client) -> dict:
    cc_status = await client.get_cc_status()
    # The processor is read here rather than once per machine at startup, so that a machine which
    # was switched off when the app started still describes itself as soon as it answers. It is also
    # why acting on a machine keeps its processor line: an action re-reads the state through here.
    host_info = await client.get_host_info()
    # Projects come back as library objects rather than dicts; they are flattened here so that
    # nothing above this module has to know the library exists.
    projects = [vars(project) for project in await client.get_project_status()]
    results = await client.get_results()
    return {
        'activity': describe_activity(cc_status),
        'mode': describe_mode(cc_status),
        'processor': describe_processor(host_info),
        'gpus': describe_gpus(host_info),
        **_summarise(results, projects),
    }


async def _collect(host: str, port: int, password: str) -> dict:
    # Entering keeps the connection `_open` made; leaving closes it, whatever was raised.
    async with await _open(host, port, password) as client:
        await _authenticate(client, host, port)
        return await _read_state(client)


async def _apply_mode(host: str, port: int, password: str, mode: str) -> dict:
    async with await _open(host, port, password) as client:
        await _authenticate(client, host, port)
        # A refusal should not happen after the authentication above succeeded, so if it ever does
        # the message needs to say what was actually refused rather than invent a cause.
        try:
            await client.set_run_mode(MODES[mode], PERMANENT)
        except BOINCAuthError as error:
            raise AuthenticationFailed(
                'The BOINC client treated the change as unauthorised'
            ) from error
        # Read back over the same connection, so the page shows the new mode immediately rather
        # than looking unchanged until the next poll. The mode is already updated by the time this
        # returns; the suspend reason may not be, because the client recomputes that on its own
        # cycle -- verified against a running client.
        return await _read_state(client)


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
        # Such as BOINCCommandError, when the client answers with an error: anything unexpected
        # still has to reach the page as a message rather than kill the poll.
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
