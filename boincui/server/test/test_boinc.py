import asyncio
import socket
import sys
import threading
import unittest
from hashlib import md5
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boinc  # noqa: E402
from boinc import read_all  # noqa: E402

END = b'\x03'
PASSWORD = 'correct horse'


def results_reply(*results: str) -> str:
    return '<boinc_gui_rpc_reply>\n<results>\n' + '\n'.join(results) + '\n</results>\n</boinc_gui_rpc_reply>'


def running_task(name='task_one', url='https://example.org/', done='0.25', deadline='4102444800'):
    return f"""<result>
<name>{name}</name>
<project_url>{url}</project_url>
<report_deadline>{deadline}</report_deadline>
<active_task>
<active_task_state>1</active_task_state>
<fraction_done>{done}</fraction_done>
</active_task>
</result>"""


QUEUED_TASK = """<result>
<name>waiting_one</name>
<project_url>https://example.org/</project_url>
</result>"""

FINISHED_TASK = """<result>
<name>done_one</name>
<project_url>https://example.org/</project_url>
<ready_to_report>1</ready_to_report>
</result>"""

PROJECTS = """<boinc_gui_rpc_reply>
<projects>
<project>
<master_url>https://example.org/</master_url>
<project_name>Example Project</project_name>
</project>
</projects>
</boinc_gui_rpc_reply>"""

NO_PROJECTS = '<boinc_gui_rpc_reply>\n<projects>\n</projects>\n</boinc_gui_rpc_reply>'
NO_TASKS = results_reply()


def cc_status(mode=2, suspend_reason=0):
    return (f'<boinc_gui_rpc_reply>\n<cc_status>\n<task_mode>{mode}</task_mode>\n'
            f'<task_suspend_reason>{suspend_reason}</task_suspend_reason>\n'
            '</cc_status>\n</boinc_gui_rpc_reply>')


class FakeBoincClient:
    """A GUI RPC server that speaks just enough of the protocol to exercise our side of it.

    The handshake mirrors BOINC's own (lib/gui_rpc_client.cpp): <auth1/> is answered with a nonce,
    and <auth2> is accepted only when it carries md5(nonce + password).
    """

    def __init__(self, password=PASSWORD, tasks=None, projects=PROJECTS, status=None):
        self.password = password
        self.tasks = tasks if tasks is not None else results_reply(running_task())
        self.projects = projects
        self.status = status if status is not None else cc_status()
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
        # Stopping the loop outright leaves the per-connection handler pending, which asyncio then
        # complains about at collection time -- noise in the test output that looks like a failure.
        asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop).result(timeout=10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)

    async def _shutdown(self):
        self._server.close()
        await self._server.wait_closed()
        pending = [task for task in asyncio.all_tasks(self._loop) if task is not asyncio.current_task()]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def as_client(self, name):
        return {'name': name, 'host': '127.0.0.1', 'port': self.port, 'password': PASSWORD}

    def _serve(self, ready):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._server = self._loop.run_until_complete(asyncio.start_server(self._handle, '127.0.0.1', 0))
        self.port = self._server.sockets[0].getsockname()[1]
        ready.set()
        self._loop.run_forever()

    async def _handle(self, reader, writer):
        self.connections_seen += 1
        nonce = '1234567890'
        try:
            while True:
                request = (await reader.readuntil(END)).decode('ISO-8859-1')
                if '<auth1' in request:
                    reply = f'<boinc_gui_rpc_reply>\n<nonce>{nonce}</nonce>\n</boinc_gui_rpc_reply>'
                elif '<auth2' in request:
                    expected = md5((nonce + self.password).encode('UTF8')).hexdigest()
                    tag = 'authorized' if expected in request else 'unauthorized'
                    reply = f'<boinc_gui_rpc_reply>\n<{tag}/>\n</boinc_gui_rpc_reply>'
                elif '<get_cc_status' in request:
                    reply = self.status
                elif '<get_project_status' in request:
                    reply = self.projects
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


def refused_port():
    with socket.socket() as taken:
        taken.bind(('127.0.0.1', 0))
        return taken.getsockname()[1]


