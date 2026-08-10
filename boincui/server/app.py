import logging
import threading
from datetime import datetime, timezone

from flask import Flask, redirect, render_template

# Home Assistant serves this app under /api/hassio_ingress/<token>/ and strips that prefix before
# forwarding, without telling us what it was: the only headers ingress adds are X-Remote-User-* and
# X-Forwarded-For. The token is also generated at install time, so it is unknown when the image is
# built and when the container starts. Every URL this app emits therefore has to be relative --
# including redirects, since an absolute `Location: /` sends the browser to the Home Assistant root
# and out of the panel. test_app.py guards all three of href, action and Location.
SELF = './'


class Snapshot:
    """The state the views render.

    Views never talk to a BOINC client while handling a request: a background refresher writes here
    and the views only read. That keeps rendering time independent of how many hosts are configured,
    and means a host that is switched off cannot stall the page.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hosts: dict[str, dict] = {}
        self._updated: datetime | None = None

    def read(self) -> tuple[dict[str, dict], datetime | None]:
        with self._lock:
            return dict(self._hosts), self._updated

    def refresh(self) -> None:
        # Nothing to collect yet: no BOINC client is configured or contacted in this version. This
        # records the attempt so the page can show it, and is where the GUI RPC fan-out will go.
        with self._lock:
            self._updated = datetime.now(timezone.utc)
        logging.debug('Refreshed snapshot')


def create_app(snapshot: Snapshot | None = None) -> Flask:
    app = Flask(__name__)
    app.config['SNAPSHOT'] = snapshot if snapshot is not None else Snapshot()

    @app.route('/')
    def index():
        hosts, updated = app.config['SNAPSHOT'].read()
        return render_template('index.html', hosts=hosts, updated=updated)

    @app.route('/refresh', methods=['POST'])
    def refresh():
        app.config['SNAPSHOT'].refresh()
        return redirect(SELF)

    return app
