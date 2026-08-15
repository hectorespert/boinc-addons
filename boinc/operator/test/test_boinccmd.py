import subprocess
import unittest
from unittest.mock import patch

from boinccmd import configure_boinc_projects

ACCOUNT_MANAGER_URL = 'https://scienceunited.org'
ACCOUNT_MANAGER_USERNAME = 'a username'
ACCOUNT_MANAGER_PASSWORD = 'a password'


def completed(stdout: str = '', returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr='')


def account_manager_info(url: str | None) -> subprocess.CompletedProcess:
    if url is None:
        return completed('Account manager info:\n   Name: \n   URL: \n')
    return completed(f'Account manager info:\n   Name: Science United\n   URL: {url}\n')


def executed_commands(run) -> list:
    return [call.args[0][1:] for call in run.call_args_list]


class ConfigureBoincProjectsTestCase(unittest.TestCase):

    @patch('boinccmd.subprocess.run')
    def test_should_keep_an_account_manager_attached_outside_the_options(self, run):
        run.return_value = account_manager_info(ACCOUNT_MANAGER_URL)

        self.assertTrue(configure_boinc_projects('a data folder', None, None, None))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info']])

    @patch('boinccmd.subprocess.run')
    def test_should_do_nothing_when_nothing_is_configured_nor_attached(self, run):
        run.return_value = account_manager_info(None)

        self.assertTrue(configure_boinc_projects('a data folder', None, None, None))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info']])

    @patch('boinccmd.subprocess.run')
    def test_should_attach_the_configured_account_manager(self, run):
        run.side_effect = [account_manager_info(None), completed()]

        self.assertTrue(configure_boinc_projects('a data folder', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD))

        self.assertEqual(executed_commands(run), [
            ['--acct_mgr', 'info'],
            ['--acct_mgr', 'attach', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD],
        ])

    @patch('boinccmd.subprocess.run')
    def test_should_synchronize_an_already_attached_account_manager(self, run):
        run.side_effect = [account_manager_info(ACCOUNT_MANAGER_URL), completed()]

        self.assertTrue(configure_boinc_projects('a data folder', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info'], ['--acct_mgr', 'sync']])

    @patch('boinccmd.subprocess.run')
    def test_should_synchronize_when_only_the_trailing_slash_differs(self, run):
        # boinccmd --acct_mgr info reports the URL already canonicalized by the client (BOINC
        # always appends a trailing slash), so a configured URL without one is still the same
        # account manager.
        run.side_effect = [account_manager_info(f'{ACCOUNT_MANAGER_URL}/'), completed()]

        self.assertTrue(configure_boinc_projects('a data folder', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info'], ['--acct_mgr', 'sync']])

    @patch('boinccmd.subprocess.run')
    def test_should_synchronize_when_only_the_scheme_is_missing_from_the_configured_url(self, run):
        # The client stores a scheme-less URL as http://, so leaving the scheme off in the option
        # is still the same account manager, not a different one to detach and re-attach.
        run.side_effect = [account_manager_info('http://scienceunited.org/'), completed()]

        self.assertTrue(configure_boinc_projects('a data folder', 'scienceunited.org', ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info'], ['--acct_mgr', 'sync']])

    @patch('boinccmd.subprocess.run')
    def test_should_replace_an_account_manager_on_the_same_host_with_a_different_path(self, run):
        # Only comparing the host (the old netloc-only comparison) would have called this the same
        # account manager and synced against the wrong one.
        run.side_effect = [account_manager_info('https://host/a'), completed(), completed()]

        self.assertTrue(configure_boinc_projects('a data folder', 'https://host/b', ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD))

        self.assertEqual(executed_commands(run), [
            ['--acct_mgr', 'info'],
            ['--acct_mgr', 'detach'],
            ['--acct_mgr', 'attach', 'https://host/b', ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD],
        ])

    @patch('boinccmd.subprocess.run')
    def test_should_replace_a_different_account_manager(self, run):
        run.side_effect = [account_manager_info('https://another.account.manager'), completed(), completed()]

        self.assertTrue(configure_boinc_projects('a data folder', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD))

        self.assertEqual(executed_commands(run), [
            ['--acct_mgr', 'info'],
            ['--acct_mgr', 'detach'],
            ['--acct_mgr', 'attach', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, ACCOUNT_MANAGER_PASSWORD],
        ])

    @patch('boinccmd.subprocess.run')
    def test_should_fail_when_only_the_account_manager_url_is_configured(self, run):
        run.return_value = account_manager_info(None)

        # Half an account manager cannot be attached, and a warning would let the app look healthy
        # while contributing to nothing.
        self.assertFalse(configure_boinc_projects('a data folder', ACCOUNT_MANAGER_URL, None, None))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info']])

    @patch('boinccmd.subprocess.run')
    def test_should_fail_when_the_account_manager_password_is_missing(self, run):
        run.return_value = account_manager_info(None)

        self.assertFalse(configure_boinc_projects('a data folder', ACCOUNT_MANAGER_URL, ACCOUNT_MANAGER_USERNAME, None))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info']])

    @patch('boinccmd.subprocess.run')
    def test_should_fail_an_incomplete_account_manager_without_detaching_the_attached_one(self, run):
        run.return_value = account_manager_info(ACCOUNT_MANAGER_URL)

        self.assertFalse(configure_boinc_projects('a data folder', None, ACCOUNT_MANAGER_USERNAME, None))

        self.assertEqual(executed_commands(run), [['--acct_mgr', 'info']])

    @patch('boinccmd.subprocess.run')
    def test_should_fail_when_the_account_manager_information_is_not_available(self, run):
        run.return_value = completed(returncode=1)

        self.assertFalse(configure_boinc_projects('a data folder', None, None, None))


if __name__ == '__main__':
    unittest.main()
