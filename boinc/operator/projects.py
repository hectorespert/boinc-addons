import json
import logging
import os
import subprocess

from url import canonicalize_url

# What the operator attached on a previous run. BOINC cannot record this for us: a project carries
# no label saying who attached it, so without this file one the user attached from boinctui would be
# indistinguishable from one the operator attached and the user then removed from the options --
# and the removal branch below would destroy it. Same pattern as .managed_global_prefs.json.
MANAGED_STATE_FILE = '.managed_projects.json'

# Projects the operator attached and still owns, and projects it has asked the client to leave once
# their work is done. The second list cannot be derived from the client: detach_when_done is not
# among the fields --get_project_status prints, so a pending detach is invisible from outside.
MANAGED_ATTACHED = 'attached'
MANAGED_DETACHING = 'detaching'

# Backoff for a project whose attach failed, in seconds. Attaching is a local RPC, so this covers a
# client that is not answering yet rather than a project that is down -- the client retries the
# project's own scheduler by itself, indefinitely, and does it better than the operator could.
RETRY_INITIAL_DELAY = 30
RETRY_MAX_DELAY = 1800


def run_boinccmd(data_folder: str, arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["boinccmd", *arguments], capture_output=True, text=True, cwd=data_folder)

def validate_projects(projects: list[dict] | None, account_manager_url: str | None) -> bool:
    if not projects:
        return True

    if account_manager_url is not None:
        # An account manager owns the project list and re-asserts it on every sync, so the two
        # would undo each other on a loop for as long as the app ran. Like half an account manager,
        # this has no safe reading, so it stops the app instead of oscillating quietly.
        logging.error(f'Conflicting configuration: projects cannot be listed while account_manager_url is set, because the account manager decides which projects are attached')
        return False

    seen = set()
    for project in projects:
        url = project.get('url')
        if not url or not project.get('account_key'):
            logging.error(f'Incomplete project configuration: every project needs both url and account_key')
            return False

        url = canonicalize_url(url)
        if url in seen:
            # Two entries for one project with different keys have no safe reading either: whichever
            # the operator picked would look arbitrary the first time it mattered.
            logging.error(f'Duplicated project {url}: list each project once')
            return False
        seen.add(url)

    return True

def read_attached_projects(data_folder: str) -> dict[str, bool] | None:
    """Every attached project, keyed by canonicalized master URL, mapped to whether an account
    manager attached it. Returns None when the client could not be asked at all."""
    result = run_boinccmd(data_folder, ["--get_project_status"])
    if result.returncode != 0:
        logging.error(f'Failed to get project status: {result.stderr}')
        return None

    logging.debug(f'{result.stdout}')

    projects = {}
    url = None
    for line in result.stdout.splitlines():
        name, separator, value = line.partition(':')
        if not separator:
            continue

        name = name.strip()
        value = value.strip()

        if name == 'master URL':
            # The client stores the URL already canonicalized, but canonicalizing again is what
            # makes it comparable to a URL typed into the options.
            url = canonicalize_url(value)
            projects[url] = False
        elif name == 'attached via Account Manager' and url is not None:
            projects[url] = value == 'yes'

    return projects

def read_managed_state(data_folder: str) -> dict[str, set[str]]:
    state_file = f'{data_folder}/{MANAGED_STATE_FILE}'
    empty = {MANAGED_ATTACHED: set(), MANAGED_DETACHING: set()}

    if not os.path.exists(state_file):
        return empty

    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
    except (OSError, ValueError) as error:
        logging.warning(f'Ignoring unreadable {MANAGED_STATE_FILE}: {error}')
        return empty

    if not isinstance(state, dict):
        logging.warning(f'Ignoring {MANAGED_STATE_FILE}, expected an object')
        return empty

    # An unreadable half means "the operator never attached this", which only ever makes the
    # removal branch do less. Erring the other way could detach a project it does not own.
    return {key: {url for url in state.get(key, []) if isinstance(url, str)} for key in empty}

