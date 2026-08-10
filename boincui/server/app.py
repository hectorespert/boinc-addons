import logging
import threading
from datetime import datetime, timezone

from flask import Flask, redirect, render_template

from boinc import read_all

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
    """The machines to poll, accepting the single-client options this add-on used to have.

    Supervisor drops options that are absent from the schema without telling anyone, so removing the
    old keys outright would silently wipe an existing configuration. They keep working for one
    version instead.
    """
    clients = options.get('clients') or []
    if clients:
        return clients

    if options.get('boinc_host') or options.get('gui_rpc_password'):
        logging.warning(
            'Using the old single-client options. Move them to the "clients" list in the '
            'Configuration tab; they will stop working in a future version'
        )
        return [{
            'name': options.get('boinc_host'),
            'host': options.get('boinc_host'),
            'port': options.get('boinc_port'),
            'password': options.get('gui_rpc_password'),
        }]

    return []


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


class Refresher(threading.Thread):
    """Polls every configured machine on its own thread, so requests never wait on the network."""

    def __init__(self, snapshot: Snapshot, options: dict, stop: threading.Event) -> None:
        super().__init__(name='refresher', daemon=True)
        self._snapshot = snapshot
        self._clients = clients_from(options)
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
        return render_template('index.html', **app.config['SNAPSHOT'].read())

    @app.route('/refresh', methods=['POST'])
    def refresh():
        refresher = app.config.get('REFRESHER')
        if refresher is not None:
            refresher.request_refresh()
        return redirect(SELF)

    return app
