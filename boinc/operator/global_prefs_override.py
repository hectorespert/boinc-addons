import json
import logging
import os
import xml.etree.ElementTree as ElementTree

ROOT_ELEMENT = 'global_preferences'

# The preferences this operator owns, in the order they are written: the computing schedule pair,
# then the in-use CPU limits, then their not-in-use ("niu_") counterparts, then the disk limits and
# the work buffer -- the same order BOINC Manager uses in its own preferences dialog. Everything
# else in global_prefs_override.xml belongs to whoever put it there (boinctui, a remote BOINC
# Manager) and is preserved untouched.
MANAGED_PREFERENCES = (
    'start_hour', 'end_hour',
    'max_ncpus_pct', 'cpu_usage_limit',
    'niu_max_ncpus_pct', 'niu_cpu_usage_limit',
    'disk_max_used_gb', 'disk_max_used_pct', 'disk_min_free_gb',
    'work_buf_min_days', 'work_buf_additional_days',
)

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

    # The two hours are written as a pair or not at all, the same way BOINC Manager always sets
    # both in its preferences mask. Anything else is a window the user did not ask for.
    if (start_hour is None) != (end_hour is None):
        # BOINC fills the missing half with its own default of 0, midnight, so writing only one of
        # them produces a window nobody asked for: start_hour alone stops computing at midnight,
        # end_hour alone never starts before it. Let BOINC compute all the time instead, which is
        # what an unset schedule means.
        logging.warning(f'Ignoring the computing schedule: start_hour and end_hour must both be set to define a window')
    elif start_hour is not None:
        start_hour = convert_time_to_boinc_format(start_hour)
        end_hour = convert_time_to_boinc_format(end_hour)

        if start_hour == end_hour:
            # BOINC reads an equal pair as no restriction at all (TIME_SPAN::suspended returns
            # false when start_hour == end_hour), so it silently means the opposite of a schedule.
            # BOINC Manager rejects this outright in its own preferences dialog.
            logging.warning(f'Ignoring the computing schedule: start_hour and end_hour are both {start_hour}, which BOINC reads as no restriction')
        else:
            preferences['start_hour'] = start_hour
            preferences['end_hour'] = end_hour

    # These two apply while the computer is in use, and BOINC itself falls back to them for the
    # not-in-use case below when its counterpart is not set (lib/prefs.cpp, GLOBAL_PREFS::parse_override,
    # on the closing </global_preferences> tag: "if not-in-use prefs weren't specified, use in-use
    # counterpart").
    max_num_cpus = data.get('max_ncpus')
    if max_num_cpus is not None:
        preferences['max_ncpus_pct'] = max_num_cpus

    max_cpu_usage = data.get('cpu_usage_limit')
    if max_cpu_usage is not None:
        preferences['cpu_usage_limit'] = max_cpu_usage

    # These two apply only while the computer is not in use, overriding the fallback above.
    max_num_cpus_idle = data.get('max_ncpus_idle')
    if max_num_cpus_idle is not None:
        preferences['niu_max_ncpus_pct'] = max_num_cpus_idle

    max_cpu_usage_idle = data.get('cpu_usage_limit_idle')
    if max_cpu_usage_idle is not None:
        preferences['niu_cpu_usage_limit'] = max_cpu_usage_idle

    # The three disk limits are independent and the client applies the *least* of them
    # (CLIENT_STATE::allowed_disk_usage, client/cs_prefs.cpp), so setting one does not disable
    # another -- which is why all three are exposed rather than a chosen pair. Zero is meaningful
    # for the first two and means "no limit": the client skips a limit whose value is falsy, so
    # writing 0 is not the same as leaving the option unset, which removes the tag entirely and
    # restores BOINC's own default.
    disk_max_used_gb = data.get('disk_max_used_gb')
    if disk_max_used_gb is not None:
        preferences['disk_max_used_gb'] = disk_max_used_gb

    disk_max_used_pct = data.get('disk_max_used_pct')
    if disk_max_used_pct is not None:
        preferences['disk_max_used_pct'] = disk_max_used_pct

    disk_min_free_gb = data.get('disk_min_free_gb')
    if disk_min_free_gb is not None:
        preferences['disk_min_free_gb'] = disk_min_free_gb

    # How much work to keep queued. These two add up: the client asks for work until it holds
    # work_buf_min_days, and tops up to work_buf_min_days + work_buf_additional_days when it talks
    # to a project anyway. Both are clamped at zero by the client (GLOBAL_PREFS::parse), and the
    # schema already refuses a negative, so nothing is validated here.
    work_buf_min_days = data.get('work_buf_min_days')
    if work_buf_min_days is not None:
        preferences['work_buf_min_days'] = work_buf_min_days

    work_buf_additional_days = data.get('work_buf_additional_days')
    if work_buf_additional_days is not None:
        preferences['work_buf_additional_days'] = work_buf_additional_days

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
