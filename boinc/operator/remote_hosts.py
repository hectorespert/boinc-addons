import logging

def prepare_remote_hosts(data_folder: str, remote_hosts: list[str] | None) -> None:
    with open(f'{data_folder}/remote_hosts.cfg', 'w') as f:
        if remote_hosts is None:
            logging.debug(f'No remote hosts to write')
        else:
            for remote_host in remote_hosts:
                f.write(f'{remote_host}\n')
                logging.debug(f'Writing remote host {remote_host}')
