import argparse
import json
import logging
import signal
import threading

import waitress

from app import Refresher, Snapshot, clients_from, create_app

# Supervisor's own default for `ingress_port`, which is why config.yaml does not set it -- the
# add-on linter rejects redeclaring a default. Home Assistant proxies to this port on the
# container's own address, so it is never published to the host nor reached directly by a user.
INGRESS_PORT = 8099

parser = argparse.ArgumentParser(prog='boincui')

parser.add_argument('--options', type=str, help='Configuration file')
parser.add_argument("--log-level", default=logging.INFO, type=lambda x: getattr(logging, x))
parser.add_argument("--exit-immediately", action='store_true', help="Exit immediately instead of waiting to be stopped")

args = parser.parse_args()
logging.basicConfig(level=args.log_level, format='%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

logging.info('Starting BOINC UI')

options = {}
if args.options:
    try:
        with open(args.options, encoding='UTF-8') as options_file:
            options = json.load(options_file)
        logging.info(f'Configuration loaded from {args.options}')
    except FileNotFoundError:
        # Supervisor always writes this file, so its absence means the image is being run directly.
        # Starting anyway is what lets the page come up and say nothing is configured yet.
        logging.warning(f'No configuration file at {args.options}, starting unconfigured')
    except json.JSONDecodeError as error:
        logging.error(f'Ignoring unreadable configuration file {args.options}: {error}')
# Worked out once and shared, because the activity buttons address a machine by its position in this
# very list.
clients = clients_from(options)
# Addresses only. The password is never logged, at any level: this add-on holds a copy of the one
# that controls the BOINC client, and DEBUG logs are what users paste into issues.
logging.debug('Watching ' + (', '.join(
    f'{client.get("host")}:{client.get("port") or "default"}' for client in clients
) or 'no machines'))

stop_requested = threading.Event()

# Blocked here, before any thread starts, and collected with sigwait() below instead of handled. A
# Python handler runs on top of whatever the main thread was doing, and the one this replaced logged
# from there: when the signal landed while that thread was itself writing a log line, Python 3.14
# refused the nested write to stderr with RuntimeError, the handler never set the stop flag, and the
# app ignored every signal after that. Every thread started below inherits the mask, so none of them
# takes the signal instead.
STOP_SIGNALS = {signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGTERM}
signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)

if args.exit_immediately:
    logging.warning('Exiting immediately instead of waiting to be stopped')
else:
    snapshot = Snapshot()
    app = create_app(snapshot)
    refresher = Refresher(snapshot, clients, stop_requested)
    app.config['CLIENTS'] = clients
    # Lets the "refresh now" button poll on demand instead of waiting for the next cycle.
    app.config['REFRESHER'] = refresher
    refresher.start()

    server = waitress.create_server(app, host='0.0.0.0', port=INGRESS_PORT)
    threading.Thread(target=server.run, daemon=True).start()
    # Logged only once the server is listening and the signals above are blocked, so it doubles as a
    # synchronization point for tests that need to connect, or to signal this process and know the
    # signal will actually be acted on: one sent before sigwait() is reached waits for it.
    logging.info(f'BOINC UI started on port {INGRESS_PORT}')
    number = signal.sigwait(STOP_SIGNALS)
    logging.debug(f'Caught signal {number}')
    stop_requested.set()
    # Closes the listening socket deterministically, so the stop below means the port is really gone
    # rather than merely that this thread stopped waiting.
    server.close()

logging.info('BOINC UI stopped')
