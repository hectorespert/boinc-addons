import argparse
import logging
import signal
import threading

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
    # There is no server to run yet, but the add-on still has to behave like one: an entrypoint that
    # returned here would leave Supervisor reporting the app as stopped seconds after the user
    # started it, which is indistinguishable from a crash. Block until Supervisor asks us to stop.
    # Logged only once the handlers above are registered, so it doubles as a synchronization point
    # for tests that need to signal this process and know the signal will actually be handled.
    logging.info('BOINC UI started')
    stop_requested.wait()

logging.info('BOINC UI stopped')
