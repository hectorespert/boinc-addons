import os
import stat
import tempfile
import unittest

from gui_rpc_auth import prepare_gui_rpc_auth

class GuiRpcAuthTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        self.data_dir = self.tmp_dir.name
        self.gui_rpc_auth = f'{self.data_dir}/gui_rpc_auth.cfg'

    def read_gui_rpc_auth(self) -> str:
        with open(self.gui_rpc_auth) as f:
            return f.read()

    def test_should_leave_the_gui_rpc_auth_to_boinc_when_no_password_is_configured(self):
        prepare_gui_rpc_auth(self.data_dir, None)

        # BOINC generates a random password when the file is missing, so not writing one is what
        # keeps that default in place.
        self.assertFalse(os.path.exists(self.gui_rpc_auth))

    def test_should_remove_an_empty_gui_rpc_auth_when_no_password_is_configured(self):
        prepare_gui_rpc_auth(self.data_dir, '')
        self.assertTrue(os.path.exists(self.gui_rpc_auth))

        prepare_gui_rpc_auth(self.data_dir, None)

        # An empty file is the empty password, not a missing one: leaving it would keep the client
        # reachable with no credential.
        self.assertFalse(os.path.exists(self.gui_rpc_auth))

    def test_should_keep_a_generated_gui_rpc_auth_when_no_password_is_configured(self):
        with open(self.gui_rpc_auth, 'w') as f:
            f.write('b786c9882cdd189d4649a9a8430acb9d\n')

        prepare_gui_rpc_auth(self.data_dir, None)

        # The BOINC client wrote this one, and it has to survive restarts or the password would
        # rotate under anything that stored it.
        self.assertEqual(self.read_gui_rpc_auth(), 'b786c9882cdd189d4649a9a8430acb9d\n')

    def test_should_restrict_a_kept_gui_rpc_auth_written_by_an_older_version(self):
        with open(self.gui_rpc_auth, 'w') as f:
            f.write('123456\n')
        os.chmod(self.gui_rpc_auth, 0o644)

        prepare_gui_rpc_auth(self.data_dir, None)

        # Older versions wrote the file world-readable. Keeping the password is right, keeping the
        # permissions is not.
        self.assertEqual(self.read_gui_rpc_auth(), '123456\n')
        self.assertEqual(stat.S_IMODE(os.stat(self.gui_rpc_auth).st_mode), 0o600)

    def test_should_create_an_empty_gui_rpc_auth_when_the_password_is_explicitly_empty(self):
        prepare_gui_rpc_auth(self.data_dir, '')

        self.assertTrue(os.path.exists(self.gui_rpc_auth))
        self.assertEqual(self.read_gui_rpc_auth(), '')

    def test_should_create_gui_rpc_auth(self):
        prepare_gui_rpc_auth(self.data_dir, '123456')

        self.assertEqual(self.read_gui_rpc_auth(), '123456\n')

    def test_should_create_gui_rpc_auth_readable_only_by_its_owner(self):
        prepare_gui_rpc_auth(self.data_dir, '123456')

        self.assertEqual(stat.S_IMODE(os.stat(self.gui_rpc_auth).st_mode), 0o600)

    def test_should_replace_an_existing_gui_rpc_auth(self):
        prepare_gui_rpc_auth(self.data_dir, '123456')

        prepare_gui_rpc_auth(self.data_dir, '654321')

        self.assertEqual(self.read_gui_rpc_auth(), '654321\n')

    def test_should_replace_a_generated_gui_rpc_auth_with_the_configured_password(self):
        with open(self.gui_rpc_auth, 'w') as f:
            f.write('b786c9882cdd189d4649a9a8430acb9d\n')

        prepare_gui_rpc_auth(self.data_dir, '123456')

        self.assertEqual(self.read_gui_rpc_auth(), '123456\n')

if __name__ == '__main__':
    unittest.main()
