import os
import tempfile
import unittest

from cc_config import prepare_cc_config


class CCConfigTestCase(unittest.TestCase):
    def test_should_create_cc_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_cc_config(tmp_dir)
            self.assertTrue(os.path.exists(f'{tmp_dir}/cc_config.xml'))
            with open(f'{tmp_dir}/cc_config.xml', 'r') as f:
                self.assertEqual(f.read(),
                                 '<cc_config>\n  <log_flags>\n    <file_xfer>1</file_xfer>\n    <sched_ops>1</sched_ops>\n    <task>1</task>\n  </log_flags>\n</cc_config>')

if __name__ == '__main__':
    unittest.main()
