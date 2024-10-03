import os
import tempfile
import unittest

from remote_hosts import prepare_remote_hosts


class RemoteHostsTestCase(unittest.TestCase):

    def test_should_create_remote_hosts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_remote_hosts(tmp_dir, ['192.168.1.146'])
            self.assertTrue(os.path.exists(f'{tmp_dir}/remote_hosts.cfg'))
            with open(f'{tmp_dir}/remote_hosts.cfg') as f:
                self.assertEqual('192.168.1.146\n', f.read())

    def test_should_create_empty_remote_hosts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_remote_hosts(tmp_dir, None)
            self.assertTrue(os.path.exists(f'{tmp_dir}/remote_hosts.cfg'))

    def test_should_create_multiple_remote_hosts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_remote_hosts(tmp_dir, ['192.168.1.145', 'github.com'])
            self.assertTrue(os.path.exists(f'{tmp_dir}/remote_hosts.cfg'))
            with open(f'{tmp_dir}/remote_hosts.cfg') as f:
                self.assertEqual('192.168.1.145\ngithub.com\n', f.read())

    def test_should_overwrite_remote_hosts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_remote_hosts(tmp_dir, ['192.168.1.146'])
            prepare_remote_hosts(tmp_dir, ['github.com'])
            self.assertTrue(os.path.exists(f'{tmp_dir}/remote_hosts.cfg'))
            with open(f'{tmp_dir}/remote_hosts.cfg') as f:
                self.assertEqual('github.com\n', f.read())

if __name__ == '__main__':
    unittest.main()