import logging
import threading
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request

from boinc import read_all, set_mode
from status import ACTIVITY_MODES

# The modes a browser is allowed to ask for. Taken from the same table the page renders, so the
# buttons and what is accepted here cannot drift apart.
MODE_NAMES = frozenset(key for key, _label, _description in ACTIVITY_MODES)

# Home Assistant serves this app under /api/hassio_ingress/<token>/ and strips that prefix before
# forwarding, without telling us what it was: the only headers ingress adds are X-Remote-User-* and
# X-Forwarded-For. The token is also generated at install time, so it is unknown when the image is
# built and when the container starts. Every URL this app emits therefore has to be relative --
# including redirects, since an absolute `Location: /` sends the browser to the Home Assistant root
# and out of the panel. test_app.py guards all three of href, action and Location.
SELF = './'

# A BOINC client's state does not move quickly, and every refresh costs each machine a connection.
# The page reloads far more often than this, but it only ever reads the snapshot below.
REFRESH_SECONDS = 60


def clients_from(options: dict) -> list[dict]:
    """The machines to poll.

    The single-client options this add-on started with (`boinc_host` and friends) were removed in
    1.0.0 and are deliberately not read any more: Supervisor discards options that are missing from
    the schema, so they cannot arrive here even if someone still has them configured.
    """
    return options.get('clients') or []


class Snapshot:
    """The state the views render.

    Views never talk to a BOINC client while handling a request: the refresher below writes here and
    the views only read. That keeps rendering time independent of how many machines are configured,
    and means one that is switched off cannot stall the page.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._machines: list[dict] | None = None
        self._updated: datetime | None = None

    def read(self) -> dict:
        with self._lock:
            return {'machines': self._machines, 'updated': self._updated}

    def store(self, machines: list[dict]) -> None:
        with self._lock:
            self._machines = machines
            self._updated = datetime.now(timezone.utc)

    def replace(self, index: int, machine: dict) -> None:
        """Update a single machine, after acting on it.

        Only the one that was acted on changes: re-reading the rest would mean waiting on every
        configured client inside a request, which is what the background refresher exists to avoid.
        """
        with self._lock:
            if self._machines is not None and 0 <= index < len(self._machines):
                self._machines[index] = machine
                self._updated = datetime.now(timezone.utc)


class Refresher(threading.Thread):
    """Polls every configured machine on its own thread, so requests never wait on the network."""

    def __init__(self, snapshot: Snapshot, clients: list[dict], stop: threading.Event) -> None:
        super().__init__(name='refresher', daemon=True)
        self._snapshot = snapshot
        self._clients = clients
        # Not `self._stop`: threading.Thread already uses that name for a private method, and
        # shadowing it makes join() raise TypeError.
        self._stop_requested = stop
        self._wake = threading.Event()

    def request_refresh(self) -> None:
        """Ask for a poll now, and return without waiting for it.

        Running the poll inline would block the request for as long as the slowest machine takes to
        answer -- up to the connect timeout when one is unreachable -- which is exactly what this
        class exists to keep out of request handling.
        """
        self._wake.set()

    def refresh_once(self) -> None:
        machines = read_all(self._clients)
        for machine in machines:
            if machine['error']:
                logging.warning(f'{machine["name"]}: {machine["error"]}')
        self._snapshot.store(machines)

    def run(self) -> None:
        while not self._stop_requested.is_set():
            self.refresh_once()
            self._wake.clear()
            self._wake.wait(REFRESH_SECONDS)


def format_due(deadline: datetime | None) -> str:
    """A deadline as something a person reads, e.g. "in 2 days"."""
    if deadline is None:
        return '—'

    # Deadlines arrive as naive datetimes in local time, because that is what the library produces.
    # `now` is deliberately naive too: mixing an aware datetime in here raises TypeError.
    seconds = (deadline - datetime.now()).total_seconds()
    if seconds <= 0:
        return 'overdue'
    for size, unit in ((86400, 'day'), (3600, 'hour'), (60, 'minute')):
        if seconds >= size:
            count = int(seconds // size)
            return f'in {count} {unit}{"s" if count > 1 else ""}'
    return 'in under a minute'


def create_app(snapshot: Snapshot | None = None) -> Flask:
    app = Flask(__name__)
    app.config['SNAPSHOT'] = snapshot if snapshot is not None else Snapshot()
    app.jinja_env.filters['due'] = format_due

    @app.route('/')
    def index():
        return render_template(
            'index.html',
            modes=ACTIVITY_MODES,
            failed=request.args.get('failed', type=int),
            **app.config['SNAPSHOT'].read(),
        )

    @app.route('/refresh', methods=['POST'])
    def refresh():
        refresher = app.config.get('REFRESHER')
        if refresher is not None:
            refresher.request_refresh()
        return redirect(SELF)

    # A flat route on purpose. Under `/mode/<machine>` the redirect below would resolve against
    # `/mode/` and never reach the page again, since the only correct relative target this app can
    # emit is one that assumes it lives at the root -- see SELF.
    @app.route('/mode', methods=['POST'])
    def mode():
        clients = app.config.get('CLIENTS') or []
        machine = request.form.get('machine', '')
        chosen = request.form.get('mode', '')
        # Both fields come from a browser, so they are checked before anything reaches a client.
        if not machine.isdigit() or int(machine) >= len(clients) or chosen not in MODE_NAMES:
            logging.warning(f'Ignoring an activity change for machine {machine!r} to {chosen!r}')
            return redirect(SELF)

        index = int(machine)
        updated = set_mode(clients[index], chosen)
        app.config['SNAPSHOT'].replace(index, updated)
        if updated['error']:
            logging.warning(f'{updated["name"]}: {updated["error"]}')
            return redirect(f'{SELF}?failed={index}')
        return redirect(SELF)

    return app
