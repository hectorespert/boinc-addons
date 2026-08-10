import asyncio
import socket
import sys
import threading
import unittest
from hashlib import md5
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boinc  # noqa: E402
from boinc import AuthenticationFailed, CannotConnect, NotConfigured, read_state  # noqa: E402

END = b'\x03'
PASSWORD = 'correct horse'

NO_TASKS = '<boinc_gui_rpc_reply>\n<results>\n</results>\n</boinc_gui_rpc_reply>'
ONE_TASK = """<boinc_gui_rpc_reply>
<results>
<result>
<name>task_one</name>
<project_url>https://example.org/</project_url>
<active_task>
<active_task_state>1</active_task_state>
<fraction_done>0.25</fraction_done>
</active_task>
</result>
</results>
</boinc_gui_rpc_reply>"""
PROJECTS = """<boinc_gui_rpc_reply>
<projects>
<project>
<master_url>https://example.org/</master_url>
<project_name>Example</project_name>
</project>
</projects>
</boinc_gui_rpc_reply>"""
CC_STATUS = '<boinc_gui_rpc_reply>\n<cc_status>\n<task_mode>2</task_mode>\n</cc_status>\n</boinc_gui_rpc_reply>'


class FakeBoincClient:
    """A GUI RPC server that speaks just enough of the protocol to exercise our side of it.

    The handshake mirrors BOINC's own (lib/gui_rpc_client.cpp): <auth1/> is answered with a nonce,
    and <auth2> is accepted only when it carries md5(nonce + password).
    """

    def __init__(self, password=PASSWORD, tasks=ONE_TASK):
        self.password = password
        self.tasks = tasks
        self.connections_seen = 0
        self.connections_closed = 0
        self._server = None
        self._loop = None
        self._thread = None
        self.port = None

    def __enter__(self):
        ready = threading.Event()
        self._thread = threading.Thread(target=self._serve, args=(ready,), daemon=True)
        self._thread.start()
        ready.wait(10)
        return self

    def __exit__(self, *exc):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)

    def _serve(self, ready):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._server = self._loop.run_until_complete(
            asyncio.start_server(self._handle, '127.0.0.1', 0)
        )
        self.port = self._server.sockets[0].getsockname()[1]
        ready.set()
        self._loop.run_forever()

    async def _handle(self, reader, writer):
        self.connections_seen += 1
        nonce = '1234567890'
        authorized = False
        try:
            while True:
                request = (await reader.readuntil(END)).decode('ISO-8859-1')
                if '<auth1' in request:
                    reply = f'<boinc_gui_rpc_reply>\n<nonce>{nonce}</nonce>\n</boinc_gui_rpc_reply>'
                elif '<auth2' in request:
                    expected = md5((nonce + self.password).encode('UTF8')).hexdigest()
                    authorized = expected in request
                    tag = 'authorized' if authorized else 'unauthorized'
                    reply = f'<boinc_gui_rpc_reply>\n<{tag}/>\n</boinc_gui_rpc_reply>'
                elif '<get_cc_status' in request:
                    reply = CC_STATUS
                elif '<get_project_status' in request:
                    reply = PROJECTS
                elif '<get_results' in request:
                    reply = self.tasks
                else:
                    reply = '<boinc_gui_rpc_reply>\n<unauthorized/>\n</boinc_gui_rpc_reply>'
                writer.write(reply.encode('ISO-8859-1') + END)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self.connections_closed += 1
            writer.close()


class TestReadState(unittest.TestCase):

    def test_should_read_tasks_and_projects(self):
        with FakeBoincClient() as server:
            state = read_state('127.0.0.1', server.port, PASSWORD)

        self.assertEqual('task_one', state['results'][0]['name'])
        self.assertEqual(0.25, state['results'][0]['active_task']['fraction_done'])
        self.assertEqual('Example', state['projects'][0]['project_name'])

    def test_should_report_a_rejected_password_rather_than_empty_data(self):
        # The library does not check authorisation on its query methods, so without our explicit
        # check a wrong password would look like a client with nothing to do.
        with FakeBoincClient() as server:
            with self.assertRaises(AuthenticationFailed):
                read_state('127.0.0.1', server.port, 'wrong password')

    def test_should_treat_the_no_tasks_sentinel_as_an_empty_list(self):
        # With no results the library returns the string "\n" instead of a list.
        with FakeBoincClient(tasks=NO_TASKS) as server:
            state = read_state('127.0.0.1', server.port, PASSWORD)

        self.assertEqual([], state['results'])

    def test_should_close_the_connection_it_opened(self):
        # Upstream never closes the socket; this is what the vendored close() patch is for.
        with FakeBoincClient() as server:
            read_state('127.0.0.1', server.port, PASSWORD)
            deadline = threading.Event()
            deadline.wait(0.5)

            self.assertEqual(1, server.connections_seen)
            self.assertEqual(1, server.connections_closed)

    def test_should_report_a_host_that_refuses_the_connection(self):
        with socket.socket() as taken:
            taken.bind(('127.0.0.1', 0))
            unused_port = taken.getsockname()[1]

        with self.assertRaises(CannotConnect):
            read_state('127.0.0.1', unused_port, PASSWORD)

    def test_should_report_missing_configuration_without_touching_the_network(self):
        for host, password in ((None, PASSWORD), ('127.0.0.1', None), (None, None)):
            with self.subTest(host=host, password=password):
                with self.assertRaises(NotConfigured):
                    read_state(host, 31416, password)

    def test_should_default_the_port_when_none_is_configured(self):
        with FakeBoincClient() as server:
            original = boinc.DEFAULT_PORT
            boinc.DEFAULT_PORT = server.port
            try:
                state = read_state('127.0.0.1', None, PASSWORD)
            finally:
                boinc.DEFAULT_PORT = original

        self.assertEqual('task_one', state['results'][0]['name'])


if __name__ == '__main__':
    unittest.main()
