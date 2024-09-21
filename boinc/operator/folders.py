import logging
import os


def prepare_data_folders(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)
        logging.debug(f'Creating BOINC data folder in {path}')

    if not os.path.exists(f'{path}/slots'):
        os.mkdir(f'{path}/slots')

    if not os.path.exists(f'{path}/locale'):
        os.mkdir(f'{path}/locale')