def write_managed_state(data_folder: str, state: dict[str, set[str]]) -> None:
    with open(f'{data_folder}/{MANAGED_STATE_FILE}', 'w') as f:
        json.dump({key: sorted(urls) for key, urls in state.items()}, f, indent=2, sort_keys=True)

def attach_project(data_folder: str, url: str, account_key: str) -> bool:
    logging.info(f'Attaching project {url}')
    result = run_boinccmd(data_folder, ["--project_attach", url, account_key])
    if result.returncode != 0:
        logging.warning(f'Failed to attach project {url}, retrying later: {result.stderr.strip() or result.stdout.strip()}')
        return False

    logging.debug(result.stdout)
    logging.info(f'Project {url} attached')
    return True

def project_operation(data_folder: str, url: str, operation: str) -> bool:
    result = run_boinccmd(data_folder, ["--project", url, operation])
    if result.returncode != 0:
        logging.error(f'Failed to {operation} project {url}: {result.stderr.strip() or result.stdout.strip()}')
        return False

    logging.debug(result.stdout)
    return True

def configure_projects(data_folder: str, projects: list[dict] | None) -> list[str]:
    """Reconcile the attached projects against the configured ones, returning the projects that
    still need attaching so the caller can try them again later."""
    desired = {canonicalize_url(project['url']): project['account_key'] for project in projects or []}
    managed = read_managed_state(data_folder)

    if not desired and not managed[MANAGED_ATTACHED] and not managed[MANAGED_DETACHING]:
        # Nothing configured and nothing ever attached by the operator: the overwhelmingly common
        # case, and the one where asking the client anything at all would be pure cost.
        return []

    statuses = read_attached_projects(data_folder)
    if statuses is None:
        # Without the current state there is no diff to compute, and acting blind could attach a
        # project twice or detach one the operator does not own. Try the whole thing again later.
        return sorted(desired)

    # A project an account manager attached belongs to the account manager, which re-asserts its
    # list on every sync. Touching it here would start exactly the loop validate_projects refuses.
    account_manager_owned = {url for url, via_account_manager in statuses.items() if via_account_manager}
    attached = set(statuses) - account_manager_owned

    for url in sorted(desired.keys() & account_manager_owned):
        logging.warning(f'Ignoring project {url}: it is attached by an account manager, which decides on its own which projects are attached')

    # Configured again after being left to drain, so undo both halves of detach_when_done. The
    # client clears its no-more-work flag with the detach flag, but saying so explicitly costs one
    # local RPC and does not depend on that.
    for url in sorted(managed[MANAGED_DETACHING] & desired.keys() & attached):
        logging.info(f'Project {url} is configured again, cancelling its pending detach')
        project_operation(data_folder, url, 'dont_detach_when_done')
        project_operation(data_folder, url, 'allowmorework')

    # Only a project the operator attached itself may be detached, and only while it is still
    # there: boinccmd fails outright on a project the user already detached by hand. A project
    # already draining stays in the set so the flag is re-asserted rather than assumed.
    owned = managed[MANAGED_ATTACHED] | managed[MANAGED_DETACHING]
    detaching = (owned - desired.keys()) & attached
    for url in sorted(detaching):
        logging.info(f'Project {url} is no longer configured, detaching it once its current work is done')
        project_operation(data_folder, url, 'detach_when_done')

    attached_now = set()
    pending = []
    for url in sorted(desired.keys() - attached - account_manager_owned):
        if attach_project(data_folder, url, desired[url]):
            attached_now.add(url)
        else:
            pending.append(url)

    write_managed_state(data_folder, {
        MANAGED_ATTACHED: (desired.keys() & attached) | attached_now,
        # Already intersected with what is attached, so an entry disappears on the run after the
        # client actually lets the project go instead of lingering forever.
        MANAGED_DETACHING: detaching,
    })

    return pending
