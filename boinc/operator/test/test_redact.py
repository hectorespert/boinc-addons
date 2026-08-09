import unittest

from redact import redact_secrets


class RedactTestCase(unittest.TestCase):

    def test_should_redact_passwords(self):
        options = {
            'gui_rpc_password': 'a gui rpc password',
            'account_manager_password': 'an account manager password',
        }

        self.assertEqual(redact_secrets(options), {
            'gui_rpc_password': '***',
            'account_manager_password': '***',
        })

    def test_should_keep_non_secret_options(self):
        options = {
            'gui_rpc_password': 'a gui rpc password',
            'account_manager_url': 'https://scienceunited.org',
            'account_manager_username': 'a username',
            'remote_hosts': ['a-host'],
            'max_ncpus': 50,
        }

        self.assertEqual(redact_secrets(options), {
            'gui_rpc_password': '***',
            'account_manager_url': 'https://scienceunited.org',
            'account_manager_username': 'a username',
            'remote_hosts': ['a-host'],
            'max_ncpus': 50,
        })

    def test_should_not_redact_unset_passwords(self):
        options = {'gui_rpc_password': None, 'account_manager_password': None}

        self.assertEqual(redact_secrets(options), {'gui_rpc_password': None, 'account_manager_password': None})

    def test_should_not_modify_the_original_options(self):
        options = {'gui_rpc_password': 'a gui rpc password'}

        redact_secrets(options)

        self.assertEqual(options, {'gui_rpc_password': 'a gui rpc password'})


if __name__ == '__main__':
    unittest.main()
