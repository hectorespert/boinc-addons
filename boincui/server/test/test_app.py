import sys
import threading
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402
from app import Refresher, Snapshot, create_app  # noqa: E402
from boinc import AuthenticationFailed, BoincError, CannotConnect, NotConfigured  # noqa: E402

# An URL that is fine to emit absolutely: it leaves the panel on purpose, or does not navigate.
EXTERNAL_PREFIXES = ('http://', 'https://', 'mailto:', '#')

URL_ATTRIBUTES = ('href', 'src', 'action', 'formaction')

CONNECTED_STATE = {
    'cc_status': {'task_mode': 2},
    'projects': [{'master_url': 'https://example.org/', 'project_name': 'Example'}],
    'results': [{
        'name': 'task_one',
        'project_url': 'https://example.org/',
        'active_task': {'active_task_state': 1, 'fraction_done': 0.25},
    }],
}


class UrlCollector(HTMLParser):
    """Collects every URL the page would make the browser resolve."""

    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in URL_ATTRIBUTES and value is not None:
                self.urls.append((tag, name, value))


def client_for(snapshot):
    app = create_app(snapshot)
    app.config.update(TESTING=True)
    return app.test_client()


def snapshot_failing_with(error):
    snapshot = Snapshot()
    snapshot.fail(error)
    return snapshot


def snapshot_connected():
    snapshot = Snapshot()
    snapshot.store(CONNECTED_STATE)
    return snapshot


class TestStates(unittest.TestCase):
    """Every state the page can be in, rendered without touching the network."""

    def page_for(self, snapshot):
        response = client_for(snapshot).get('/')
        self.assertEqual(200, response.status_code)
        return response.get_data(as_text=True)

    def test_should_say_it_is_still_checking_before_the_first_refresh(self):
        self.assertIn('Checking the BOINC client', self.page_for(Snapshot()))

    def test_should_explain_what_to_fill_in_when_not_configured(self):
        page = self.page_for(snapshot_failing_with(NotConfigured('nothing set')))

        self.assertIn('No BOINC client is configured', page)
        self.assertIn('Configuration tab', page)

    def test_should_show_the_address_it_tried_when_it_cannot_connect(self):
        page = self.page_for(snapshot_failing_with(CannotConnect('Could not reach a BOINC client at boinc-host:31416')))

        self.assertIn('Cannot reach the BOINC client', page)
        self.assertIn('boinc-host:31416', page)

    def test_should_point_at_the_password_when_it_is_rejected(self):
        page = self.page_for(snapshot_failing_with(AuthenticationFailed('rejected')))

        self.assertIn('rejected the password', page)

    def test_should_still_render_on_an_unexpected_failure(self):
        page = self.page_for(snapshot_failing_with(BoincError('Unexpected reply')))

        self.assertIn('Something went wrong', page)
        self.assertIn('Unexpected reply', page)

    def test_should_list_tasks_and_projects_when_connected(self):
        page = self.page_for(snapshot_connected())

        self.assertIn('task_one', page)
        self.assertIn('25%', page)
        self.assertIn('Example', page)

    def test_should_keep_the_last_state_visible_when_a_refresh_fails(self):
        # A single failed poll should not blank a page that was working a minute ago.
        snapshot = snapshot_connected()
        snapshot.fail(CannotConnect('Could not reach a BOINC client at boinc-host:31416'))

        page = self.page_for(snapshot)

        self.assertIn('Cannot reach the BOINC client', page)
        self.assertIn('task_one', page)

    def test_should_say_there_are_no_tasks_rather_than_showing_nothing(self):
        snapshot = Snapshot()
        snapshot.store({'cc_status': {}, 'projects': [], 'results': []})

        page = self.page_for(snapshot)

        self.assertIn('No tasks', page)
        self.assertIn('not attached to any project', page)


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
            ('not configured', snapshot_failing_with(NotConfigured('nothing set'))),
            ('connected', snapshot_connected()),
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
        # Polling inline would hold the request for as long as the BOINC host takes to answer, which
        # is the very thing the background refresher exists to avoid.
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


class TestRefresher(unittest.TestCase):

    def test_should_poll_again_promptly_when_a_refresh_is_requested(self):
        # Without this the button would do nothing visible until the next scheduled poll, which is a
        # minute away.
        polls = threading.Semaphore(0)
        original = app_module.read_state
        app_module.read_state = lambda *args: polls.release() or {'cc_status': {}, 'projects': [], 'results': []}
        stop = threading.Event()
        refresher = Refresher(Snapshot(), {}, stop)
        try:
            refresher.start()
            self.assertTrue(polls.acquire(timeout=10), 'the refresher never polled on startup')

            refresher.request_refresh()

            self.assertTrue(polls.acquire(timeout=10), 'requesting a refresh did not wake the poller')
        finally:
            stop.set()
            refresher.request_refresh()
            refresher.join(timeout=10)
            app_module.read_state = original


if __name__ == '__main__':
    unittest.main()
