import json
import logging
import os
import xml.etree.ElementTree as ElementTree

ROOT_ELEMENT = 'global_preferences'

# The preferences this operator owns, in the order they are written. Everything else in
# global_prefs_override.xml belongs to whoever put it there (boinctui, a remote BOINC Manager)
# and is preserved untouched.
MANAGED_PREFERENCES = ('start_hour', 'end_hour', 'niu_max_ncpus_pct', 'niu_cpu_usage_limit')

# What the operator wrote on its last run. BOINC cannot record this for us: the client writes the
# blob a GUI sends it verbatim and drops any tag it does not know, so a marker inside the XML would
# not survive the first edit from boinctui.
MANAGED_STATE_FILE = '.managed_global_prefs.json'

def convert_time_to_boinc_format(time: str) -> float:
    hours, minutes = map(int, time.split(':'))
    return hours + minutes / 100

def build_managed_preferences(data: dict) -> dict:
    preferences = {}

    start_hour = data.get('start_hour')
    end_hour = data.get('end_hour')

    if (start_hour is None) != (end_hour is None):
        # BOINC fills the missing half with its own default of 0, midnight, so writing only one of
        # them produces a window nobody asked for: start_hour alone stops computing at midnight,
        # end_hour alone never starts before it. Drop the pair and let BOINC compute all the time,
        # which is what an unset schedule means.
        logging.warning(f'Ignoring the computing schedule: start_hour and end_hour must both be set to define a window')
        start_hour = end_hour = None

    if start_hour is not None:
        preferences['start_hour'] = convert_time_to_boinc_format(start_hour)

    if end_hour is not None:
        preferences['end_hour'] = convert_time_to_boinc_format(end_hour)

    max_num_cpus = data.get('max_ncpus')
    if max_num_cpus is not None:
        preferences['niu_max_ncpus_pct'] = max_num_cpus

    max_cpu_usage = data.get('cpu_usage_limit')
    if max_cpu_usage is not None:
        preferences['niu_cpu_usage_limit'] = max_cpu_usage

    return preferences

def read_managed_state(data_folder: str) -> dict:
    state_file = f'{data_folder}/{MANAGED_STATE_FILE}'
    if not os.path.exists(state_file):
        return {}

    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
    except (OSError, ValueError) as error:
        logging.warning(f'Ignoring unreadable {MANAGED_STATE_FILE}: {error}')
        return {}

    if not isinstance(state, dict):
        logging.warning(f'Ignoring {MANAGED_STATE_FILE}, expected an object')
        return {}

    return state

def write_managed_state(data_folder: str, preferences: dict) -> None:
    with open(f'{data_folder}/{MANAGED_STATE_FILE}', 'w') as f:
        json.dump(preferences, f, indent=2, sort_keys=True)

def read_preferences_tree(global_prefs_override: str) -> ElementTree.Element:
    if not os.path.isfile(global_prefs_override):
        return ElementTree.Element(ROOT_ELEMENT)

    try:
        root = ElementTree.parse(global_prefs_override).getroot()
    except ElementTree.ParseError as error:
        logging.warning(f'Regenerating unparseable global_prefs_override.xml: {error}')
        return ElementTree.Element(ROOT_ELEMENT)

    if root.tag != ROOT_ELEMENT:
        logging.warning(f'Regenerating global_prefs_override.xml, expected a {ROOT_ELEMENT} root but found {root.tag}')
        return ElementTree.Element(ROOT_ELEMENT)

    return root

def merge_managed_preferences(root: ElementTree.Element, preferences: dict, previous: dict) -> None:
    for name in MANAGED_PREFERENCES:
        element = root.find(name)

        if name in preferences:
            if element is None:
                element = ElementTree.SubElement(root, name)
            element.text = str(preferences[name])
        elif element is not None and name in previous:
            # The operator wrote it and the option is now gone, so removing it is what the user
            # asked for. A managed preference we never wrote was set from outside and stays.
            root.remove(element)
            logging.debug(f'Removed {name} from global_prefs_override.xml, its option is no longer set')

def write_preferences_tree(global_prefs_override: str, root: ElementTree.Element) -> None:
    ElementTree.indent(root, space='  ')
    if len(root) == 0:
        # BOINC parses XML with its own hand-rolled parser, so never hand it a self-closing
        # <global_preferences/>: the text forces an explicit closing tag.
        root.text = '\n'

    with open(global_prefs_override, 'w') as f:
        f.write(ElementTree.tostring(root, encoding='unicode'))

def link_global_prefs_override(data_folder: str, config_folder: str, data: dict) -> None:
    global_prefs_override = f'{data_folder}/global_prefs_override.xml'

    configured_global_prefs_override = f'{config_folder}/global_prefs_override.xml'
    if os.path.exists(configured_global_prefs_override):
        # lexists, not exists: a symlink left over from a previous run whose target is gone reads
        # as missing, and writing to it would recreate the file in the config folder.
        if os.path.lexists(global_prefs_override):
            os.remove(global_prefs_override)
            logging.debug(f'Removing existing global_prefs_override.xml')

        os.symlink(configured_global_prefs_override, global_prefs_override)
        logging.debug(f'Linked global_prefs_override.xml to {configured_global_prefs_override}')
        logging.info(f'Using global_prefs_override.xml to configure BOINC client')
        # The user owns the whole file in this mode, so the operator manages no preference at all.
        write_managed_state(data_folder, {})
        return

    if os.path.islink(global_prefs_override):
        os.remove(global_prefs_override)
        logging.debug(f'Removing global_prefs_override.xml symlink, {configured_global_prefs_override} is gone')

    preferences = build_managed_preferences(data)
    previous = read_managed_state(data_folder)

    root = read_preferences_tree(global_prefs_override)
    merge_managed_preferences(root, preferences, previous)
    write_preferences_tree(global_prefs_override, root)

    write_managed_state(data_folder, preferences)
