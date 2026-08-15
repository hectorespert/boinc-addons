SECRET_OPTIONS = ('gui_rpc_password', 'account_manager_password')

# Secrets nested inside a list-of-dict option, which the flat pass over the top level cannot reach.
# Missing one here means it reaches the DEBUG dump, and CI runs the image at DEBUG, so every build's
# public log would carry it.
SECRET_LIST_OPTIONS = {'projects': ('account_key',)}

REDACTED = '***'

def redact_entry(entry, secrets: tuple) -> dict:
    if not isinstance(entry, dict):
        return entry
    return {key: REDACTED if key in secrets and value is not None else value for key, value in entry.items()}

def redact_secrets(options: dict) -> dict:
    redacted = {}

    for key, value in options.items():
        if key in SECRET_OPTIONS and value is not None:
            redacted[key] = REDACTED
        elif key in SECRET_LIST_OPTIONS and isinstance(value, list):
            redacted[key] = [redact_entry(entry, SECRET_LIST_OPTIONS[key]) for entry in value]
        else:
            redacted[key] = value

    return redacted
