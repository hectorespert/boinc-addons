import os
import tempfile
import unittest

from gui_rpc_auth import prepare_gui_rpc_auth

class GuiRpcAuthTestCase(unittest.TestCase):

    def test_should_not_create_gui_rpc_auth(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_gui_rpc_auth(tmp_dir, None)
            self.assertFalse(os.path.exists(f'{tmp_dir}/gui_rpc_auth.cfg'))

    def test_should_create_gui_rpc_auth(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_gui_rpc_auth(tmp_dir, '123456')
            self.assertTrue(os.path.exists(f'{tmp_dir}/gui_rpc_auth.cfg'))
            with open(f'{tmp_dir}/gui_rpc_auth.cfg') as f:
                self.assertEqual('123456', f.read())

    def test_should_remove_gui_rpc_auth(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_gui_rpc_auth(tmp_dir, '123456')
            self.assertTrue(os.path.exists(f'{tmp_dir}/gui_rpc_auth.cfg'))

            prepare_gui_rpc_auth(tmp_dir, '654321')
            self.assertTrue(os.path.exists(f'{tmp_dir}/gui_rpc_auth.cfg'))
            with open(f'{tmp_dir}/gui_rpc_auth.cfg') as f:
                self.assertEqual('654321', f.read())

if __name__ == '__main__':
    unittest.main()
