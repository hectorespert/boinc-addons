import sys
import threading
import unittest
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402
from app import Refresher, Snapshot, clients_from, create_app, format_due  # noqa: E402

# An URL that is fine to emit absolutely: it leaves the panel on purpose, or does not navigate.
EXTERNAL_PREFIXES = ('http://', 'https://', 'mailto:', '#')

URL_ATTRIBUTES = ('href', 'src', 'action', 'formaction')


def machine(name='pc', error=None, error_kind=None, running=(), queued=0, ready=0,
            projects=(('Example Project', 'https://example.org/'),), activity='Computing',
            mode='auto'):
    return {
        'name': name,
        'host': 'pc.local',
        'error': error,
        'error_kind': error_kind,
        'state': None if error else {
            'activity': activity,
            'mode': mode,
            'running': list(running),
            'queued': queued,
            'ready_to_report': ready,
            'projects': [{'name': n, 'url': u} for n, u in projects],
        },
    }


def task(name='task_one', project='Example Project', fraction_done=0.25, deadline=None):
    return {
        'name': name,
        'project': project,
        'fraction_done': fraction_done,
        'deadline': deadline if deadline is not None else datetime.now() + timedelta(days=2),
    }


def snapshot_of(*machines):
    snapshot = Snapshot()
    snapshot.store(list(machines))
    return snapshot


class UrlCollector(HTMLParser):
    """Collects every URL the page would make the browser resolve."""

    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in URL_ATTRIBUTES and value is not None:
                self.urls.append((tag, name, value))


class ModeButtonCollector(HTMLParser):
    """The activity buttons as {mode: whether it is shown as the current one}."""

    def __init__(self):
        super().__init__()
        self.buttons = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'button' and attrs.get('name') == 'mode':
            self.buttons[attrs.get('value')] = attrs.get('aria-pressed')


def modes_in(page):
    collector = ModeButtonCollector()
    collector.feed(page)
    return collector.buttons


def client_for(snapshot, clients=None):
    app = create_app(snapshot)
    app.config.update(TESTING=True, CLIENTS=clients if clients is not None else [])
    return app.test_client()


class TestStates(unittest.TestCase):
    """Every state the page can be in, rendered without touching the network."""

    def page_for(self, snapshot):
        response = client_for(snapshot).get('/')
        self.assertEqual(200, response.status_code)
        return response.get_data(as_text=True)

    def test_should_say_it_is_still_checking_before_the_first_refresh(self):
        self.assertIn('Checking your BOINC clients', self.page_for(Snapshot()))

    def test_should_explain_what_to_fill_in_when_nothing_is_configured(self):
        page = self.page_for(snapshot_of())

        self.assertIn('No BOINC client is configured', page)
        self.assertIn('Configuration tab', page)

    def test_should_show_running_tasks_with_progress_and_deadline(self):
        page = self.page_for(snapshot_of(machine(running=[task()], queued=12, ready=2)))

        self.assertIn('Example Project', page)
        self.assertIn('25%', page)
        self.assertIn('in 1 day', page)
        self.assertIn('12 waiting', page)
        self.assertIn('2 finished', page)

    def test_should_keep_the_task_identifier_out_of_the_way_but_reachable(self):
        # BOINC's names say nothing to a reader, but they are what you would search for in boinctui.
        page = self.page_for(snapshot_of(machine(running=[task(name='LATeah4013L03_925.0_0')])))

        self.assertIn('title="LATeah4013L03_925.0_0"', page)
        self.assertNotIn('>LATeah4013L03_925.0_0<', page)

    def test_should_say_when_a_connected_machine_is_running_nothing(self):
        page = self.page_for(snapshot_of(machine(running=[], queued=5)))

        self.assertIn('Nothing is running right now', page)

    def test_should_show_why_a_machine_is_paused(self):
        page = self.page_for(snapshot_of(machine(activity='Paused — the processor is busy with something else')))

        self.assertIn('the processor is busy', page)

    def test_should_report_each_failure_kind_against_its_own_machine(self):
        for kind, expected in (
            ('cannot_connect', 'Cannot be reached'),
            ('auth_failed', 'Rejected the password'),
            ('not_configured', 'Not fully configured'),
            ('error', 'Something went wrong'),
        ):
            with self.subTest(kind=kind):
                page = self.page_for(snapshot_of(machine(error='boom', error_kind=kind)))
                self.assertIn(expected, page)

    def test_should_still_show_the_machines_that_work_when_one_is_broken(self):
        page = self.page_for(snapshot_of(
            machine(name='broken', error='boom', error_kind='cannot_connect'),
            machine(name='working', running=[task(project='Rosetta@home')]),
        ))

        self.assertIn('Cannot be reached', page)
        self.assertIn('working', page)
        self.assertIn('Rosetta@home', page)

    def test_should_render_a_section_per_machine_in_configured_order(self):
        page = self.page_for(snapshot_of(machine(name='first'), machine(name='second')))

        self.assertLess(page.index('first'), page.index('second'))


