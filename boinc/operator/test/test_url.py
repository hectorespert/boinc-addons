import unittest

from url import canonicalize_url


class CanonicalizeUrlTestCase(unittest.TestCase):

    def test_defaults_to_http_when_no_scheme_is_given(self):
        self.assertEqual(canonicalize_url('scienceunited.org'), 'http://scienceunited.org/')

    def test_keeps_https(self):
        self.assertEqual(canonicalize_url('https://scienceunited.org'), 'https://scienceunited.org/')

    def test_forces_a_non_https_scheme_to_http(self):
        self.assertEqual(canonicalize_url('ftp://scienceunited.org'), 'http://scienceunited.org/')

    def test_appends_a_trailing_slash(self):
        self.assertEqual(canonicalize_url('https://host/a'), 'https://host/a/')

    def test_does_not_duplicate_an_existing_trailing_slash(self):
        self.assertEqual(canonicalize_url('https://scienceunited.org/'), 'https://scienceunited.org/')

    def test_collapses_repeated_slashes(self):
        self.assertEqual(canonicalize_url('https://host//a///b'), 'https://host/a/b/')

    def test_lowercases_only_the_host(self):
        self.assertEqual(canonicalize_url('https://HOST/PATH'), 'https://host/PATH/')

    # The table from the plan this module implements: what gets configured, what BOINC's client
    # itself stores after applying canonicalize_master_url, and whether the two now compare equal.
    def test_configured_url_matches_the_client_stored_form_with_scheme(self):
        self.assertEqual(
            canonicalize_url('https://scienceunited.org'),
            canonicalize_url('https://scienceunited.org/'),
        )

    def test_configured_url_without_a_scheme_matches_the_client_stored_form(self):
        self.assertEqual(
            canonicalize_url('scienceunited.org'),
            canonicalize_url('http://scienceunited.org/'),
        )

    def test_same_host_different_path_are_not_equal(self):
        self.assertNotEqual(canonicalize_url('https://host/a'), canonicalize_url('https://host/b'))

    def test_http_and_https_are_deliberately_not_equal(self):
        # Unlike the netloc-only comparison this replaces, correcting the scheme in the option is
        # now treated as configuring a different account manager, and re-attaches to it.
        self.assertNotEqual(canonicalize_url('http://x'), canonicalize_url('https://x'))


if __name__ == '__main__':
    unittest.main()
