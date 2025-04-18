import spotipy
from spotipy.oauth2 import SpotifyOAuth
import configparser

# Read settings from settings.ini
config = configparser.ConfigParser()
config.read('config/settings.ini')

CLIENT_ID = config['DEFAULT']['CLIENT_ID']
CLIENT_SECRET = config['DEFAULT']['CLIENT_SECRET']
REDIRECT_URI = config['DEFAULT']['REDIRECT_URI']

# Define the required scopes - add user-library-read for liked songs
SCOPE = "playlist-read-private user-top-read user-library-read"

# Authenticate and obtain access token
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
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

# Fetch tracks for a specific playlist ID
def get_playlist_tracks(playlist_id):
    """Fetches all tracks for a given playlist ID."""
    tracks = []
    try:
        results = sp.playlist_items(playlist_id, fields='items(track(id,name,artists(name))),next')
        tracks.extend(results['items'])
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        # Filter out potential null tracks if any
        return [item['track'] for item in tracks if item and item.get('track')]
    except Exception as e:
        print(f"Error fetching tracks for playlist {playlist_id}: {e}")
        return [] # Return empty list on error for now

# Fetch details for a specific playlist ID
def get_playlist_by_id(playlist_id):
    """Fetches details for a single playlist by its ID."""
    try:
        playlist = sp.playlist(playlist_id, fields='id,name,tracks(total)')
        return playlist
    except Exception as e:
        print(f"Error fetching playlist details for {playlist_id}: {e}")
        return None # Return None on error

# Improve liked songs fetching to match spotify_downloader.py implementation
def get_user_liked_tracks():
    """Fetches the user's liked/saved tracks from Spotify."""
    tracks = []
    try:
        results = sp.current_user_saved_tracks(limit=50)
        while results:
            tracks.extend(results['items'])
            if results['next']:
                results = sp.next(results)
            else:
                break
                
        # Return in the format expected by the application
        return {'items': tracks, 'name': 'Liked Songs', 'id': 'liked_songs'}
    except Exception as e:
        print(f"Error fetching liked tracks: {e}")
        return {'items': [], 'name': 'Liked Songs', 'id': 'liked_songs'}

# Store access token securely for subsequent API calls
def get_access_token():
    return access_token
