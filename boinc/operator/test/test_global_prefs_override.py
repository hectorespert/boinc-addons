import json
import os
import tempfile
import unittest

from global_prefs_override import MANAGED_STATE_FILE, link_global_prefs_override


class GlobalPreferencesOverrideTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        self.data_dir = f'{self.tmp_dir.name}/data'
        os.makedirs(self.data_dir)
        self.config_dir = f'{self.tmp_dir.name}/config'
        os.makedirs(self.config_dir)

        self.global_prefs_override = f'{self.data_dir}/global_prefs_override.xml'
        self.configured_global_prefs_override = f'{self.config_dir}/global_prefs_override.xml'

    def write_preferences(self, path: str, content: str) -> None:
        with open(path, 'w') as f:
            f.write(content)

    def read_preferences(self, path: str) -> str:
        with open(path, 'r') as f:
            return f.read()

    def write_managed_state(self, state: dict) -> None:
        with open(f'{self.data_dir}/{MANAGED_STATE_FILE}', 'w') as f:
            json.dump(state, f)

    def read_managed_state(self) -> dict:
        with open(f'{self.data_dir}/{MANAGED_STATE_FILE}', 'r') as f:
            return json.load(f)

    def test_should_create_global_prefs_override(self):
        link_global_prefs_override(self.data_dir, self.config_dir, {})

        self.assertTrue(os.path.exists(self.global_prefs_override))
        self.assertFalse(os.path.islink(self.global_prefs_override))

    def test_should_link_global_prefs_override(self):
        self.write_preferences(self.configured_global_prefs_override, '<global_preferences></global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {})

        self.assertTrue(os.path.exists(self.global_prefs_override))
        self.assertTrue(os.path.islink(self.global_prefs_override))

    def test_should_not_overwrite_a_linked_global_prefs_override(self):
        configured_preferences = '<global_preferences>\n  <disk_max_used_gb>100</disk_max_used_gb>\n</global_preferences>'
        self.write_preferences(self.configured_global_prefs_override, configured_preferences)

        link_global_prefs_override(self.data_dir, self.config_dir, {
            'start_hour': '00:35',
            'end_hour': '08:59'
        })

        self.assertEqual(self.read_preferences(self.configured_global_prefs_override), configured_preferences)
        self.assertEqual(self.read_preferences(self.global_prefs_override), configured_preferences)

    def test_should_manage_no_preference_while_linked(self):
        self.write_managed_state({'start_hour': 0.35})
        self.write_preferences(self.configured_global_prefs_override, '<global_preferences></global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {'start_hour': '00:35'})

        self.assertEqual(self.read_managed_state(), {})

    def test_should_create_global_prefs_override_with_configuration(self):
        link_global_prefs_override(self.data_dir, self.config_dir, {
            'start_hour': '00:35',
            'end_hour': '08:59'
        })

        self.assertFalse(os.path.islink(self.global_prefs_override))
        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <start_hour>0.35</start_hour>\n  <end_hour>8.59</end_hour>\n</global_preferences>')
        self.assertEqual(self.read_managed_state(), {'start_hour': 0.35, 'end_hour': 8.59})

    def test_should_create_global_prefs_override_with_cpu_configurations(self):
        link_global_prefs_override(self.data_dir, self.config_dir, {
            'max_ncpus': 50,
            'cpu_usage_limit': 75.0
        })

        self.assertFalse(os.path.islink(self.global_prefs_override))
        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <niu_max_ncpus_pct>50</niu_max_ncpus_pct>\n  <niu_cpu_usage_limit>75.0</niu_cpu_usage_limit>\n</global_preferences>')

    def test_should_keep_preferences_set_outside_the_add_on(self):
        self.write_preferences(self.global_prefs_override,
                               '<global_preferences>\n  <disk_max_used_gb>100</disk_max_used_gb>\n</global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {'start_hour': '00:35'})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <disk_max_used_gb>100</disk_max_used_gb>\n  <start_hour>0.35</start_hour>\n</global_preferences>')

    def test_should_update_a_managed_preference_in_place(self):
        self.write_preferences(self.global_prefs_override,
                               '<global_preferences>\n  <start_hour>22.0</start_hour>\n  <disk_max_used_gb>100</disk_max_used_gb>\n</global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {'start_hour': '00:35'})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <start_hour>0.35</start_hour>\n  <disk_max_used_gb>100</disk_max_used_gb>\n</global_preferences>')

    def test_should_remove_a_managed_preference_it_wrote_when_its_option_is_gone(self):
        self.write_managed_state({'start_hour': 22.0})
        self.write_preferences(self.global_prefs_override,
                               '<global_preferences>\n  <start_hour>22.0</start_hour>\n  <disk_max_used_gb>100</disk_max_used_gb>\n</global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <disk_max_used_gb>100</disk_max_used_gb>\n</global_preferences>')
        self.assertEqual(self.read_managed_state(), {})

    def test_should_keep_a_managed_preference_it_never_wrote(self):
        self.write_preferences(self.global_prefs_override,
                               '<global_preferences>\n  <start_hour>22.0</start_hour>\n</global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <start_hour>22.0</start_hour>\n</global_preferences>')

    def test_should_not_recreate_the_config_file_through_a_broken_symlink(self):
        os.symlink(self.configured_global_prefs_override, self.global_prefs_override)

        link_global_prefs_override(self.data_dir, self.config_dir, {'start_hour': '00:35'})

        self.assertFalse(os.path.exists(self.configured_global_prefs_override))
        self.assertFalse(os.path.islink(self.global_prefs_override))
        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <start_hour>0.35</start_hour>\n</global_preferences>')

    def test_should_regenerate_an_unparseable_global_prefs_override(self):
        self.write_preferences(self.global_prefs_override, '<global_preferences>\n  <start_hour>0.35')

        link_global_prefs_override(self.data_dir, self.config_dir, {'end_hour': '08:59'})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <end_hour>8.59</end_hour>\n</global_preferences>')

    def test_should_regenerate_a_global_prefs_override_with_an_unexpected_root(self):
        self.write_preferences(self.global_prefs_override, '<cc_config>\n  <log_flags></log_flags>\n</cc_config>')

        link_global_prefs_override(self.data_dir, self.config_dir, {'end_hour': '08:59'})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <end_hour>8.59</end_hour>\n</global_preferences>')

    def test_should_ignore_an_unreadable_managed_state(self):
        self.write_preferences(f'{self.data_dir}/{MANAGED_STATE_FILE}', 'not json')
        self.write_preferences(self.global_prefs_override,
                               '<global_preferences>\n  <start_hour>22.0</start_hour>\n</global_preferences>')

        link_global_prefs_override(self.data_dir, self.config_dir, {})

        self.assertEqual(self.read_preferences(self.global_prefs_override),
                         '<global_preferences>\n  <start_hour>22.0</start_hour>\n</global_preferences>')

if __name__ == '__main__':
    unittest.main()
