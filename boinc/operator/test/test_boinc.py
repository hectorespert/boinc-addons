import unittest

from boinc import build_boinc_command


class TestBoincCommand(unittest.TestCase):

    def test_builds_command_with_remote_gui_rpc(self):
        result = build_boinc_command("/data", True)
        self.assertEqual(result, ["boinc", "--dir", "/data", "--allow_remote_gui_rpc"])

    def test_builds_command_without_remote_gui_rpc(self):
        result = build_boinc_command("/data", False)
        self.assertEqual(result, ["boinc", "--dir", "/data"])

if __name__ == '__main__':
    unittest.main()