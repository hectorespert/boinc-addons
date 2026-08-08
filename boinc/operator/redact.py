SECRET_OPTIONS = ('gui_rpc_password', 'account_manager_password')

REDACTED = '***'

def redact_secrets(options: dict) -> dict:
    return {key: REDACTED if key in SECRET_OPTIONS and value is not None else value for key, value in options.items()}
