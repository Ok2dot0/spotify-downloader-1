# Spotify Album Downloader and Burner

## Overview

Spotify Album Downloader and Burner is a powerful command-line tool that allows you to search, download, and burn music from Spotify. This tool is designed to be portable and easy to use on Windows.

## Features

- Search for songs or albums on Spotify
- Download music using spotdl
- Burn downloaded music to CD/DVD
- Automated environment setup
- Setup wizard for initial configuration
- Windows-only support

## Requirements

- Windows 10 or later
- Python 3.6 or later
- Spotify API credentials (Client ID and Client Secret)
- CDBurnerXP (for burning CDs/DVDs)

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/Ok2dot0/spotify-downloader-1.git
   cd spotify-downloader-1
   ```

2. Install the required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Set up the environment variables:
   ```sh
   cp .env.sample .env
   ```

4. Edit the `.env` file and add your Spotify API credentials:
   ```sh
   SPOTIPY_CLIENT_ID=your_spotify_client_id_here
   SPOTIPY_CLIENT_SECRET=your_spotify_client_secret_here
   ```

## Usage

### Running the Tool

To run the tool, use the following command:
```sh
python spotify_burner.py
```

### Setup Wizard

The setup wizard will guide you through the initial configuration and setup process. Follow the on-screen instructions to set up your environment variables and other settings.

### Searching and Downloading Music

1. Select the "Search & Download" option from the main menu.
2. Enter the song or album name to search for.
3. Select the desired item from the search results.
4. Confirm the download and wait for the process to complete.

### Burning Music to CD/DVD

1. After downloading music, select the "Burn to CD/DVD" option from the main menu.
2. Insert a blank CD/DVD into your drive.
3. Follow the on-screen instructions to complete the burning process.

## Creating an Executable

To create a single executable file for Windows using PyInstaller, run the following command:
```sh
pyinstaller --onefile spotify_burner.py
```

The executable file will be created in the `dist` directory.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
