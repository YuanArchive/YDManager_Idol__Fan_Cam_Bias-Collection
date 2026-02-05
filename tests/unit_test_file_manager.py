
import unittest
import os
import shutil
import sys
import tempfile
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.managers.file_manager import FileManager
from src.core import consts

class TestFileManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.file_manager = FileManager()
        
        # Override constants for testing
        self.file_manager.tags_file_path = os.path.join(self.test_dir, "test_tags.json")
        self.file_manager.highlights_file_path = os.path.join(self.test_dir, "test_highlights.json")
        
    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_path_normalization(self):
        """Test if paths are correctly normalized."""
        if sys.platform == 'win32':
            # Case insensitivity test
            path1 = r"C:\Users\Video.mp4"
            path2 = r"c:\users\video.mp4"
            self.assertEqual(
                self.file_manager._get_norm_key(path1), 
                self.file_manager._get_norm_key(path2)
            )
            
            # Slash direction test
            path3 = "C:/Users/Video.mp4"
            self.assertEqual(
                self.file_manager._get_norm_key(path1), 
                self.file_manager._get_norm_key(path3)
            )

    def test_json_atomic_write(self):
        """Test if JSON saving is atomic and data persists."""
        data = {"key": "value", "number": 123}
        target_file = os.path.join(self.test_dir, "test_atomic.json")
        
        # Perform save
        success = self.file_manager.save_json(target_file, data)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_file))
        
        # Verify content
        with open(target_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            self.assertEqual(loaded_data, data)

if __name__ == '__main__':
    unittest.main()
