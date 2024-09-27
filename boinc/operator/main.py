import argparse
import json
import logging
import os
import signal
import subprocess
from time import sleep

from folders import prepare_data_folders
from gui_rpc_auth import prepare_gui_rpc_auth

parser = argparse.ArgumentParser(prog='operator')

parser.add_argument('--options', type=argparse.FileType('r', encoding='UTF-8'), required=True, help='Configuration file')
parser.add_argument('--data', type=str, required=True, help='BOINC data folder')
parser.add_argument("--log-level", default=logging.INFO, type=lambda x: getattr(logging, x))

args = parser.parse_args()
logging.basicConfig(level=args.log_level, format='%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

logging.info(f'Starting BOINC Add-on Operator with pid {os.getpid()}')
logging.info(f'Configuration loaded from {args.options.name}')

options = json.load(args.options)
logging.debug(f'Current configuration\n{json.dumps(options, indent=2)}')

data_folder = args.data
logging.info(f'BOINC data folder {data_folder}')

prepare_data_folders(data_folder)

prepare_gui_rpc_auth(data_folder, options.get('gui_rpc_auth'))

boinc_process = subprocess.Popen(["boinc", "--dir", f'{data_folder}'])
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

while boinc_process.poll() is None:
    sleep(0.5)

logging.debug(f'BOINC client stopped with code {boinc_process.returncode}')
logging.info(f'BOINC Add-on Operator stopped')
