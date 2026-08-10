"""How a BOINC client describes what it is doing, translated for someone who is not running one.

The tables come from the client's own source so the wording matches what BOINC says about itself:
`suspend_reason_string()` and `run_mode_string()` in `lib/str_util.cpp`, and the constants in
`lib/common_defs.h`.
"""

# BOINC looks these up with an exact `switch`, not bit tests, and that is deliberate: the values
# look like flags up to 4096, but 4097 onwards are sequential and would collide with combinations
# (4097 == 4096 | 1). Matching on the exact value is the only correct reading.
SUSPEND_REASONS = {
    1: 'the computer is on battery power',
    2: 'the computer is in use',
    4: 'someone asked it to stop',
    8: 'the time of day is outside its schedule',
    16: 'it is measuring the computer speed',
    32: 'it has run out of the disk space it is allowed',
    128: 'nobody has used the computer recently',
    256: 'it has just started and is waiting a moment',
    512: 'a program it was told to avoid is running',
    1024: 'the processor is busy with something else',
    2048: 'it has used up its network allowance',
    4096: 'the operating system asked it to stop',
    4097: 'the computer is not on WiFi',
    4098: 'the battery is low',
    4099: 'the battery is too hot',
    4100: 'no BOINC window is open',
    4101: 'Podman is starting up',
    4102: 'it is waiting for the battery to charge',
    4103: 'it is waiting for the battery to cool down',
}

# 64 (CPU throttle) is missing on purpose: the client never reports it, as its own header notes.

RUN_MODE_ALWAYS = 1
RUN_MODE_AUTO = 2
RUN_MODE_NEVER = 3

RUN_MODES = {
    RUN_MODE_ALWAYS: 'always computing',
    RUN_MODE_AUTO: 'computing when its settings allow',
    RUN_MODE_NEVER: 'set never to compute',
}


def describe_activity(cc_status: dict | None) -> str:
    """One line saying whether the client is computing, and if not, why not."""
    if not cc_status:
        return 'Unknown'

    mode = cc_status.get('task_mode')
    reason = cc_status.get('task_suspend_reason') or 0

    if reason:
        return f'Paused — {SUSPEND_REASONS.get(reason, "BOINC did not say why")}'
    if mode == RUN_MODE_NEVER:
        return 'Paused — set never to compute'
    return f'Computing — {RUN_MODES.get(mode, "running")}'
