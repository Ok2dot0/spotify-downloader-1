# Spotify Playlist Downloader

## Overview

This application connects to your Spotify account, fetches all your playlists, and downloads them using `spotdl`. It organizes the downloaded tracks into folders that mirror the structure of your playlists on Spotify. The application also supports downloading personalized mixes and Spotify-generated playlists for your specific account. It ensures that the songs and folders are updated according to changes on Spotify. If a track is already downloaded and appears in more than one playlist, it will be copied instead of downloaded again. The application works on both Windows and Linux, using actual copies of files instead of symlinks. The settings are stored in a `settings.ini` file.

## Features

- Connects to your Spotify account using OAuth 2.0 authentication.
- Fetches and organizes playlists and personalized mixes from Spotify.
- Downloads tracks using the `spotdl` library.
- Organizes downloaded tracks into folders that mirror the structure of your playlists on Spotify.
- Checks if a track is already downloaded and copies it to other playlists instead of downloading it again.
- Periodically updates the downloaded tracks and folders to reflect changes on Spotify.
- Modern-looking terminal interface with clickable elements and interactive checkboxes.
- Configurable settings stored in a `settings.ini` file.

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/githubnext/workspace-blank.git
   cd workspace-blank
   ```

2. Install the required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Create a `settings.ini` file in the `config/` directory with the following content:
   ```ini
   [DEFAULT]
   CLIENT_ID = your_spotify_client_id
   CLIENT_SECRET = your_spotify_client_secret
   REDIRECT_URI = http://127.0.0.1:8080

   [SETTINGS]
   DOWNLOAD_LIKED = True
   UPDATE_FREQUENCY = daily
   DOWNLOAD_LOCATION = data/
   ```

## Usage

1. Run the application:
   ```sh
   python src/interface.py
   ```

2. Follow the instructions in the terminal interface to authenticate with your Spotify account and select the playlists and mixes to download.

3. The application will download the selected tracks and organize them into folders that mirror the structure of your playlists on Spotify.

4. The application will periodically update the downloaded tracks and folders based on changes on Spotify. You can also manually trigger an update through the terminal interface.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
