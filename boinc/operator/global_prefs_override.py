
# rm -f /data/boinc/global_prefs_override.xml
# if bashio::fs.file_exists "/config/global_prefs_override.xml"; then
#     ln -s /config/global_prefs_override.xml /data/boinc/global_prefs_override.xml
# fi

def link_global_prefs_override(data_folder: str) -> None:
    return None