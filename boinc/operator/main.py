import argparse
import json
import logging
import os
import signal
import subprocess
import sys
from time import sleep

from boinc import build_boinc_command
from boinccmd import configure_boinc_projects, get_state
from cc_config import prepare_cc_config
from folders import prepare_data_folders
from global_prefs_override import link_global_prefs_override
from gui_rpc_auth import prepare_gui_rpc_auth
from projects import configure_projects, validate_projects
from redact import redact_secrets
from remote_hosts import prepare_remote_hosts

parser = argparse.ArgumentParser(prog='operator')

parser.add_argument('--options', type=argparse.FileType('r', encoding='UTF-8'), required=True, help='Configuration file')
parser.add_argument('--data', type=str, required=True, help='BOINC data folder')
parser.add_argument('--config', type=str, required=True, help='Add-on config folder')
parser.add_argument("--log-level", default=logging.INFO, type=lambda x: getattr(logging, x))
parser.add_argument("--exit-immediately", action='store_true', help="Exit immediately after BOINC client is started")

args = parser.parse_args()
logging.basicConfig(level=args.log_level, format='%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

current_pid = os.getpid()
logging.info(f'Starting BOINC Add-on Operator with pid {current_pid}')

# This heuristic depends on `init: false` in config.yaml: with no init system in the image, the
# operator is PID 1 exactly when Protection Mode confines the container to its own PID namespace,
# and `host_pid: true` gives it the host's namespace (so a much higher PID) when it does not.
# Setting `init: true` would put Docker's init at PID 1 and silently disable this warning.
if current_pid == 1:
    logging.warning('Protection Mode is enabled. BOINC requires system-wide usage monitoring to function properly.')

logging.info(f'Configuration loaded from {args.options.name}')

options = json.load(args.options)
logging.debug(f'Current configuration\n{json.dumps(redact_secrets(options), indent=2)}')

# Checked before anything is started because it needs no client to answer it: a contradiction
# between the options is the one kind of failure that is cheaper to report than to act on.
if not validate_projects(options.get('projects'), options.get('account_manager_url')):
    logging.error(f'BOINC Add-on Operator stopped: the configured projects cannot be applied')
    sys.exit(1)

data_folder = args.data
logging.info(f'BOINC data folder {data_folder}')

prepare_data_folders(data_folder)

prepare_gui_rpc_auth(data_folder, options.get('gui_rpc_password'))

prepare_remote_hosts(data_folder, options.get('remote_hosts'))

link_global_prefs_override(data_folder, args.config, options)

prepare_cc_config(data_folder)

boinc_command = build_boinc_command(data_folder, options.get('allow_remote_gui_rpc'))
logging.debug(f'BOINC client command {boinc_command}')

boinc_process = subprocess.Popen(boinc_command)
logging.debug(f'BOINC client started with pid {boinc_process.pid}')

stopping_boinc_process = False

def signal_handler(number, frame):
    global stopping_boinc_process
    logging.debug(f'Caught signal {number}')
    # BOINC's client treats SIGHUP/SIGINT/SIGQUIT/SIGTERM identically (a clean, checkpointed
    # shutdown), so all four are forwarded the same way. Registering a handler for SIGINT already
    # replaces Python's default disposition (which would otherwise raise KeyboardInterrupt), so
    # excluding it here would swallow it instead of leaving it to that default.
    if boinc_process.poll() is None:
        logging.debug(f'Stopping BOINC client with signal {number}')
        stopping_boinc_process = True
        boinc_process.send_signal(number)

signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
# Only true once the handlers above are registered, so it doubles as a synchronization point for
# tests that need to signal this process and know the signal will actually be handled.
logging.info(f'BOINC Add-on Operator started')

boinc_process_initialized = False
while boinc_process.poll() is None and not boinc_process_initialized:
    sleep(0.5)
    boinc_process_initialized = get_state(data_folder)
    if boinc_process_initialized:
        logging.debug(f'BOINC client initialized')
    else:
        logging.debug(f'Waiting for BOINC client to initialize')

# A stop requested during initialization (a signal, or the client dying on its own) already means
# there is nothing left to configure: skipping this avoids running boinccmd against a client that
# is no longer there to answer it, which would otherwise be misreported as a configuration failure.
if not stopping_boinc_process and boinc_process.poll() is None:
    projects_configured = configure_boinc_projects(data_folder, options.get('account_manager_url'), options.get('account_manager_username'), options.get('account_manager_password'))

    # Asked again after the call and not only before it: attaching an account manager polls it over
    # the network from inside boinccmd, so a stop arriving meanwhile leaves it talking to a client
    # that is already gone. That is a stop, not a configuration mistake, and 3.8.5 drew the same
    # line for a stop during initialization.
    stopping = stopping_boinc_process or boinc_process.poll() is not None

    if not projects_configured and not stopping:
        boinc_process.send_signal(signal.SIGTERM)
        boinc_process.wait()
        logging.error(f'BOINC Add-on Operator stopped: failed to configure BOINC projects')
        sys.exit(1)

    if not stopping:
        # Reconciling happens once, here: Home Assistant cannot apply an options change without
        # restarting the app, so there is nothing new to read afterwards. Attaching is a local RPC
        # against a client that has already answered --get_state, so a failure here is rare enough
        # that saying so and moving on beats keeping the operator awake to try again.
        unattached_projects = configure_projects(data_folder, options.get('projects'))
        if unattached_projects:
            logging.warning(f'These projects could not be attached and will be attempted again when the app restarts: {", ".join(unattached_projects)}')

if args.exit_immediately:
    logging.warning(f'Exiting immediately after BOINC client is started')
    stopping_boinc_process = True
    boinc_process.send_signal(signal.SIGTERM)
    boinc_process.wait()

# Everything is configured by this point, so block on the client rather than polling it. Keep this
# a bare wait(): with no timeout it is a blocking waitpid(), while wait(timeout=...) is a busy loop
# sleeping up to 50ms a turn -- worse than the sleep(0.5) it replaced -- so anything that needs to
# wake up periodically here has to be built some other way. It returns immediately if the client is
# already gone.
boinc_process.wait()

logging.debug(f'BOINC client stopped with code {boinc_process.returncode}')

# Only a client that stopped on its own is a failure: the operator asking it to stop is how both a
# Supervisor stop and --exit-immediately end, whatever code the client reports for that.
if not stopping_boinc_process and boinc_process.returncode != 0:
    logging.error(f'BOINC Add-on Operator stopped: BOINC client exited with code {boinc_process.returncode}')
    sys.exit(1)

logging.info(f'BOINC Add-on Operator stopped')
