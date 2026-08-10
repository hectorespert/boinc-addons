import argparse
import logging
import signal
import threading

import waitress

from app import Snapshot, create_app

# Must match `ingress_port` in config.yaml: Home Assistant proxies to this port on the container's
# own address, so it is never published to the host and never reached directly by a user.
INGRESS_PORT = 8099

parser = argparse.ArgumentParser(prog='boincui')

parser.add_argument("--log-level", default=logging.INFO, type=lambda x: getattr(logging, x))
parser.add_argument("--exit-immediately", action='store_true', help="Exit immediately instead of waiting to be stopped")

args = parser.parse_args()
logging.basicConfig(level=args.log_level, format='%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

logging.info('hello world')

stop_requested = threading.Event()

def signal_handler(number, frame):
    logging.debug(f'Caught signal {number}')
    stop_requested.set()

signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if args.exit_immediately:
    logging.warning('Exiting immediately instead of waiting to be stopped')
else:
    server = waitress.create_server(create_app(Snapshot()), host='0.0.0.0', port=INGRESS_PORT)
    threading.Thread(target=server.run, daemon=True).start()
    # Logged only once the server is listening and the handlers above are registered, so it doubles
    # as a synchronization point for tests that need to connect, or to signal this process and know
    # the signal will actually be handled.
    logging.info(f'BOINC UI started on port {INGRESS_PORT}')
    stop_requested.wait()
    # Closes the listening socket deterministically, so the stop below means the port is really gone
    # rather than merely that this thread stopped waiting.
    server.close()

logging.info('BOINC UI stopped')
