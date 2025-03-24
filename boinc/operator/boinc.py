
def build_boinc_command(data_folder: str, allow_remote_gui_rpc: bool) -> list:
    boinc_command = ["boinc", "--dir", f'{data_folder}', '--exit_when_idle']
    if allow_remote_gui_rpc:
        boinc_command.extend(["--allow_remote_gui_rpc"])
    return boinc_command