class TestFormatDue(unittest.TestCase):

    def test_should_describe_a_deadline_in_readable_units(self):
        # Each delta carries a small margin because format_due reads the clock itself: the unit is
        # truncated, never rounded up, so a deadline is never described as further away than it is.
        now = datetime.now()
        for delta, expected in (
            (timedelta(days=3, minutes=1), 'in 3 days'),
            (timedelta(days=1, hours=2), 'in 1 day'),
            (timedelta(hours=5, minutes=1), 'in 5 hours'),
            (timedelta(minutes=90), 'in 1 hour'),
            (timedelta(seconds=30), 'in under a minute'),
            (timedelta(days=-1), 'overdue'),
        ):
            with self.subTest(delta=delta):
                self.assertEqual(expected, format_due(now + delta))

    def test_should_never_overstate_the_time_left(self):
        # Truncating up would tell someone they have three days when they have two and a bit.
        self.assertEqual('in 2 days', format_due(datetime.now() + timedelta(days=2, hours=23)))

    def test_should_cope_with_a_task_that_has_no_deadline(self):
        self.assertEqual('—', format_due(None))

    def test_should_not_mix_naive_and_aware_datetimes(self):
        # Deadlines arrive naive; comparing them against an aware "now" raises TypeError, which
        # would take the whole page down rather than one cell.
        try:
            format_due(datetime.now() + timedelta(days=1))
        except TypeError as error:
            self.fail(f'format_due compared incompatible datetimes: {error}')


class TestClientsFrom(unittest.TestCase):

    def test_should_use_the_client_list_when_present(self):
        clients = clients_from({'clients': [{'host': 'a', 'password': 'x'}]})

        self.assertEqual([{'host': 'a', 'password': 'x'}], clients)

    def test_should_accept_the_old_single_client_options(self):
        # Supervisor silently drops options missing from the schema, so removing these outright
        # would wipe an existing configuration. It still has to say so in the log.
        with self.assertLogs(level='WARNING') as logged:
            clients = clients_from({'boinc_host': 'pc', 'boinc_port': 31417, 'gui_rpc_password': 'x'})

        self.assertEqual([{'name': 'pc', 'host': 'pc', 'port': 31417, 'password': 'x'}], clients)
        self.assertIn('will stop working', ''.join(logged.output))

    def test_should_prefer_the_list_over_the_old_options(self):
        clients = clients_from({
            'clients': [{'host': 'new', 'password': 'x'}],
            'boinc_host': 'old', 'gui_rpc_password': 'y',
        })

        self.assertEqual('new', clients[0]['host'])

    def test_should_return_nothing_when_unconfigured(self):
        self.assertEqual([], clients_from({}))


class TestIngressConstraint(unittest.TestCase):
    """Home Assistant ingress serves this app under /api/hassio_ingress/<token>/ and strips that
    prefix without telling the app what it was, so a root-relative URL escapes the panel and lands on
    the Home Assistant root instead. These are the guard for that, and they are the reason this
    add-on renders on the server rather than shipping a bundled front end."""

    def assert_no_root_relative_urls(self, page):
        collector = UrlCollector()
        collector.feed(page)

        self.assertTrue(collector.urls, 'the page emitted no URLs at all, so this proves nothing')
        for tag, attribute, url in collector.urls:
            with self.subTest(tag=tag, attribute=attribute, url=url):
                if url.startswith(EXTERNAL_PREFIXES):
                    continue
                self.assertFalse(
                    url.startswith('/'),
                    f'<{tag} {attribute}="{url}"> is root-relative and would escape the ingress path',
                )

    def test_should_never_emit_a_root_relative_url_in_any_state(self):
        for name, snapshot in (
            ('checking', Snapshot()),
            ('unconfigured', snapshot_of()),
            ('connected', snapshot_of(machine(running=[task()]))),
            ('broken', snapshot_of(machine(error='boom', error_kind='cannot_connect'))),
        ):
            with self.subTest(state=name):
                self.assert_no_root_relative_urls(client_for(snapshot).get('/').get_data(as_text=True))

    def test_should_redirect_relatively_after_refreshing(self):
        response = client_for(Snapshot()).post('/refresh')

        self.assertEqual(302, response.status_code)
        location = response.headers['Location']
        self.assertFalse(
            location.startswith('/'),
            f'Location: {location} is root-relative and would send the browser out of the panel',
        )


class TestRefreshButton(unittest.TestCase):

    def test_should_ask_for_a_poll_without_waiting_for_it(self):
        # Polling inline would hold the request for as long as the slowest machine takes to answer,
        # which is the very thing the background refresher exists to avoid.
        calls = []
        app = create_app(Snapshot())
        app.config['REFRESHER'] = type('FakeRefresher', (), {
            'request_refresh': lambda self: calls.append('requested'),
            'refresh_once': lambda self: calls.append('polled inline'),
        })()

        app.test_client().post('/refresh')

        self.assertEqual(['requested'], calls)

    def test_should_still_redirect_when_no_refresher_is_wired_in(self):
        # The app is created without one in the unit tests, and must not fall over because of it.
        self.assertEqual(302, client_for(Snapshot()).post('/refresh').status_code)


