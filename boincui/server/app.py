import logging
import threading
from datetime import datetime, timezone

from flask import Flask, redirect, render_template

from boinc import AuthenticationFailed, BoincError, CannotConnect, NotConfigured, read_state

# Home Assistant serves this app under /api/hassio_ingress/<token>/ and strips that prefix before
# forwarding, without telling us what it was: the only headers ingress adds are X-Remote-User-* and
# X-Forwarded-For. The token is also generated at install time, so it is unknown when the image is
# built and when the container starts. Every URL this app emits therefore has to be relative --
# including redirects, since an absolute `Location: /` sends the browser to the Home Assistant root
# and out of the panel. test_app.py guards all three of href, action and Location.
SELF = './'

# The BOINC client's state does not move quickly, and every refresh costs it a connection. The page
# reloads far more often than this, but it only ever reads the snapshot below.
REFRESH_SECONDS = 60

ERROR_KINDS = {
    NotConfigured: 'not_configured',
    CannotConnect: 'cannot_connect',
    AuthenticationFailed: 'auth_failed',
}


class Snapshot:
    """The state the views render.

    Views never talk to a BOINC client while handling a request: the refresher below writes here and
    the views only read. That keeps rendering time independent of how many hosts are configured, and
    means a host that is switched off cannot stall the page.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict | None = None
        self._updated: datetime | None = None
        self._error: str | None = None
        self._error_kind: str | None = None

    def read(self) -> dict:
        with self._lock:
            return {
                'state': self._state,
                'updated': self._updated,
                'error': self._error,
                'error_kind': self._error_kind,
            }

    def store(self, state: dict) -> None:
        with self._lock:
            self._state = state
            self._updated = datetime.now(timezone.utc)
            self._error = self._error_kind = None

    def fail(self, error: BoincError) -> None:
        # The last good state is deliberately kept: a page showing yesterday's tasks next to "could
        # not reach the client" is more useful than one that goes blank on a single failed poll.
        with self._lock:
            self._updated = datetime.now(timezone.utc)
            self._error = str(error)
            self._error_kind = ERROR_KINDS.get(type(error), 'error')


class Refresher(threading.Thread):
    """Polls the BOINC client on its own thread, so requests never wait on the network."""

    def __init__(self, snapshot: Snapshot, options: dict, stop: threading.Event) -> None:
        super().__init__(name='refresher', daemon=True)
        self._snapshot = snapshot
        self._options = options
        self._stop = stop

    def refresh_once(self) -> None:
        try:
            self._snapshot.store(read_state(
                self._options.get('boinc_host'),
                self._options.get('boinc_port'),
                self._options.get('gui_rpc_password'),
            ))
            logging.debug('Refreshed state from the BOINC client')
        except BoincError as error:
            logging.warning(f'Could not read the BOINC client state: {error}')
            self._snapshot.fail(error)

    def run(self) -> None:
        while not self._stop.is_set():
            self.refresh_once()
            self._stop.wait(REFRESH_SECONDS)


def create_app(snapshot: Snapshot | None = None) -> Flask:
    app = Flask(__name__)
    app.config['SNAPSHOT'] = snapshot if snapshot is not None else Snapshot()
    app.config['REFRESH_SECONDS'] = REFRESH_SECONDS

    @app.route('/')
    def index():
        return render_template('index.html', **app.config['SNAPSHOT'].read())

    @app.route('/refresh', methods=['POST'])
    def refresh():
        refresher = app.config.get('REFRESHER')
        if refresher is not None:
            refresher.refresh_once()
        return redirect(SELF)

    return app
