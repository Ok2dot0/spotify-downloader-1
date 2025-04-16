import unittest
from unittest.mock import patch, MagicMock
from src.playlist_manager import fetch_and_organize_playlists, organize_tracks, is_track_downloaded

class TestPlaylistManager(unittest.TestCase):

    @patch('src.playlist_manager.get_user_playlists')
    @patch('src.playlist_manager.get_user_personalized_mixes')
    @patch('src.playlist_manager.download_track')
    @patch('src.playlist_manager.get_download_location')
    def test_fetch_and_organize_playlists(self, mock_get_download_location, mock_download_track, mock_get_user_personalized_mixes, mock_get_user_playlists):
        mock_get_download_location.return_value = 'test_data'
        mock_get_user_playlists.return_value = {
            'items': [
                {
                    'name': 'Test Playlist',
                    'tracks': {
                        'items': [
                            {
                                'track': {
                                    'name': 'Test Track',
                                    'id': 'test_track_id'
                                }
                            }
                        ]
                    }
                }
            ]
        }
        mock_get_user_personalized_mixes.return_value = {
            'items': [
                {
                    'name': 'Test Mix',
                    'tracks': {
                        'items': [
                            {
                                'track': {
                                    'name': 'Test Mix Track',
                                    'id': 'test_mix_track_id'
                                }
                            }
                        ]
                    }
                }
            ]
        }

        fetch_and_organize_playlists()

        mock_download_track.assert_any_call('test_track_id', 'test_data/Test Playlist/Test Track.mp3')
        mock_download_track.assert_any_call('test_mix_track_id', 'test_data/Test Mix/Test Mix Track.mp3')

    @patch('src.playlist_manager.get_user_playlists')
    @patch('src.playlist_manager.download_track')
    @patch('src.playlist_manager.get_download_location')
    def test_organize_tracks(self, mock_get_download_location, mock_download_track, mock_get_user_playlists):
        mock_get_download_location.return_value = 'test_data'
        mock_get_user_playlists.return_value = {
            'items': [
                {
                    'name': 'Test Playlist',
                    'tracks': {
                        'items': [
                            {
                                'track': {
                                    'name': 'Test Track',
                                    'id': 'test_track_id'
                                }
                            }
                        ]
                    }
                }
            ]
        }

        organize_tracks()

        mock_download_track.assert_any_call('test_track_id', 'test_data/Test Playlist/Test Track.mp3')

    @patch('os.walk')
    def test_is_track_downloaded(self, mock_os_walk):
        mock_os_walk.return_value = [
            ('test_data', [], ['Test Track.mp3'])
        ]

        result = is_track_downloaded('Test Track', 'test_data')
        self.assertTrue(result)

        result = is_track_downloaded('Nonexistent Track', 'test_data')
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
