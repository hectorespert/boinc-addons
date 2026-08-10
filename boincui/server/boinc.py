"""The only place that talks to a BOINC client.

Everything above this module works with plain dicts and never sees that the vendored library is
asyncio-based, so the views and the refresher stay synchronous.
"""

import asyncio
import logging

from pyboinc import init_rpc_client
from status import describe_activity

DEFAULT_PORT = 31416
# BOINC's own client gives up well before this; the point is only that a host which accepts the
# connection and then says nothing cannot hold the refresher forever.
TIMEOUT_SECONDS = 30

# `active_task_state` when a task is actually executing (lib/common_defs.h: PROCESS_EXECUTING).
PROCESS_EXECUTING = 1


class BoincError(Exception):
    """Anything that stopped us reading a client's state, phrased for a user to read."""


class NotConfigured(BoincError):
    pass


class CannotConnect(BoincError):
    pass


class AuthenticationFailed(BoincError):
    pass


ERROR_KINDS = {
    NotConfigured: 'not_configured',
    CannotConnect: 'cannot_connect',
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


async def _collect(host: str, port: int, password: str) -> dict:
    client = await init_rpc_client(host, password, port)
    try:
        # init_rpc_client connects but does not authenticate, and the query methods below do not
        # check authorisation: against an unauthorised session they return parsed nonsense rather
        # than failing. Checking the return value here is what turns a wrong password into an error
        # the page can explain instead of a silently empty screen.
        if not await client.authorize():
            raise AuthenticationFailed('The BOINC client rejected the password')
        cc_status = await client.get_cc_status()
        projects = _as_list(await client.get_project_status())
        results = _as_list(await client.get_results())
    finally:
        await client.close()

    return {'activity': describe_activity(cc_status), **_summarise(results, projects)}


async def _collect_safely(client: dict) -> dict:
    host, password = client.get('host'), client.get('password')
    port = client.get('port') or DEFAULT_PORT
    if not host or not password:
        return {'error': NotConfigured('This client is missing an address or a password')}

    try:
        logging.debug(f'Reading state from {host}:{port}')
        state = await asyncio.wait_for(_collect(host, port, password), TIMEOUT_SECONDS)
        return {'state': state}
    except AuthenticationFailed as error:
        return {'error': error}
    except (TimeoutError, OSError, ConnectionError) as error:
        return {'error': CannotConnect(f'Could not reach a BOINC client at {host}:{port}')}
    except Exception as error:
        # The library raises bare exceptions and assertion-style errors on malformed replies, so
        # anything unexpected still has to reach the page as a message rather than kill the poll.
        logging.debug(f'Unexpected failure reading {host}:{port}: {error!r}')
        return {'error': BoincError(f'Unexpected reply from the BOINC client at {host}:{port}')}


async def _read_all(clients: list[dict]) -> list[dict]:
    # Every client is contacted at the same time, so a machine that is switched off delays only
    # itself: a cycle takes as long as the slowest one rather than the sum of all of them.
    return await asyncio.gather(*(_collect_safely(client) for client in clients))


def read_all(clients: list[dict]) -> list[dict]:
    """Read every configured client. A failure is reported per client, never raised."""
    if not clients:
        return []

    outcomes = asyncio.run(_read_all(clients))
    machines = []
    for client, outcome in zip(clients, outcomes):
        error = outcome.get('error')
        machines.append({
            'name': describe_client(client),
            'host': client.get('host'),
            'state': outcome.get('state'),
            'error': str(error) if error else None,
            'error_kind': ERROR_KINDS.get(type(error), 'error') if error else None,
        })
    return machines
