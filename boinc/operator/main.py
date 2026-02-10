import argparse
import json
import logging
import os
import signal
import subprocess
import threading
from time import sleep

from boinc import build_boinc_command
from boinccmd import configure_boinc_projects, get_state
from cc_config import prepare_cc_config
from folders import prepare_data_folders
from global_prefs_override import link_global_prefs_override
from gui_rpc_auth import prepare_gui_rpc_auth
from remote_hosts import prepare_remote_hosts

parser = argparse.ArgumentParser(prog='operator')

parser.add_argument('--options', type=argparse.FileType('r', encoding='UTF-8'), required=True, help='Configuration file')
parser.add_argument('--data', type=str, required=True, help='BOINC data folder')
parser.add_argument('--config', type=str, required=True, help='Add-on config folder')
parser.add_argument("--log-level", default=logging.INFO, type=lambda x: getattr(logging, x))
parser.add_argument("--exit-immediately", type=bool, help="Exit immediately after BOINC client is started", default=False)

args = parser.parse_args()
logging.basicConfig(level=args.log_level, format='%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

current_pid = os.getpid()
logging.info(f'Starting BOINC Add-on Operator with pid {current_pid}')

if current_pid == 1:
    logging.warning('Protection Mode is enabled. BOINC requires system-wide usage monitoring to function properly.')

logging.info(f'Configuration loaded from {args.options.name}')

options = json.load(args.options)
logging.debug(f'Current configuration\n{json.dumps(options, indent=2)}')

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

def signal_handler(number, frame):
    logging.debug(f'Caught signal {number}')
    if  number != signal.SIGINT and boinc_process.poll() is None:
        logging.debug(f'Stopping BOINC client with signal {number}')
        boinc_process.send_signal(number)

logging.info(f'BOINC Add-on Operator started')
signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Flag to indicate if configuration thread should terminate the process
should_terminate = threading.Event()

def configure_boinc_in_background():
    """Background thread to wait for BOINC initialization and configure projects"""
    try:
        # Wait for BOINC client to initialize
        boinc_process_initialized = False
        while boinc_process.poll() is None and not boinc_process_initialized:
            boinc_process_initialized = get_state(data_folder)
            if boinc_process_initialized:
                logging.debug(f'BOINC client initialized')
            else:
                logging.debug(f'Waiting for BOINC client to initialize')
                # Sleep briefly before next check if not initialized
                sleep(0.5)
        
        # If process already terminated, exit thread
        if boinc_process.poll() is not None:
            return
        
        # Configure BOINC projects
        projects_configured = configure_boinc_projects(
            data_folder,
            options.get('account_manager_url'),
            options.get('account_manager_username'),
            options.get('account_manager_password')
        )
        
        if not projects_configured:
            logging.error('Failed to configure BOINC projects, terminating')
            should_terminate.set()
            boinc_process.send_signal(signal.SIGTERM)
            return
        
        if args.exit_immediately:
            logging.warning(f'Exiting immediately after BOINC client is started')
            should_terminate.set()
            boinc_process.send_signal(signal.SIGTERM)
    except Exception as e:
        logging.error(f'Error in configuration thread: {e}')
        should_terminate.set()
        if boinc_process.poll() is None:
            boinc_process.send_signal(signal.SIGTERM)

# Start configuration in background thread
config_thread = threading.Thread(target=configure_boinc_in_background, daemon=True)
config_thread.start()

# Main thread waits efficiently for process to exit
boinc_process.wait()

logging.debug(f'BOINC client stopped with code {boinc_process.returncode}')
logging.info(f'BOINC Add-on Operator stopped')
