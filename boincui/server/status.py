"""How a BOINC client describes what it is doing, translated for someone who is not running one.

The tables come from the client's own source so the wording matches what BOINC says about itself:
`suspend_reason_string()` and `run_mode_string()` in `lib/str_util.cpp`, and the constants in
`lib/common_defs.h`.
"""

import re

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

# What each mode is called on screen. The three labels and their descriptions are copied verbatim
# from BOINC's own Activity menu (`clientgui/AdvancedFrame.cpp:517-529`); `boinctui` uses the same
# three strings (`src/topmenu.cpp:89-91`). Anyone who has used either recognises this control.
ACTIVITY_MODES = (
    ('always', 'Run always', 'Allow work regardless of preferences'),
    ('auto', 'Run based on preferences', 'Allow work according to preferences'),
    ('never', 'Suspend', 'Stop work regardless of preferences'),
)

MODE_KEYS = {
    RUN_MODE_ALWAYS: 'always',
    RUN_MODE_AUTO: 'auto',
    RUN_MODE_NEVER: 'never',
}

# BOINC appends its own decoding of the CPUID to the model string -- e.g. "Intel(R) Core(TM) i7-8700
# CPU @ 3.20GHz [Family 6 Model 158 Stepping 10]" (`get_processor_info`, lib/hostinfo.cpp). It
# roughly doubles the length of the line and says nothing to someone glancing at a status page.
_CPUID_SUFFIX = re.compile(r'\s*\[[^]]*]\s*$')


def describe_activity(cc_status: dict | None) -> str:
    """One line saying whether the client is computing, and if not, why not.

    Deliberately silent about the run mode: the activity control on the page already shows it, and
    saying it here as well produced the likes of "Computing — computing when its settings allow".
    """
    if not cc_status:
        return 'Unknown'

    reason = cc_status.get('task_suspend_reason') or 0
    if reason:
        return f'Paused — {SUSPEND_REASONS.get(reason, "BOINC did not say why")}'
    if cc_status.get('task_mode') == RUN_MODE_NEVER:
        # Reached only in the moment between setting the mode and the client recomputing its
        # suspend reason, which it does on its own cycle rather than when the mode is set.
        return 'Paused — someone asked it to stop'
    return 'Computing'


def describe_processor(host_info) -> str | None:
    """The machine's processor in one line, e.g. "ARM · 14 cores".

    Returns None when the client described nothing usable, so the page can leave the line out
    instead of printing a heading with no information under it.

    `host_info` is whatever the library made of the reply, which is not always a dict: a
    self-closing tag becomes `True` and an empty one a bare string. A client that will not answer
    this request is not an error worth reporting on a status page, so it takes the same path as one
    that answers without saying anything.
    """
    if not isinstance(host_info, dict):
        return None

    model = _CPUID_SUFFIX.sub('', str(host_info.get('p_model') or '')).strip()
    # The vendor is a fallback rather than a second part of the line: it holds the CPUID string
    # ("GenuineIntel", "AuthenticAMD", "ARM"), and a model already begins with the readable form of
    # it. It is needed because on some machines the model is nothing *but* the decoding stripped
    # above -- an Apple Silicon host reports "[Impl 0x61 Arch 8 Variant 0x0 Part 0x000 Rev 0]" and
    # no name at all, verified against a real client -- which leaves the vendor as the only readable
    # thing on offer.
    if not model:
        model = str(host_info.get('p_vendor') or '').strip()
    parts = [model] if model else []

    cores = host_info.get('p_ncpus')
    # `True` is what the library makes of a self-closing tag, and it counts as an int here: without
    # excluding it, a client that sends `<p_ncpus/>` would be reported as having one core.
    if isinstance(cores, int) and not isinstance(cores, bool) and cores > 0:
        # A non-breaking space, because a long model name wraps this line on a phone and the count is
        # where it broke: "Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz · 12" / "cores". The line may
        # still wrap, now only at the separator, which leaves the count whole on the second line.
        parts.append(f'{cores}\N{NO-BREAK SPACE}core{"s" if cores > 1 else ""}')

    return ' · '.join(parts) or None


def describe_mode(cc_status: dict | None) -> str | None:
    """Which activity mode the buttons should show as selected.

    Reads `task_mode_perm`, not `task_mode`: a temporary mode set from BOINC Manager makes the two
    differ, and the temporary one reverts on its own, so marking it would highlight a state this
    control never set and cannot restore.
    """
    if not cc_status:
        return None
    return MODE_KEYS.get(cc_status.get('task_mode_perm'))
