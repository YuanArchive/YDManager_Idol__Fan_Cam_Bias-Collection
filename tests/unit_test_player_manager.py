
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock PyQt6 modules BEFORE importing PlayerManager
sys.modules["PyQt6.QtMultimedia"] = MagicMock()
sys.modules["PyQt6.QtMultimediaWidgets"] = MagicMock()
sys.modules["PyQt6.QtCore"] = MagicMock()
sys.modules["PyQt6.QtWidgets"] = MagicMock()

from src.managers.player_manager import PlayerManager

class TestPlayerManager(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_video_view = MagicMock()
        self.mock_video_view.scene = MagicMock()
        self.mock_video_view.size.return_value = MagicMock() # QSizeF
        
        self.mock_chk_audio = MagicMock()
        
        self.manager = PlayerManager(self.mock_video_view, self.mock_chk_audio)

    def test_initialization(self):
        """Test if players are correctly initialized for all modes."""
        self.assertEqual(len(self.manager.pools['main']), 3)
        self.assertEqual(len(self.manager.pools['highlight']), 1)
        self.assertEqual(len(self.manager.pools['trash']), 3)

    def test_switch_mode_isolation(self):
        """Test if switching mode cleans up the previous mode's resources."""
        # Setup: 'main' mode is active
        self.manager.current_mode = 'main'
        
        # Mock players in 'main' pool
        for p_data in self.manager.pools['main']:
            p_data['player'] = MagicMock()
            p_data['item'] = MagicMock()
            p_data['audio'] = MagicMock()
            p_data['path'] = "/path/to/video.mp4"
            
        # Action: Switch to 'highlight'
        self.manager.switch_mode('highlight')
        
        # Verify: Old pool resources are released
        for p_data in self.manager.pools['main']:
            p_data['player'].stop.assert_called()
            p_data['player'].setSource.assert_called() # Should call with empty URL
            p_data['item'].setOpacity.assert_called_with(0.0)
            p_data['audio'].setMuted.assert_called_with(True)
            self.assertIsNone(p_data['path'])
            
        # Verify call arguments (checking setSource called with empty object)
        # Note: QUrl() in real code, here it's MagicMock due to sys.modules mock
        
    def test_bulkhead_active_index(self):
        """Test if active index is maintained per mode."""
        self.manager.active_indices['main'] = 2
        self.manager.active_indices['highlight'] = 0
        
        self.manager.switch_mode('highlight')
        self.assertEqual(self.manager.current_mode, 'highlight')
        # Active index for 'main' should persist
        self.assertEqual(self.manager.active_indices['main'], 2)

if __name__ == '__main__':
    unittest.main()
