import signal
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
MAIN_PY = SERVER_DIR / 'main.py'

STARTED_MARKER = 'BOINC UI started'
# Fixed rather than injectable, because it has to match `ingress_port` in config.yaml; Home Assistant
# reaches it on the container's own address, so nothing else on the host competes for it in practice.
INGRESS_PORT = 8099


class TestMain(unittest.TestCase):

    def test_should_log_hello_world_and_exit_when_asked_to_exit_immediately(self):
        result = subprocess.run(
            [sys.executable, str(MAIN_PY), '--log-level', 'DEBUG', '--exit-immediately'],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn('hello world', result.stderr)
        self.assertIn('BOINC UI stopped', result.stderr)
        # Without a server to run there is nothing to wait for, so this run must not have blocked.
        self.assertNotIn(STARTED_MARKER, result.stderr)

    def test_should_keep_running_until_it_is_signalled(self):
        for number in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number):
                process = subprocess.Popen(
                    [sys.executable, str(MAIN_PY), '--log-level', 'DEBUG'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    consumed = self.wait_until_started(process)
                    # Still running: an entrypoint that returned here would show up in Supervisor as
                    # an app that stopped on its own moments after being started.
                    self.assertIsNone(process.poll())

                    process.send_signal(number)
                    _, remaining = process.communicate(timeout=30)
                except BaseException:
                    process.kill()
                    process.communicate()
                    raise

                # The lines read while waiting are already off the pipe, so communicate() only
                # returns what came after them.
                stderr = consumed + remaining
                self.assertEqual(0, process.returncode)
                self.assertIn('hello world', stderr)
                self.assertIn('BOINC UI stopped', stderr)

    def test_should_serve_the_page_while_it_is_running(self):
        process = subprocess.Popen(
            [sys.executable, str(MAIN_PY), '--log-level', 'DEBUG'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.wait_until_started(process)
            with urllib.request.urlopen(f'http://127.0.0.1:{INGRESS_PORT}/', timeout=10) as page:
                status, body = page.status, page.read().decode()
        finally:
            process.terminate()
            process.communicate(timeout=30)

        self.assertEqual(200, status)
        self.assertIn('BOINC UI', body)

    def test_should_release_the_port_once_it_is_stopped(self):
        process = subprocess.Popen(
            [sys.executable, str(MAIN_PY), '--log-level', 'DEBUG'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.wait_until_started(process)
        except BaseException:
            process.kill()
            process.communicate()
            raise
        process.terminate()
        process.communicate(timeout=30)

        # The listening socket is closed explicitly on shutdown, so a stopped app really is gone
        # rather than lingering long enough to make the next start fail on a bound port.
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(f'http://127.0.0.1:{INGRESS_PORT}/', timeout=5)

    def wait_until_started(self, process):
        consumed = ''
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            line = process.stderr.readline()
            consumed += line
            if STARTED_MARKER in line:
                return consumed
            if not line and process.poll() is not None:
                break
        self.fail(f'main.py never logged "{STARTED_MARKER}", got:\n{consumed}')


if __name__ == '__main__':
    unittest.main()
