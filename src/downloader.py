import os
import shutil
from spotdl import Spotdl

# Initialize Spotdl
spotdl = Spotdl()

# Use spotdl library to download tracks
def download_track(track_id, track_path):
    spotdl.download([track_id], output=track_path)

# Copy existing tracks to new playlist folders if already downloaded
def copy_existing_track(track_name, source_folder, destination_folder):
    source_path = os.path.join(source_folder, f"{track_name}.mp3")
    destination_path = os.path.join(destination_folder, f"{track_name}.mp3")
    shutil.copy2(source_path, destination_path)
