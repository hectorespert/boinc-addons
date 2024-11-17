import os
import tempfile
import unittest

from global_prefs_override import link_global_prefs_override


class GlobalPreferencesOverrideTestCase(unittest.TestCase):

    def test_should_create_global_prefs_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = f'{tmp_dir}/data'
            os.makedirs(data_dir)
            config_dir = f'{tmp_dir}/config'
            os.makedirs(config_dir)
            link_global_prefs_override(data_dir, config_dir, {})

            self.assertTrue(os.path.exists(f'{tmp_dir}/data/global_prefs_override.xml'))
            self.assertFalse(os.path.islink(f'{tmp_dir}/data/global_prefs_override.xml'))

    def test_should_link_global_prefs_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = f'{tmp_dir}/data'
            os.makedirs(data_dir)
            config_dir = f'{tmp_dir}/config'
            os.makedirs(config_dir)

            with open(f'{config_dir}/global_prefs_override.xml', 'w') as f:
                f.write('<global_preferences></global_preferences>')

            link_global_prefs_override(data_dir, config_dir, {})

            self.assertTrue(os.path.exists(f'{tmp_dir}/data/global_prefs_override.xml'))
            self.assertTrue(os.path.islink(f'{tmp_dir}/data/global_prefs_override.xml'))

    def test_should_create_global_prefs_override_with_configuration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = f'{tmp_dir}/data'
            os.makedirs(data_dir)
            config_dir = f'{tmp_dir}/config'
            os.makedirs(config_dir)
            link_global_prefs_override(data_dir, config_dir, {
                'start_hour': '00:35',
                'end_hour': '08:59'
            })

            self.assertTrue(os.path.exists(f'{tmp_dir}/data/global_prefs_override.xml'))
            self.assertFalse(os.path.islink(f'{tmp_dir}/data/global_prefs_override.xml'))

            with open(f'{tmp_dir}/data/global_prefs_override.xml', 'r') as f:
                self.assertEqual(f.read(), '<global_preferences>\n  <end_hour>8.59</end_hour>\n  <start_hour>0.35</start_hour>\n</global_preferences>')

    def test_should_create_global_prefs_override_with_cpu_configurations(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = f'{tmp_dir}/data'
            os.makedirs(data_dir)
            config_dir = f'{tmp_dir}/config'
            os.makedirs(config_dir)
            link_global_prefs_override(data_dir, config_dir, {
                'max_ncpus': 50,
                'cpu_usage_limit': 75
            })

            self.assertTrue(os.path.exists(f'{tmp_dir}/data/global_prefs_override.xml'))
            self.assertFalse(os.path.islink(f'{tmp_dir}/data/global_prefs_override.xml'))

            with open(f'{tmp_dir}/data/global_prefs_override.xml', 'r') as f:
                self.assertEqual(f.read(), '<global_preferences>\n  <cpu_usage_limit>75.0</cpu_usage_limit>\n  <max_ncpus>50.0</max_ncpus>\n</global_preferences>')

if __name__ == '__main__':
    unittest.main()