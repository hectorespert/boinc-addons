import argparse
import json
import logging
import os

from folders import prepare_data_folders

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

logging.info(f'BOINC Add-on Operator stopped')