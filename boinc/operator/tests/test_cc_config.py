import os
import tempfile
import unittest

from cc_config import prepare_cc_config


class CCConfigTestCase(unittest.TestCase):
    def test_should_create_cc_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_cc_config(tmp_dir)
            self.assertTrue(os.path.exists(f'{tmp_dir}/cc_config.xml'))


if __name__ == '__main__':
    unittest.main()
