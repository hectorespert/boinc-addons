import os.path
import tempfile
import unittest

from folders import prepare_data_folders

class FoldersTestCase(unittest.TestCase):

    def test_should_create_folders(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prepare_data_folders(tmp_dir)
            self.assertTrue(os.path.isdir(tmp_dir))
            self.assertTrue(os.path.isdir(f'{tmp_dir}/slots'))
            self.assertTrue(os.path.isdir(f'{tmp_dir}/locale'))

if __name__ == '__main__':
    unittest.main()
