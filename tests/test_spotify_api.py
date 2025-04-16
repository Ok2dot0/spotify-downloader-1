import unittest
from unittest.mock import patch, MagicMock
import src.spotify_api as spotify_api

class TestSpotifyAPI(unittest.TestCase):

    @patch('src.spotify_api.SpotifyOAuth')
    @patch('src.spotify_api.configparser.ConfigParser')
    def test_authentication(self, mock_config, mock_spotify_oauth):
        # Mock the config parser
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.read.return_value = None
        mock_config_instance['DEFAULT']['CLIENT_ID'] = 'test_client_id'
        mock_config_instance['DEFAULT']['CLIENT_SECRET'] = 'test_client_secret'
        mock_config_instance['DEFAULT']['REDIRECT_URI'] = 'http://127.0.0.1:8080'

        # Mock the SpotifyOAuth
        mock_spotify_oauth_instance = MagicMock()
        mock_spotify_oauth.return_value = mock_spotify_oauth_instance
        mock_spotify_oauth_instance.get_access_token.return_value = {'access_token': 'test_access_token'}

        # Call the function
        access_token = spotify_api.get_access_token()

        # Assert the access token is correct
        self.assertEqual(access_token, 'test_access_token')

    @patch('src.spotify_api.sp')
    def test_get_user_playlists(self, mock_sp):
        # Mock the Spotify client
        mock_sp_instance = MagicMock()
        mock_sp.return_value = mock_sp_instance
        mock_sp_instance.current_user_playlists.return_value = {'items': ['playlist1', 'playlist2']}

        # Call the function
        playlists = spotify_api.get_user_playlists()

        # Assert the playlists are correct
        self.assertEqual(playlists, {'items': ['playlist1', 'playlist2']})

    @patch('src.spotify_api.sp')
    def test_get_user_personalized_mixes(self, mock_sp):
        # Mock the Spotify client
        mock_sp_instance = MagicMock()
        mock_sp.return_value = mock_sp_instance
        mock_sp_instance.current_user_top_tracks.return_value = {'items': ['track1', 'track2']}

        # Call the function
        mixes = spotify_api.get_user_personalized_mixes()

        # Assert the mixes are correct
        self.assertEqual(mixes, {'items': ['track1', 'track2']})

if __name__ == '__main__':
    unittest.main()
