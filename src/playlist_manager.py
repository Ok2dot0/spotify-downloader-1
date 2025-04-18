import os
import shutil
# Import sp for making API calls within this module
from src.spotify_api import get_user_playlists, get_user_personalized_mixes, sp, get_playlist_tracks
from src.downloader import download_track
from src.settings import get_download_location
import re # Import regex for sanitization
import lyricsgenius

# Function to sanitize filenames
def sanitize_filename(name):
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace sequences of whitespace with a single space
    name = re.sub(r'\s+', ' ', name).strip()
    # Limit length if necessary (optional)
    # max_len = 100
    # name = name[:max_len]
    return name

def get_genius_token():
    """Get the Genius API token from settings."""
    settings_file = os.path.join("config", "spotdl_settings.json")
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                settings = json.load(f)
                return settings.get("genius_token", "")
    except Exception:
        pass
    return ""

def fetch_lyrics(track):
    """Fetch lyrics from Genius using track name and artist."""
    genius_token = get_genius_token()
    if not genius_token:
        return None
        
    try:
        genius = lyricsgenius.Genius(genius_token)
        artist = track['artists'][0]['name'] if track.get('artists') else ''
        song = genius.search_song(track['name'], artist)
        return song.lyrics if song else None
    except Exception as e:
        print(f"Error fetching lyrics for {track['name']}: {str(e)}")
        return None

def embed_lyrics(file_path, lyrics):
    """Embed lyrics into the audio file's ID3 tag using USLT frame."""
    from mutagen.id3 import ID3, USLT
    try:
        audio = ID3(file_path)
    except Exception:
        audio = ID3()
    audio.delall("USLT")
    audio.add(USLT(encoding=3, lang="eng", desc="Lyrics", text=lyrics))
    audio.save(file_path)

# NOTE: fetch_and_organize_playlists downloads EVERYTHING.
# We will use a new function `process_downloads` for selected items.
def fetch_and_organize_playlists():
    # ... (keep existing function as is for now, or deprecate later) ...
    pass # Placeholder to avoid modifying it now

