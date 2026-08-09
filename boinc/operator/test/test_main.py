import os
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

OPERATOR_DIR = Path(__file__).resolve().parent.parent
MAIN_PY = OPERATOR_DIR / 'main.py'

# Neither fake talks to a real BOINC client: they only stand in for the two things main.py
# actually depends on from the outside — the client process's signal behavior, and boinccmd's
# text output — so the operator's own signal-forwarding and exit-code logic can be exercised as a
# real subprocess, the way TODO.md asked for once these bugs were fixed.
FAKE_BOINC = textwrap.dedent("""\
    #!/usr/bin/env bash
    set -u

    if [ -n "${FAKE_BOINC_EXIT_CODE:-}" ]; then
        touch "$BOINC_MARKER_FILE"
        exit "$FAKE_BOINC_EXIT_CODE"
    fi

    trap 'echo TERM > "$BOINC_SIGNAL_FILE"; exit 0' TERM
    trap 'echo INT > "$BOINC_SIGNAL_FILE"; exit 0' INT

    # Written only once the traps above are armed: the marker is what the tests wait on before
    # signalling, so it has to mean "this client can record a signal", not merely "it started".
    # Touching it any earlier leaves a window where a forwarded signal hits bash's default
    # disposition and the signal file is never written.
    touch "$BOINC_MARKER_FILE"

    while true; do
        sleep 0.05
    done
    """)

FAKE_BOINCCMD = textwrap.dedent("""\
    #!/usr/bin/env bash
    set -u

    if [ "$1" = "--get_state" ]; then
        if [ -n "${FAKE_BOINCCMD_GET_STATE_FAIL:-}" ]; then
            echo "boinccmd: the client isn't running" >&2
            exit 1
        fi
        echo "======== Time Stats ========"
        exit 0
    fi

    if [ "$1" = "--acct_mgr" ] && [ "$2" = "info" ]; then
        # Once the fake client has recorded that it caught a stop signal, answer the way the real
        # boinccmd would against a client that is no longer there to take the RPC.
        if [ -f "$BOINC_SIGNAL_FILE" ]; then
            echo "boinccmd: can't connect to local client" >&2
            exit 1
        fi
        printf 'Account manager info:\\n   Name: \\n   URL: \\n'
        exit 0
    fi

    exit 0
    """)


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class MainTestCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)

        bin_dir = base / 'bin'
        bin_dir.mkdir()
        write_executable(bin_dir / 'boinc', FAKE_BOINC)
        write_executable(bin_dir / 'boinccmd', FAKE_BOINCCMD)

        self.data_dir = base / 'data'
        self.config_dir = base / 'config'
        self.config_dir.mkdir()

        self.options_file = base / 'options.json'
        self.options_file.write_text('{}')

        self.log_file = base / 'operator.log'

        self.marker_file = base / 'boinc-started'
        self.signal_file = base / 'boinc-signal'

        self.env = dict(os.environ)
        self.env['PATH'] = f'{bin_dir}{os.pathsep}{self.env.get("PATH", "")}'
        self.env['BOINC_MARKER_FILE'] = str(self.marker_file)
        self.env['BOINC_SIGNAL_FILE'] = str(self.signal_file)

        self.proc = None

    def tearDown(self):
        # A bug in the code under test must never be able to hang this suite: whatever assertion
        # fails or times out above, make sure the subprocess is actually gone afterwards.
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=5)

    def start_operator(self, *extra_args, env=None):
        run_env = dict(self.env)
        if env:
            run_env.update(env)

        with open(self.log_file, 'w') as log:
            self.proc = subprocess.Popen(
                [
                    sys.executable, str(MAIN_PY),
                    '--options', str(self.options_file),
                    '--data', str(self.data_dir),
                    '--config', str(self.config_dir),
                    *extra_args,
                ],
                env=run_env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        return self.proc

    def log_contents(self) -> str:
        return self.log_file.read_text() if self.log_file.exists() else ''

    def wait_until(self, predicate, description: str, timeout: float = 10) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            if self.proc.poll() is not None and not predicate():
                self.fail(f'operator exited (code {self.proc.returncode}) before {description}:\n{self.log_contents()}')
            time.sleep(0.05)
        self.fail(f'timed out waiting for {description}:\n{self.log_contents()}')

    def wait_for_marker(self) -> None:
        self.wait_until(self.marker_file.exists, 'the fake BOINC client to start')

    def wait_for_operator_ready(self) -> None:
        # "started" is logged only after the signal handlers are registered, so waiting for it (in
        # addition to the marker file) avoids a race where a signal sent too early would hit
        # Python's default disposition instead of the operator's handler.
        self.wait_for_marker()
        self.wait_until(lambda: 'BOINC Add-on Operator started' in self.log_contents(),
                         'the operator to register its signal handlers')

    def read_signal(self) -> str:
        return self.signal_file.read_text().strip()

    def test_exit_immediately_flag_takes_no_value_and_stops_the_client(self):
        self.start_operator('--exit-immediately')
        self.wait_for_marker()

        self.proc.wait(timeout=10)

        self.assertEqual(self.proc.returncode, 0)
        self.assertEqual(self.read_signal(), 'TERM')

    def test_sigint_is_forwarded_to_the_client(self):
        self.start_operator()
        self.wait_for_operator_ready()

        self.proc.send_signal(signal.SIGINT)
        self.proc.wait(timeout=10)

        self.assertEqual(self.proc.returncode, 0)
        self.assertEqual(self.read_signal(), 'INT')

    def test_sigterm_is_forwarded_to_the_client(self):
        self.start_operator()
        self.wait_for_operator_ready()

        self.proc.send_signal(signal.SIGTERM)
        self.proc.wait(timeout=10)

        self.assertEqual(self.proc.returncode, 0)
        self.assertEqual(self.read_signal(), 'TERM')

    def test_operator_fails_when_the_client_exits_on_its_own(self):
        self.start_operator(env={'FAKE_BOINC_EXIT_CODE': '3'})
        self.wait_for_marker()

        self.proc.wait(timeout=10)

        self.assertEqual(self.proc.returncode, 1)

    def test_sigterm_during_initialization_stops_cleanly_without_a_configuration_failure(self):
        # --get_state always failing keeps the operator in its initialization loop until the
        # forwarded signal kills the fake client, exercising the extra fix: configure_boinc_projects
        # must not run against a client that is already gone.
        self.start_operator(env={'FAKE_BOINCCMD_GET_STATE_FAIL': '1'})
        self.wait_for_operator_ready()

        self.proc.send_signal(signal.SIGTERM)
        self.proc.wait(timeout=10)

        self.assertEqual(self.proc.returncode, 0)
        self.assertEqual(self.read_signal(), 'TERM')
        self.assertNotIn('failed to configure', self.log_contents())


if __name__ == '__main__':
    unittest.main()
