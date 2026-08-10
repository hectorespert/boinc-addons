import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import Snapshot, create_app  # noqa: E402

# An URL that is fine to emit absolutely: it leaves the panel on purpose, or does not navigate.
EXTERNAL_PREFIXES = ('http://', 'https://', 'mailto:', '#')

URL_ATTRIBUTES = ('href', 'src', 'action', 'formaction')


class UrlCollector(HTMLParser):
    """Collects every URL the page would make the browser resolve."""

    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in URL_ATTRIBUTES and value is not None:
                self.urls.append((tag, name, value))


class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = create_app(Snapshot())
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_should_render_the_page_when_no_client_is_connected(self):
        response = self.client.get('/')

        self.assertEqual(200, response.status_code)
        self.assertIn('No BOINC client is connected', response.get_data(as_text=True))

    # Home Assistant ingress serves this app under /api/hassio_ingress/<token>/ and strips that
    # prefix without telling the app what it was, so a root-relative URL escapes the panel and lands
    # on the Home Assistant root instead. The three tests below are the guard for that, and they are
    # the reason this add-on renders on the server rather than shipping a bundled front end.
    def test_should_never_emit_a_root_relative_url(self):
        collector = UrlCollector()
        collector.feed(self.client.get('/').get_data(as_text=True))

        self.assertTrue(collector.urls, 'the page emitted no URLs at all, so this proves nothing')
        for tag, attribute, url in collector.urls:
            with self.subTest(tag=tag, attribute=attribute, url=url):
                if url.startswith(EXTERNAL_PREFIXES):
                    continue
                self.assertFalse(
                    url.startswith('/'),
                    f'<{tag} {attribute}="{url}"> is root-relative and would escape the ingress path',
                )

    def test_should_redirect_relatively_after_refreshing(self):
        response = self.client.post('/refresh')

        self.assertEqual(302, response.status_code)
        location = response.headers['Location']
        self.assertFalse(
            location.startswith('/'),
            f'Location: {location} is root-relative and would send the browser out of the panel',
        )

    def test_should_record_the_refresh_in_the_snapshot(self):
        snapshot = Snapshot()
        client = create_app(snapshot).test_client()
        self.assertIsNone(snapshot.read()[1])

        client.post('/refresh')

        self.assertIsNotNone(snapshot.read()[1])


if __name__ == '__main__':
    unittest.main()
