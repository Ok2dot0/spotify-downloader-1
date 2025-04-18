from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal, Grid
from textual.widgets import Button, Static, Select, Input, Checkbox, TabPane, Tabs, Tab
from textual.binding import Binding
import json
import os
from typing import Dict, Any

class SpotdlSettingsModal(ModalScreen):
    """Modal dialog for spotdl settings configuration."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]
    
    def __init__(self, initial_settings=None):
        super().__init__()
        self.settings_file = os.path.join("config", "spotdl_settings.json")
        self.settings = self.load_settings() if initial_settings is None else initial_settings
        
    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Static("spotdl Settings", classes="dialog-title")
            
            # Use tabs to organize all the settings
            with Tabs(id="settings-tabs"):
                # Basic tab
                yield Tab("Basic", id="tab-basic")
                
                # Audio tab
                yield Tab("Audio", id="tab-audio")
                
                # Lyrics tab
                yield Tab("Lyrics", id="tab-lyrics")
                
                # Output tab
                yield Tab("Output", id="tab-output")
                
                # Advanced tab
                yield Tab("Advanced", id="tab-advanced")
                
                # Spotify tab
                yield Tab("Spotify", id="tab-spotify")
            
            # Tab content area
            with Container(id="tab-content"):
                # Basic tab content
                with TabPane("tab-basic", id="pane-basic"):
                    yield Static("Output Format:", classes="settings-label")
                    yield Select(
                        [(f"Format: {fmt}", fmt) for fmt in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]], 
                        value=self.settings.get("format", "mp3"),
                        id="select-format"
                    )
                    
                    yield Static("Bitrate:", classes="settings-label")
                    bitrates = ["auto", "disable", "8k", "16k", "24k", "32k", "48k", "64k", "96k", "128k", "160k", "192k", "224k", "256k", "320k"]
                    yield Select(
                        [(f"Bitrate: {br}", br) for br in bitrates],
                        value=self.settings.get("bitrate", "auto"),
                        id="select-bitrate"
                    )
                    
                    yield Static("Output Template:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("output", "{title}.{output-ext}"),
                        placeholder="{title}.{output-ext}",
                        id="input-output-template"
                    )
                    
                    yield Static("Additional Options:", classes="settings-label")
                    with Grid(id="basic-options-grid"):
                        with Horizontal():
                            yield Static("Use SponsorBlock:", classes="checkbox-label")
                            yield Checkbox(value=self.settings.get("sponsor_block", False), id="checkbox-sponsor-block")
                        
                        with Horizontal():
                            yield Static("Playlist Numbering:", classes="checkbox-label")
                            yield Checkbox(value=self.settings.get("playlist_numbering", False), id="checkbox-playlist-numbering")
                        
                        with Horizontal():
                            yield Static("Threads:", classes="setting-label")
                            yield Input(
                                value=str(self.settings.get("threads", 4)),
                                id="input-threads",
                                type="integer"
                            )
                
                # Audio tab content
                with TabPane("tab-audio", id="pane-audio"):
                    yield Static("Audio Providers:", classes="settings-label")
                    audio_providers = ["youtube", "youtube-music", "slider-kz", "soundcloud", "bandcamp", "piped"]
                    
                    for provider in audio_providers:
                        with Horizontal():
                            yield Static(f"{provider}:", classes="checkbox-label")
                            yield Checkbox(
                                value=provider in self.settings.get("audio", ["youtube"]),
                                id=f"checkbox-{provider}"
                            )
                    
                    yield Static("Audio Options:", classes="settings-label")
                    with Horizontal():
                        yield Static("Don't Filter Results:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("dont_filter_results", False), id="checkbox-dont-filter")
                    
                    with Horizontal():
                        yield Static("Only Verified Results:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("only_verified_results", False), id="checkbox-verified")
                    
                    with Horizontal():
                        yield Static("Album Type:", classes="setting-label")
                        yield Select(
                            [("Album", "album"), ("Single", "single")],
                            value=self.settings.get("album_type", "album"),
                            id="select-album-type"
                        )
                
                # Lyrics tab content
                with TabPane("tab-lyrics", id="pane-lyrics"):
                    yield Static("Lyrics Providers:", classes="settings-label")
                    lyrics_providers = ["genius", "musixmatch", "azlyrics", "synced"]
                    
                    for provider in lyrics_providers:
                        with Horizontal():
                            yield Static(f"{provider}:", classes="checkbox-label")
                            yield Checkbox(
                                value=provider in self.settings.get("lyrics", ["genius"]),
                                id=f"checkbox-lyrics-{provider}"
                            )
                    
                    yield Static("Genius API Token:", classes="settings-label highlight")
                    yield Input(
                        value=self.settings.get("genius_token", ""),
                        placeholder="Enter your Genius access token here",
                        password=True,
                        id="input-genius-token"
                    )
                    yield Static("Get a token at [link=https://genius.com/api-clients]genius.com/api-clients[/]", classes="help-text")
                    
                    yield Static("Lyrics Options:", classes="settings-label")
                    with Horizontal():
                        yield Static("Generate LRC Files:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("generate_lrc", False), id="checkbox-lrc")
                
                # Output tab content
                with TabPane("tab-output", id="pane-output"):
                    yield Static("Output Options:", classes="settings-label")
                    
                    with Horizontal():
                        yield Static("M3U Playlist:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("m3u", False), id="checkbox-m3u")
                    
                    yield Static("M3U Filename:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("m3u_name", "{list[0]}.m3u8"),
                        placeholder="{list[0]}.m3u8",
                        id="input-m3u-name",
                        disabled=not self.settings.get("m3u", False)
                    )
                    
                    yield Static("Overwrite Mode:", classes="settings-label")
                    yield Select(
                        [("Skip", "skip"), ("Metadata only", "metadata"), ("Force", "force")],
                        value=self.settings.get("overwrite", "skip"),
                        id="select-overwrite"
                    )
                    
                    yield Static("Filename Restrictions:", classes="settings-label")
                    yield Select(
                        [("None", "none"), ("ASCII only", "ascii"), ("Strict", "strict")],
                        value=self.settings.get("restrict", "none"),
                        id="select-restrict"
                    )
                    
                    with Horizontal():
                        yield Static("Scan For Existing Songs:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("scan_for_songs", False), id="checkbox-scan-songs")
                    
                    with Horizontal():
                        yield Static("Skip Explicit Songs:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("skip_explicit", False), id="checkbox-skip-explicit")
                
                # Advanced tab content
                with TabPane("tab-advanced", id="pane-advanced"):
                    yield Static("Advanced Options:", classes="settings-label")
                    
                    yield Static("FFmpeg Path:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("ffmpeg", "ffmpeg"),
                        placeholder="Path to ffmpeg executable",
                        id="input-ffmpeg"
                    )
                    
                    yield Static("FFmpeg Arguments:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("ffmpeg_args", ""),
                        placeholder="Additional ffmpeg arguments",
                        id="input-ffmpeg-args"
                    )
                    
                    yield Static("YT-DLP Arguments:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("yt_dlp_args", ""),
                        placeholder="Arguments to pass to yt-dlp",
                        id="input-ytdlp-args"
                    )
                    
                    yield Static("Proxy Server:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("proxy", ""),
                        placeholder="http://host:port",
                        id="input-proxy"
                    )
                    
                    with Horizontal():
                        yield Static("Force Update Metadata:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("force_update_metadata", False), id="checkbox-force-metadata")
                    
                    with Horizontal():
                        yield Static("Create Skip File:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("create_skip_file", False), id="checkbox-create-skip")
                    
                    with Horizontal():
                        yield Static("Respect Skip File:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("respect_skip_file", False), id="checkbox-respect-skip")
                
                # Spotify tab content
                with TabPane("tab-spotify", id="pane-spotify"):
                    yield Static("Spotify Connection:", classes="settings-label")
                    
                    with Horizontal():
                        yield Static("Use OAuth:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("user_auth", False), id="checkbox-user-auth")
                    
                    yield Static("Cache Path:", classes="settings-label")
                    yield Input(
                        value=self.settings.get("cache_path", ""),
                        placeholder="Path for spotipy cache file",
                        id="input-cache-path"
                    )
                    
                    with Horizontal():
                        yield Static("Disable Cache:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("no_cache", False), id="checkbox-no-cache")
                    
                    yield Static("Max Retries:", classes="settings-label")
                    yield Input(
                        value=str(self.settings.get("max_retries", 3)),
                        id="input-max-retries",
                        type="integer"
                    )
                    
                    with Horizontal():
                        yield Static("Headless Mode:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("headless", True), id="checkbox-headless")
                    
                    with Horizontal():
                        yield Static("Use Cache File:", classes="checkbox-label")
                        yield Checkbox(value=self.settings.get("use_cache_file", False), id="checkbox-use-cache")
            
            with Horizontal(id="settings-dialog-buttons"):
                yield Button("Save", variant="primary", id="btn-save-settings")
                yield Button("Cancel", variant="error", id="btn-cancel-settings")
    
    def on_tabs_tab_activated(self, event) -> None:
        """Handle tab changes."""
        # Show the corresponding tab pane
        tab_id = event.tab.id
        pane_id = f"pane-{tab_id.split('-')[1]}"
        
        # Hide all panes
        for pane in self.query(TabPane):
            pane.display = False
        
        # Show selected pane
        self.query_one(f"#{pane_id}").display = True
    
    def on_mount(self) -> None:
        """Set up the initial tab display."""
        # Only show the first tab pane initially
        for i, pane in enumerate(self.query(TabPane)):
            pane.display = i == 0
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "btn-save-settings":
            self.collect_settings()
            self.save_current_settings()
            self.dismiss(self.settings)
        elif button_id == "btn-cancel-settings":
            self.dismiss(None)
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes."""
        select_id = event.select.id
        value = event.value
        
        if select_id == "select-format":
            self.settings["format"] = value
        elif select_id == "select-bitrate":
            self.settings["bitrate"] = value
        elif select_id == "select-album-type":
            self.settings["album_type"] = value
        elif select_id == "select-overwrite":
            self.settings["overwrite"] = value
        elif select_id == "select-restrict":
            self.settings["restrict"] = value
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        input_id = event.input.id
        value = event.value
        
        if input_id == "input-output-template":
            self.settings["output"] = value
        elif input_id == "input-threads":
            try:
                self.settings["threads"] = int(value) if value else 1
            except ValueError:
                # Reset to default if not a number
                self.settings["threads"] = 1
        elif input_id == "input-genius-token":
            self.settings["genius_token"] = value
        elif input_id == "input-m3u-name":
            self.settings["m3u_name"] = value
        elif input_id == "input-ffmpeg":
            self.settings["ffmpeg"] = value
        elif input_id == "input-ffmpeg-args":
            self.settings["ffmpeg_args"] = value
        elif input_id == "input-ytdlp-args":
            self.settings["yt_dlp_args"] = value
        elif input_id == "input-proxy":
            self.settings["proxy"] = value
        elif input_id == "input-cache-path":
            self.settings["cache_path"] = value
        elif input_id == "input-max-retries":
            try:
                self.settings["max_retries"] = int(value) if value else 3
            except ValueError:
                self.settings["max_retries"] = 3
    
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes."""
        checkbox_id = event.checkbox.id
        is_checked = event.value
        
        # Special handling for provider checkboxes
        if checkbox_id.startswith("checkbox-lyrics-"):
            provider = checkbox_id.replace("checkbox-lyrics-", "")
            if "lyrics" not in self.settings:
                self.settings["lyrics"] = []
            
            if is_checked and provider not in self.settings["lyrics"]:
                self.settings["lyrics"].append(provider)
            elif not is_checked and provider in self.settings["lyrics"]:
                self.settings["lyrics"].remove(provider)
                
        elif checkbox_id.startswith("checkbox-") and checkbox_id[9:] in ["youtube", "youtube-music", "slider-kz", "soundcloud", "bandcamp", "piped"]:
            provider = checkbox_id[9:] # Remove "checkbox-" prefix
            if "audio" not in self.settings:
                self.settings["audio"] = []
            
            if is_checked and provider not in self.settings["audio"]:
                self.settings["audio"].append(provider)
            elif not is_checked and provider in self.settings["audio"]:
                self.settings["audio"].remove(provider)
        
        # Regular checkbox settings
        elif checkbox_id == "checkbox-lrc":
            self.settings["generate_lrc"] = is_checked
        elif checkbox_id == "checkbox-sponsor-block":
            self.settings["sponsor_block"] = is_checked
        elif checkbox_id == "checkbox-playlist-numbering":
            self.settings["playlist_numbering"] = is_checked
        elif checkbox_id == "checkbox-dont-filter":
            self.settings["dont_filter_results"] = is_checked
        elif checkbox_id == "checkbox-verified":
            self.settings["only_verified_results"] = is_checked
        elif checkbox_id == "checkbox-m3u":
            self.settings["m3u"] = is_checked
            # Enable/disable M3U filename input based on checkbox
            m3u_input = self.query_one("#input-m3u-name")
            m3u_input.disabled = not is_checked
        elif checkbox_id == "checkbox-scan-songs":
            self.settings["scan_for_songs"] = is_checked
        elif checkbox_id == "checkbox-skip-explicit":
            self.settings["skip_explicit"] = is_checked
        elif checkbox_id == "checkbox-force-metadata":
            self.settings["force_update_metadata"] = is_checked
        elif checkbox_id == "checkbox-create-skip":
            self.settings["create_skip_file"] = is_checked
        elif checkbox_id == "checkbox-respect-skip":
            self.settings["respect_skip_file"] = is_checked
        elif checkbox_id == "checkbox-user-auth":
            self.settings["user_auth"] = is_checked
        elif checkbox_id == "checkbox-no-cache":
            self.settings["no_cache"] = is_checked
        elif checkbox_id == "checkbox-headless":
            self.settings["headless"] = is_checked
        elif checkbox_id == "checkbox-use-cache":
            self.settings["use_cache_file"] = is_checked
    
    def collect_settings(self) -> None:
        """Collect settings from all controls."""
        # This method collects any settings that might not be collected by the onChange handlers
        # Most settings are already collected in the event handlers
        pass
    
    def save_current_settings(self) -> None:
        """Save settings to a file."""
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from a file."""
        default_settings = {
            "format": "mp3",
            "bitrate": "auto",
            "output": "{title}.{output-ext}",
            "lyrics": ["genius"],
            "audio": ["youtube"],
            "generate_lrc": False,
            "sponsor_block": False,
            "playlist_numbering": False,
            "threads": 4,
            "genius_token": "",  # Highlighted as important by the user
            "m3u": False,
            "m3u_name": "{list[0]}.m3u8",
            "overwrite": "skip",
            "restrict": "none",
            "user_auth": False,
            "headless": True
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass  # If there's any error, return default settings
            
        return default_settings
