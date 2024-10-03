from dict2xml import dict2xml


def prepare_cc_config(data_folder: str) -> None:
    data = {
        'options': {
            'allow_remote_gui_rpc': 0,
        },
        'log_flags': {
            'task': 1,
            'file_xfer': 1,
            'sched_ops': 1,
        },
    }

    with open(f'{data_folder}/cc_config.xml', 'w') as f:
        f.write(dict2xml(data, wrap="cc_config", indent="  ", newlines=True))
