# Spotify Album Downloader and Burner v2.0.0

A powerful command-line and menu-driven application that lets you search for songs or albums on Spotify, display them with detailed information, download them using multithreaded performance, and burn them directly to CD/DVD using native Windows IMAPI2 COM interface. **NEW: Now features AI-powered music discovery using Llama 3.2 Vision and other multimodal AI models!**

![Spotify Downloader and Burner](https://img.shields.io/badge/Spotify-Downloader-1DB954?style=for-the-badge&logo=spotify&logoColor=white)
[![Python Package](https://github.com/username/spotify-burner/actions/workflows/python-package.yml/badge.svg)](https://github.com/username/spotify-burner/actions/workflows/python-package.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🌟 Features

- 🔍 **Powerful Search**: Find tracks and albums on Spotify with ease
- 🤖 **AI Music Discovery**: NEW! Use Llama 3.2 Vision to analyze images and find music
- 📷 **Image Analysis**: Upload album covers, concert posters, or music-related photos
- 📝 **Text Analysis**: Analyze lyrics, descriptions, or music-related text  
- ⚡ **Multithreaded Downloads**: Download multiple tracks simultaneously for maximum speed
- 💿 **Direct CD/DVD Burning**: Burn your music to disc using native Windows IMAPI2 interface
- 🎵 **Multiple Audio Formats**: Choose from MP3, FLAC, OGG, and more
- 📊 **Library Management**: Organize, play, and manage your downloaded music
- ⚙️ **Advanced Settings**: Customize download location, audio quality, and AI providers
- 🎛️ **User-Friendly Interface**: Beautiful terminal interface using Rich and Colorama

## 📋 Requirements

- Python 3.6+
- Windows OS for native CD/DVD burning (fallback options for other platforms)
- Spotify Developer API credentials
- **AI Features (Optional)**: Ollama, OpenAI API, or Anthropic API for AI music discovery

## 💻 Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip install spotify-album-burner

# For Windows users who want full CD/DVD burning functionality:
pip install "spotify-album-burner[windows]"

# For developers who want to contribute:
pip install "spotify-album-burner[dev]"
```

### Option 2: Install from source

1. Clone this repository:
   ```bash
   git clone https://github.com/username/spotify-burner.git
   cd spotify-burner
   ```

2. Install the package in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

### Setting up Spotify API credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Create a new application
3. Get your Client ID and Client Secret
4. Set these up using one of these methods:
   
   **Method A**: Environment variables
   ```bash
   export SPOTIPY_CLIENT_ID=your_client_id
   export SPOTIPY_CLIENT_SECRET=your_client_secret
   ```
   
   **Method B**: Create a `.env` file in the project directory:
   ```
   SPOTIPY_CLIENT_ID=your_client_id
   SPOTIPY_CLIENT_SECRET=your_client_secret
   ```
   
   **Method C**: Enter them when prompted on first run

### Setting up AI Music Discovery (Optional)

The application now supports AI-powered music discovery using multimodal AI models like Llama 3.2 Vision. Choose one of these providers:

#### Option A: Ollama (Local, Free)
1. Install [Ollama](https://ollama.ai/)
2. Pull the Llama 3.2 Vision model: `ollama pull llama3.2-vision:latest`
3. Set environment variables:
   ```bash
   export AI_PROVIDER=ollama
   export AI_MODEL=llama3.2-vision:latest
   export OLLAMA_BASE_URL=http://localhost:11434
   ```

#### Option B: OpenAI (Cloud, Paid)
1. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
2. Set environment variables:
   ```bash
   export AI_PROVIDER=openai
   export AI_MODEL=gpt-4-vision-preview
   export OPENAI_API_KEY=your_openai_api_key
   ```

#### Option C: Anthropic (Cloud, Paid)
1. Get an API key from [Anthropic](https://console.anthropic.com/)
2. Set environment variables:
   ```bash
   export AI_PROVIDER=anthropic  
   export AI_MODEL=claude-3-sonnet-20240229
   export ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

## 🚀 Usage

### Menu-Driven Interface

Run the application without parameters to use the interactive menu:

```bash
# If installed with pip:
spotify-burner

# If running from source:
python spotify_burner.py
```

This will open the main menu with the following options:
1. **Manage Existing Albums** - Play, burn or delete your downloaded albums
2. **Search & Download** - Find and download new music from Spotify
3. **Video Management** - Download and manage videos from URLs
4. **AI Music Discovery** - Use AI to analyze images and find music (if configured)
5. **Settings** - Configure download and burning options
6. **About** - Information about the application

### Command-Line Usage

For direct command-line usage:

```bash
spotify-burner "Album or track name"
```

### Advanced Options

```
usage: spotify-burner [-h] [-o OUTPUT] [--drive DRIVE] [-t THREADS] [--version] [--format {mp3,flac,ogg,m4a,opus,wav}] [--bitrate {128k,192k,256k,320k,best}] [query]

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

### 🤖 AI Music Discovery (NEW!)

The application now includes advanced AI capabilities for discovering music through multimodal analysis:

#### Image Analysis
- Upload album covers, concert posters, or music-related photos
- AI analyzes images to identify artists, albums, songs, and genres
- Automatically generates optimized Spotify search queries
- Supports multiple image formats (JPG, PNG, GIF, BMP, WebP)

#### Text Analysis  
- Analyze song lyrics, artist descriptions, or music-related text
- Extract musical entities and context using natural language processing
- Generate targeted search queries based on textual content

#### Supported AI Models
- **Llama 3.2 Vision** (via Ollama): Free, local processing
- **GPT-4 Vision** (via OpenAI): Cloud-based, high accuracy
- **Claude 3 Vision** (via Anthropic): Cloud-based, nuanced analysis

#### How It Works
1. Select "AI Music Discovery" from the main menu
2. Choose to analyze an image file or enter text
3. AI processes the input and extracts musical information
4. Generated search queries are executed on Spotify
5. Select and download music using the existing workflow

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

## 🧑‍💻 Development

Please see the [Contributing Guide](CONTRIBUTING.md) for information on how to develop and contribute to this project.

## 🙏 Credits

This application uses several excellent open-source projects:
- [Spotipy](https://github.com/plamere/spotipy) - Lightweight Python client for Spotify API
- [SpotDL](https://github.com/spotDL/spotify-downloader) - Download music from Spotify
- [Rich](https://github.com/willmcgugan/rich) - Beautiful terminal formatting
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading functionality
- [Colorama](https://github.com/tartley/colorama) - Cross-platform colored terminal output
- [Python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
- [Pillow](https://github.com/python-pillow/Pillow) - Image processing for AI features
- [Ollama](https://ollama.ai/) - Local AI model serving (optional)
- [OpenAI](https://openai.com/) - GPT-4 Vision API (optional)
- [Anthropic](https://anthropic.com/) - Claude 3 Vision API (optional)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
