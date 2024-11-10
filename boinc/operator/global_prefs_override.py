import logging
import os
from dict2xml import dict2xml

def convert_time_to_boinc_format(time: str) -> float:
    hours, minutes = map(int, time.split(':'))
    return hours + minutes / 100

def link_global_prefs_override(data_folder: str, config_folder: str, data: dict) -> None:
    gui_rpc_auth = f'{data_folder}/global_prefs_override.xml'
    if os.path.exists(gui_rpc_auth):
        os.remove(gui_rpc_auth)
        logging.debug(f'Removing existing global_prefs_override.xml')

    configured_gui_rpc_auth = f'{config_folder}/global_prefs_override.xml'
    if os.path.exists(configured_gui_rpc_auth):
        os.symlink(configured_gui_rpc_auth, gui_rpc_auth)
        logging.debug(f'Linked global_prefs_override.xml to {configured_gui_rpc_auth}')
        logging.info(f'Using global_prefs_override.xml to configure BOINC client')

    preferences = {}

    start_hour = data.get('start_hour')
    if start_hour is not None:
        preferences['start_hour'] = convert_time_to_boinc_format(start_hour)

    end_hour = data.get('end_hour')
    if end_hour is not None:
        preferences['end_hour'] = convert_time_to_boinc_format(end_hour)

    max_num_cpus = data.get('max_ncpus')
    if max_num_cpus is not None:
        preferences['max_ncpus'] = max_num_cpus
        
    max_cpu_usage = data.get('cpu_usage_limit')
    if max_cpu_usage is not None:
        preferences['cpu_usage_limit'] = max_cpu_usage

    with open(gui_rpc_auth, 'w') as f:
        f.write(dict2xml(preferences, wrap="global_preferences", indent="  ", newlines=True))