class TestSingleClient(unittest.TestCase):

    def read_one(self, server, **overrides):
        client = server.as_client('machine')
        client.update(overrides)
        return read_all([client])[0]

    def test_should_read_running_tasks_with_their_project_name(self):
        with FakeBoincClient() as server:
            machine = self.read_one(server)

        self.assertIsNone(machine['error'])
        running = machine['state']['running']
        self.assertEqual(1, len(running))
        # Tasks only carry a URL; the readable name comes from joining against the project list.
        self.assertEqual('Example Project', running[0]['project'])
        self.assertEqual(0.25, running[0]['fraction_done'])
        self.assertEqual('task_one', running[0]['name'])

    def test_should_count_waiting_and_finished_tasks_without_listing_them(self):
        # A machine with a work buffer has dozens queued; the page shows what is running and counts
        # the rest.
        tasks = results_reply(running_task(), QUEUED_TASK, QUEUED_TASK, FINISHED_TASK)
        with FakeBoincClient(tasks=tasks) as server:
            state = self.read_one(server)['state']

        self.assertEqual(1, len(state['running']))
        self.assertEqual(2, state['queued'])
        self.assertEqual(1, state['ready_to_report'])

    def test_should_sort_running_tasks_by_deadline_and_tolerate_a_missing_one(self):
        no_deadline = running_task(name='undated').replace('<report_deadline>4102444800</report_deadline>\n', '')
        tasks = results_reply(
            running_task(name='later', deadline='4102531200'),
            no_deadline,
            running_task(name='sooner', deadline='4102444800'),
        )
        with FakeBoincClient(tasks=tasks) as server:
            running = self.read_one(server)['state']['running']

        self.assertEqual(['sooner', 'later', 'undated'], [task['name'] for task in running])

    def test_should_fall_back_to_the_url_when_the_project_has_no_name(self):
        with FakeBoincClient(projects=NO_PROJECTS) as server:
            running = self.read_one(server)['state']['running']

        self.assertEqual('https://example.org/', running[0]['project'])
        self.assertIsInstance(running[0]['project'], str)

    def test_should_describe_why_a_client_is_paused(self):
        with FakeBoincClient(status=cc_status(suspend_reason=1024)) as server:
            state = self.read_one(server)['state']

        self.assertIn('Paused', state['activity'])
        self.assertIn('processor is busy', state['activity'])

    def test_should_not_break_on_a_suspend_reason_it_does_not_know(self):
        with FakeBoincClient(status=cc_status(suspend_reason=99999)) as server:
            state = self.read_one(server)['state']

        self.assertIn('Paused', state['activity'])
        self.assertIn('did not say why', state['activity'])

    def test_should_report_a_rejected_password_rather_than_empty_data(self):
        # The library does not check authorisation on its query methods, so without our explicit
        # check a wrong password would look like a client with nothing to do.
        with FakeBoincClient() as server:
            machine = self.read_one(server, password='wrong password')

        self.assertEqual('auth_failed', machine['error_kind'])

    def test_should_treat_the_no_tasks_sentinel_as_an_empty_list(self):
        # With no results the library returns the string "\n" instead of a list.
        with FakeBoincClient(tasks=NO_TASKS, projects=NO_PROJECTS) as server:
            state = self.read_one(server)['state']

        self.assertEqual([], state['running'])
        self.assertEqual([], state['projects'])

    def test_should_close_the_connection_it_opened(self):
        # Upstream never closes the socket; this is what the vendored close() patch is for.
        with FakeBoincClient() as server:
            self.read_one(server)
            threading.Event().wait(0.5)

            self.assertEqual(1, server.connections_seen)
            self.assertEqual(1, server.connections_closed)

    def test_should_report_a_host_that_refuses_the_connection(self):
        machine = read_all([{'name': 'off', 'host': '127.0.0.1', 'port': refused_port(), 'password': PASSWORD}])[0]

        self.assertEqual('cannot_connect', machine['error_kind'])

    def test_should_report_a_client_missing_its_address_or_password(self):
        for client in ({'host': None, 'password': PASSWORD}, {'host': '127.0.0.1', 'password': None}):
            with self.subTest(client=client):
                self.assertEqual('not_configured', read_all([client])[0]['error_kind'])

    def test_should_default_the_port_when_none_is_configured(self):
        with FakeBoincClient() as server:
            original, boinc.DEFAULT_PORT = boinc.DEFAULT_PORT, server.port
            try:
                machine = read_all([{'host': '127.0.0.1', 'password': PASSWORD}])[0]
            finally:
                boinc.DEFAULT_PORT = original

        self.assertIsNone(machine['error'])

    def test_should_name_a_client_after_its_address_when_unnamed(self):
        with FakeBoincClient() as server:
            machine = read_all([{'host': '127.0.0.1', 'port': server.port, 'password': PASSWORD}])[0]

        self.assertEqual('127.0.0.1', machine['name'])


class TestSeveralClients(unittest.TestCase):

    def test_should_read_every_machine(self):
        with FakeBoincClient(tasks=results_reply(running_task(name='on_first'))) as first, \
                FakeBoincClient(tasks=results_reply(running_task(name='on_second'))) as second:
            machines = read_all([first.as_client('first'), second.as_client('second')])

        self.assertEqual(['first', 'second'], [machine['name'] for machine in machines])
        self.assertEqual('on_first', machines[0]['state']['running'][0]['name'])
        self.assertEqual('on_second', machines[1]['state']['running'][0]['name'])

    def test_should_keep_showing_the_machines_that_answer_when_one_does_not(self):
        # The reason every machine is polled concurrently with errors collected rather than raised:
        # one that is switched off must not cost you the others.
        unreachable = {'name': 'off', 'host': '127.0.0.1', 'port': refused_port(), 'password': PASSWORD}
        with FakeBoincClient() as server:
            machines = read_all([unreachable, server.as_client('on')])

        self.assertEqual('cannot_connect', machines[0]['error_kind'])
        self.assertIsNone(machines[1]['error'])
        self.assertEqual(1, len(machines[1]['state']['running']))

    def test_should_isolate_a_wrong_password_to_its_own_machine(self):
        with FakeBoincClient() as first, FakeBoincClient() as second:
            bad = first.as_client('bad')
            bad['password'] = 'wrong password'
            machines = read_all([bad, second.as_client('good')])

        self.assertEqual('auth_failed', machines[0]['error_kind'])
        self.assertIsNone(machines[1]['error'])

    def test_should_return_nothing_when_no_client_is_configured(self):
        self.assertEqual([], read_all([]))


if __name__ == '__main__':
    unittest.main()