def process_downloads(selected_playlist_objects: list, liked_songs_object=None, log_callback=print):
    """
    Processes the download for selected playlists and liked songs.

    Args:
        selected_playlist_objects: A list of playlist dictionary objects.
        liked_songs_object: Optional object containing liked songs data.
        log_callback: A function to call for logging messages (e.g., log.write_line).
    """
    download_location = get_download_location()
    log_callback(f"Download location: {download_location}")
    
    # Check if we have a Genius token configured
    genius_token = get_genius_token()
    have_lyrics = bool(genius_token)
    if have_lyrics:
        log_callback(f"[green]Genius lyrics API configured - will fetch lyrics for tracks[/]")
    else:
        log_callback(f"[yellow]No Genius API token found - lyrics will not be embedded[/]")

    # --- Process Playlists ---
    if selected_playlist_objects:
        log_callback(f"Processing {len(selected_playlist_objects)} selected playlists...")
        for playlist in selected_playlist_objects:
            if not playlist or 'name' not in playlist or 'id' not in playlist:
                log_callback(f"[yellow]Skipping invalid playlist data: {playlist}[/]")
                continue

            playlist_name = sanitize_filename(playlist['name'])
            playlist_id = playlist['id']
            playlist_folder = os.path.join(download_location, playlist_name)
            log_callback(f"Processing playlist: '{playlist_name}'")

            try:
                # Fetch tracks for the current playlist
                playlist_tracks = get_playlist_tracks(playlist_id)

                if not playlist_tracks:
                    log_callback(f"  No tracks found or error fetching tracks for '{playlist_name}'.")
                    continue

                log_callback(f"  Found {len(playlist_tracks)} tracks. Downloading...")
                for track in playlist_tracks:
                    if track and track.get('id') and track.get('name'):
                        track_name = sanitize_filename(track['name'])
                        track_id = track['id']
                        
                        log_callback(f"    Downloading '{track_name}'...")
                        try:
                            # Pass just the folder path to download_track
                            success = download_track(track_id, playlist_folder)
                            
                            # If download was successful and we have lyrics capability, try to add lyrics
                            if success and have_lyrics:
                                # Find the downloaded file (likely with .mp3 extension)
                                possible_extensions = ['mp3', 'flac', 'ogg', 'opus', 'm4a', 'wav']
                                found_file = None
                                for ext in possible_extensions:
                                    file_path = os.path.join(playlist_folder, f"{track_name}.{ext}")
                                    if os.path.exists(file_path):
                                        found_file = file_path
                                        break
                                        
                                if found_file:
                                    log_callback(f"      [blue]Fetching lyrics for '{track_name}'[/]")
                                    lyrics = fetch_lyrics(track)
                                    if lyrics:
                                        embed_lyrics(found_file, lyrics)
                                        log_callback(f"      [green]Lyrics embedded successfully[/]")
                                    else:
                                        log_callback(f"      [yellow]No lyrics found for '{track_name}'[/]")
                                        
                            elif not success:
                                log_callback(f"      [red]Failed to download '{track_name}'[/]")
                        except Exception as download_error:
                            log_callback(f"      [red]Error downloading track {track_id} ('{track_name}'): {download_error}[/]")
                    else:
                        log_callback(f"    [yellow]Skipping invalid track data in playlist '{playlist_name}'.[/]")
            except Exception as e:
                log_callback(f"  [red]Error processing playlist '{playlist_name}': {e}[/]")
    else:
        log_callback("No playlists selected for download.")

    # --- Process Liked Songs ---
    if liked_songs_object and liked_songs_object.get('items'):
        log_callback(f"Processing liked songs...")
        liked_folder_name = "Liked Songs"
        liked_folder = os.path.join(download_location, liked_folder_name)
        os.makedirs(liked_folder, exist_ok=True)  # Ensure the directory exists
        
        track_count = len(liked_songs_object['items'])
        log_callback(f"Processing {track_count} liked songs into: '{liked_folder_name}'")
        
        for item in liked_songs_object['items']:
            # Liked songs have a different structure, they include added_at and a track key
            if not item or not item.get('track'):
                continue
                
            track = item['track']
            if track and track.get('id') and track.get('name'):
                track_name = sanitize_filename(track['name'])
                track_id = track['id']
                expected_track_path = os.path.join(liked_folder, f"{track_name}.mp3")

                # Skip if already downloaded
                if os.path.exists(expected_track_path):
                    log_callback(f"    Skipping '{track_name}' (already exists).")
                    continue

                # Show artists in the log 
                artists = ", ".join([artist['name'] for artist in track['artists']]) if track.get('artists') else "Unknown Artist"
                log_callback(f"    Downloading '{track_name}' by {artists}...")
                
                try:
                    success = download_track(track_id, liked_folder)
                    if not success:
                        log_callback(f"      [red]Failed to download '{track_name}'[/]")
                    # If download was successful and we have lyrics capability, try to add lyrics
                    if success and have_lyrics:
                        # Find the downloaded file (likely with .mp3 extension)
                        possible_extensions = ['mp3', 'flac', 'ogg', 'opus', 'm4a', 'wav']
                        found_file = None
                        for ext in possible_extensions:
                            file_path = os.path.join(liked_folder, f"{track_name}.{ext}")
                            if os.path.exists(file_path):
                                found_file = file_path
                                break
                                
                        if found_file:
                            log_callback(f"      [blue]Fetching lyrics for '{track_name}'[/]")
                            lyrics = fetch_lyrics(track)
                            if lyrics:
                                embed_lyrics(found_file, lyrics)
                                log_callback(f"      [green]Lyrics embedded successfully[/]")
                            else:
                                log_callback(f"      [yellow]No lyrics found for '{track_name}'[/]")
                except Exception as download_error:
                    log_callback(f"      [red]Error downloading track {track_id} ('{track_name}'): {download_error}[/]")
            else:
                log_callback(f"    [yellow]Skipping invalid track data in liked songs.[/]")
    elif liked_songs_object:
        log_callback("No liked songs found.")

    log_callback("[green]Download processing finished.[/]")

# Organize downloaded tracks into folders mirroring Spotify structure
# NOTE: This function is likely redundant if fetch_and_organize_playlists handles downloads.
# Consider removing or refactoring its purpose. Updated similarly for now.
def organize_tracks():
    print("[yellow]Warning: organize_tracks function is likely redundant and not used by the TUI download process.[/]")
    pass

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
