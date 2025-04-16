import os
import shutil
from src.spotify_api import get_user_playlists, get_user_personalized_mixes
from src.downloader import download_track
from src.settings import get_download_location

# Fetch and organize playlists from Spotify
def fetch_and_organize_playlists():
    playlists = get_user_playlists()
    personalized_mixes = get_user_personalized_mixes()
    download_location = get_download_location()

    for playlist in playlists['items']:
        playlist_name = playlist['name']
        playlist_folder = os.path.join(download_location, playlist_name)
        os.makedirs(playlist_folder, exist_ok=True)

        tracks = playlist['tracks']['items']
        for track in tracks:
            track_name = track['track']['name']
            track_id = track['track']['id']
            track_path = os.path.join(playlist_folder, f"{track_name}.mp3")

            if not os.path.exists(track_path):
                download_track(track_id, track_path)
            else:
                print(f"Track {track_name} already exists in {playlist_name}")

    for mix in personalized_mixes['items']:
        mix_name = mix['name']
        mix_folder = os.path.join(download_location, mix_name)
        os.makedirs(mix_folder, exist_ok=True)

        tracks = mix['tracks']['items']
        for track in tracks:
            track_name = track['track']['name']
            track_id = track['track']['id']
            track_path = os.path.join(mix_folder, f"{track_name}.mp3")

            if not os.path.exists(track_path):
                download_track(track_id, track_path)
            else:
                print(f"Track {track_name} already exists in {mix_name}")

# Organize downloaded tracks into folders mirroring Spotify structure
def organize_tracks():
    download_location = get_download_location()
    playlists = get_user_playlists()

    for playlist in playlists['items']:
        playlist_name = playlist['name']
        playlist_folder = os.path.join(download_location, playlist_name)
        os.makedirs(playlist_folder, exist_ok=True)

        tracks = playlist['tracks']['items']
        for track in tracks:
            track_name = track['track']['name']
            track_id = track['track']['id']
            track_path = os.path.join(playlist_folder, f"{track_name}.mp3")

            if not os.path.exists(track_path):
                download_track(track_id, track_path)
            else:
                print(f"Track {track_name} already exists in {playlist_name}")

# Implement mechanism to check if a track is already downloaded
def is_track_downloaded(track_name, download_location):
    for root, dirs, files in os.walk(download_location):
        if f"{track_name}.mp3" in files:
            return True
    return False

def copy_existing_track(track_name, source_folder, destination_folder):
    source_path = os.path.join(source_folder, f"{track_name}.mp3")
    destination_path = os.path.join(destination_folder, f"{track_name}.mp3")
    shutil.copy2(source_path, destination_path)
