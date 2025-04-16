import unittest
from unittest.mock import patch, MagicMock
from src.interface import display_playlists, display_personalized_mixes, select_playlists, select_mixes, update_tracks

class TestInterface(unittest.TestCase):

    @patch('src.interface.console.print')
    def test_display_playlists(self, mock_print):
        playlists = {'items': [{'name': 'Playlist 1'}, {'name': 'Playlist 2'}]}
        display_playlists(playlists)
        self.assertTrue(mock_print.called)

    @patch('src.interface.console.print')
    def test_display_personalized_mixes(self, mock_print):
        mixes = {'items': [{'name': 'Mix 1'}, {'name': 'Mix 2'}]}
        display_personalized_mixes(mixes)
        self.assertTrue(mock_print.called)

    @patch('src.interface.Prompt.ask', return_value='0,1')
    def test_select_playlists(self, mock_ask):
        playlists = {'items': [{'name': 'Playlist 1'}, {'name': 'Playlist 2'}]}
        selected_playlists = select_playlists(playlists)
        self.assertEqual(len(selected_playlists), 2)

    @patch('src.interface.Prompt.ask', return_value='0,1')
    def test_select_mixes(self, mock_ask):
        mixes = {'items': [{'name': 'Mix 1'}, {'name': 'Mix 2'}]}
        selected_mixes = select_mixes(mixes)
        self.assertEqual(len(selected_mixes), 2)

    @patch('src.interface.fetch_and_organize_playlists')
    @patch('src.interface.organize_tracks')
    @patch('src.interface.Progress')
    def test_update_tracks(self, mock_progress, mock_organize_tracks, mock_fetch_and_organize_playlists):
        mock_progress.return_value.__enter__.return_value.add_task.return_value = 1
        update_tracks()
        self.assertTrue(mock_fetch_and_organize_playlists.called)
        self.assertTrue(mock_organize_tracks.called)

if __name__ == '__main__':
    unittest.main()
