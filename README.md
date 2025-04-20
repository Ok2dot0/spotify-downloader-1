# Spotify Album Downloader and Burner v2.0.0

A powerful command-line and menu-driven application that lets you search for songs or albums on Spotify, display them with detailed information, download them using multithreaded performance, and burn them directly to CD/DVD using native Windows IMAPI2 COM interface.

![Spotify Downloader and Burner](https://img.shields.io/badge/Spotify-Downloader-1DB954?style=for-the-badge&logo=spotify&logoColor=white)

## 🌟 Features

- 🔍 **Powerful Search**: Find tracks and albums on Spotify with ease
- ⚡ **Multithreaded Downloads**: Download multiple tracks simultaneously for maximum speed
- 💿 **Direct CD/DVD Burning**: Burn your music to disc using native Windows IMAPI2 interface
- 🎵 **Multiple Audio Formats**: Choose from MP3, FLAC, OGG, and more
- 📊 **Library Management**: Organize, play, and manage your downloaded music
- ⚙️ **Advanced Settings**: Customize download location, audio quality, and more
- 🎛️ **User-Friendly Interface**: Beautiful terminal interface using Rich and Colorama

## 📋 Requirements

- Python 3.6+
- Windows OS for native CD/DVD burning (fallback options for other platforms)
- Spotify Developer API credentials

## 💻 Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/spotify-downloader.git
cd spotify-downloader
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Set up your Spotify API credentials:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
   - Create a new application
   - Get your Client ID and Client Secret
   - Set these as environment variables or use `.env` file:
   ```
   SPOTIPY_CLIENT_ID=your_client_id
   SPOTIPY_CLIENT_SECRET=your_client_secret
   ```

## 🚀 Usage

### Menu-Driven Interface

Run the application without parameters to use the interactive menu:

```bash
python spotify_burner.py
```

This will open the main menu with the following options:
1. **Manage Existing Albums** - Play, burn or delete your downloaded albums
2. **Search & Download** - Find and download new music from Spotify
3. **Settings** - Configure download and burning options
4. **About** - Information about the application

### Command-Line Usage

For direct command-line usage:

```bash
python spotify_burner.py "Album or track name"
```

### Advanced Options

```
usage: spotify_burner.py [-h] [-o OUTPUT] [--drive DRIVE] [-t THREADS] [--version] [--format {mp3,flac,ogg,m4a,opus,wav}] [--bitrate {128k,192k,256k,320k,best}] [query]

Spotify Album Downloader and Burner - Search, download, and burn music from Spotify.

positional arguments:
  query                 Song or album name to search for (optional)

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Custom output directory for downloads
  --drive DRIVE         Specify CD/DVD drive letter (Windows only)
  -t THREADS, --threads THREADS
                        Maximum number of download threads (1-10)
  --version             show program's version number and exit
  --format {mp3,flac,ogg,m4a,opus,wav}
                        Audio format for downloads
  --bitrate {128k,192k,256k,320k,best}
                        Audio bitrate for downloads
```

## 🔥 Key Features in Detail

### Multithreaded Downloads

The application uses Python's ThreadPoolExecutor to download multiple tracks at once:
- Default: 3 concurrent downloads
- Configurable: Up to 10 threads
- Dynamic progress tracking for each download

### Native CD/DVD Burning

On Windows, the application uses the IMAPI2 COM interface for direct disc burning:
- Auto-detection of optical drives
- Volume naming
- Support for CD-R, CD-RW, DVD±R, and DVD±RW
- Fallback to Windows shell integration on systems without pywin32

### Music Library Management

Manage your downloaded music collection:
- List all albums with track counts and sizes
- Play albums using your default media player
- Burn existing albums to disc
- Delete unwanted albums

### Configurable Settings

Customize application behavior:
- Download directory location
- Optical drive selection
- Audio format (MP3, FLAC, OGG, M4A, OPUS, WAV)
- Bitrate quality (128k to 320k or "best")
- Download thread count

## 📝 Notes

- This tool is for personal use only
- Please respect copyright laws and terms of service
- CD/DVD burning features work best on Windows with pywin32 installed

## 🙏 Credits

This application uses several excellent open-source projects:
- [Spotipy](https://github.com/plamere/spotipy) - Lightweight Python client for Spotify API
- [SpotDL](https://github.com/spotDL/spotify-downloader) - Download music from Spotify
- [Rich](https://github.com/willmcgugan/rich) - Beautiful terminal formatting
- [Colorama](https://github.com/tartley/colorama) - Cross-platform colored terminal output
- [Python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