class TestActivityControl(unittest.TestCase):
    """The three-way control, and the route behind it."""

    def page_with(self, **kwargs):
        return client_for(snapshot_of(machine(**kwargs))).get('/').get_data(as_text=True)

    def test_should_offer_the_three_modes_boinc_itself_names(self):
        page = self.page_with()

        for label in ('Run always', 'Run based on preferences', 'Suspend'):
            self.assertIn(label, page)
        self.assertIn('Allow work regardless of preferences', page)

    def test_should_mark_the_mode_the_machine_is_actually_in(self):
        self.assertEqual(
            {'always': 'false', 'auto': 'false', 'never': 'true'},
            modes_in(self.page_with(mode='never')),
        )

    def test_should_not_offer_the_control_for_a_machine_it_cannot_read(self):
        # There is nothing to act on, and the buttons would only mislead.
        page = self.page_with(error='boom', error_kind='cannot_connect')

        self.assertEqual({}, modes_in(page))

    def test_should_explain_a_connection_that_was_refused_rather_than_absent(self):
        page = self.page_with(error='hung up', error_kind='rejected')

        self.assertIn('Refused the connection', page)
        self.assertIn('allowed to connect', page)


class TestModeRoute(unittest.TestCase):

    def setUp(self):
        self.calls = []
        self.original = app_module.set_mode
        app_module.set_mode = lambda client, mode: (
            self.calls.append((client, mode)) or machine(name='pc', mode=mode)
        )
        self.addCleanup(setattr, app_module, 'set_mode', self.original)

    def post(self, snapshot=None, clients=None, **data):
        snapshot = snapshot if snapshot is not None else snapshot_of(machine())
        clients = clients if clients is not None else [{'host': 'pc.local', 'password': 'x'}]
        return client_for(snapshot, clients).post('/mode', data=data)

    def test_should_change_the_mode_of_the_machine_that_was_asked_for(self):
        response = self.post(machine='0', mode='never')

        self.assertEqual(302, response.status_code)
        self.assertEqual([({'host': 'pc.local', 'password': 'x'}, 'never')], self.calls)

    def test_should_show_the_new_state_without_waiting_for_the_next_poll(self):
        # Otherwise the page comes back looking exactly as before and the button reads as broken.
        snapshot = snapshot_of(machine(mode='auto'))
        self.post(snapshot=snapshot, machine='0', mode='never')

        self.assertEqual('never', snapshot.read()['machines'][0]['state']['mode'])

    def test_should_redirect_back_to_the_page_and_not_alongside_it(self):
        # A nested route such as /mode/0 would make this same './' resolve to /mode/, which is why
        # the machine travels in the form instead of the path. The root-relative guard elsewhere
        # cannot catch this: './' does not start with a slash either.
        response = self.post(machine='0', mode='never')

        self.assertEqual('/', urljoin('/mode', response.headers['Location']))

    def test_should_point_at_the_machine_that_could_not_be_changed(self):
        app_module.set_mode = lambda client, mode: machine(
            name='pc', error='hung up', error_kind='rejected')
        response = self.post(machine='0', mode='never')

        self.assertEqual('/?failed=0', urljoin('/mode', response.headers['Location']))

    def test_should_say_so_on_the_page_when_a_change_did_not_go_through(self):
        page = client_for(snapshot_of(machine(error='hung up', error_kind='rejected'))) \
            .get('/?failed=0').get_data(as_text=True)

        self.assertIn('did not go through', page)

    def test_should_refuse_anything_the_browser_made_up(self):
        for data in ({'machine': '7', 'mode': 'never'},      # no such machine
                     {'machine': 'all', 'mode': 'never'},    # not a number
                     {'machine': '0', 'mode': 'turbo'},      # not a mode
                     {}):                                    # nothing at all
            with self.subTest(data=data):
                response = self.post(**data)

                self.assertEqual(302, response.status_code)
                self.assertEqual([], self.calls, 'a made-up request reached a BOINC client')


class TestRefresher(unittest.TestCase):

    def test_should_poll_again_promptly_when_a_refresh_is_requested(self):
        # Without this the button would do nothing visible until the next scheduled poll, which is a
        # minute away.
        polls = threading.Semaphore(0)
        original = app_module.read_all
        app_module.read_all = lambda clients: polls.release() or []
        stop = threading.Event()
        refresher = Refresher(Snapshot(), [], stop)
        try:
            refresher.start()
            self.assertTrue(polls.acquire(timeout=10), 'the refresher never polled on startup')

            refresher.request_refresh()

            self.assertTrue(polls.acquire(timeout=10), 'requesting a refresh did not wake the poller')
        finally:
            stop.set()
            refresher.request_refresh()
            refresher.join(timeout=10)
            app_module.read_all = original


if __name__ == '__main__':
    unittest.main()
