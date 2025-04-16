import spotipy
from spotipy.oauth2 import SpotifyOAuth
import configparser

# Read settings from settings.ini
config = configparser.ConfigParser()
config.read('config/settings.ini')

CLIENT_ID = config['DEFAULT']['CLIENT_ID']
CLIENT_SECRET = config['DEFAULT']['CLIENT_SECRET']
REDIRECT_URI = config['DEFAULT']['REDIRECT_URI']

# Authenticate and obtain access token
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI)
token_info = sp_oauth.get_access_token()
access_token = token_info['access_token']

# Create Spotify client
sp = spotipy.Spotify(auth=access_token)

# Fetch user's playlists
def get_user_playlists():
    playlists = sp.current_user_playlists()
    return playlists

# Fetch user's personalized mixes
def get_user_personalized_mixes():
    mixes = sp.current_user_top_tracks()
    return mixes

# Store access token securely for subsequent API calls
def get_access_token():
    return access_token
