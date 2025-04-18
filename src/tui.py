import asyncio
import re
import json
import os
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import (
    Header, Footer, Log, Button, Static, Checkbox, Label,
    Input, Pretty
)
from textual.reactive import var
from textual.screen import ModalScreen
from textual.binding import Binding

# Import necessary functions from your existing modules
from .playlist_manager import process_downloads
from .spotify_api import (
    get_user_playlists, get_playlist_tracks,
    get_playlist_by_id, get_user_liked_tracks
)

# Import the settings modal
from .settings_modal import SpotdlSettingsModal

class PlaylistSongsModal(ModalScreen):
    """A modal dialog to display songs in a playlist."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]
    
    def __init__(self, playlist_id, playlist_name):
        super().__init__()
        self.playlist_id = playlist_id
        self.playlist_name = playlist_name
        self.songs = []
    
    def compose(self) -> ComposeResult:
        with Container(id="songs-dialog"):
            yield Static(f"Songs in '{self.playlist_name}'", classes="dialog-title")
            with VerticalScroll(id="songs-list"):
                yield Static("Loading songs...", id="songs-loading")
            yield Button("Close", variant="primary", id="btn-close-dialog")
    
    def on_mount(self) -> None:
        """Load songs when the modal is mounted."""
        asyncio.create_task(self.load_songs())
    
    async def load_songs(self) -> None:
        """Load songs from the playlist using API call."""
        songs_container = self.query_one("#songs-list")
        
        try:
            fetched_songs = await asyncio.to_thread(get_playlist_tracks, self.playlist_id)
            
            # Remove loading indicator
            songs_container.query_one("#songs-loading").remove()
            
            if fetched_songs:
                self.songs = fetched_songs
                # Create all song Static widgets at once
                song_widgets = []
                for song in self.songs:
                    if song and song.get('name') and song.get('artists'):
                        artists = ", ".join([artist['name'] for artist in song['artists'] if artist and artist.get('name')])
                        song_widgets.append(Static(f"▶ {song['name']} - {artists}", classes="song-item"))
                    else:
                        song_widgets.append(Static("[dim]Invalid song data[/]", classes="song-item"))
                
                # Mount all at once
                if song_widgets:
                    songs_container.mount(*song_widgets)
                else:
                    songs_container.mount(Static("No valid songs found in this playlist."))
            else:
                songs_container.mount(Static("No songs found or error loading playlist."))
                
        except Exception as e:
            # Clear loading indicator
            songs_container.query_one("#songs-loading").remove()
            songs_container.mount(Static(f"[red]Error loading songs: {str(e)}[/]"))
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the dialog."""
        if event.button.id == "btn-close-dialog":
            self.dismiss()

class PlaylistItem(Container):
    """A custom widget for displaying a playlist with checkbox and view button."""
    
    def __init__(self, playlist_id, name, tracks_count, is_playlist=True, is_liked_songs=False):
        super().__init__()
        self.playlist_id = playlist_id
        self.display_name = name
        self.tracks_count = tracks_count
        self.is_playlist = is_playlist
        self.is_liked_songs = is_liked_songs
        
        # Create a unique ID based on type and playlist ID
        if is_liked_songs:
            self.item_id = "liked_songs"
            self.checkbox_id = "cb-liked-songs"
        else:
            self.item_id = f"pl-{playlist_id}" 
            self.checkbox_id = f"cb-{self.item_id}"
        
    def compose(self) -> ComposeResult:
        """Create child widgets for the playlist item."""
        self.add_class("playlist-row")  # Apply styling
        
        # Special styling for liked songs
        if self.is_liked_songs:
            self.add_class("liked-songs-row")
        
        # Create the checkbox with appropriate label
        label = f"{self.display_name} ({self.tracks_count} tracks)"
        yield Checkbox(label, id=self.checkbox_id)

        # View button for playlists (not for liked songs as they're just a flat list)
        if not self.is_liked_songs:
            yield Button("View", id=f"view-{self.playlist_id}", classes="view-btn")

class SpotifyDownloaderTUI(App):
    """A Textual app to manage Spotify playlist downloads."""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
        ("r", "refresh_data", "Refresh Data"),
        ("s", "start_download", "Start Download"),
        ("a", "select_all", "Select All Playlists"),
        ("o", "open_settings", "Settings")
    ]

    CSS_PATH = "tui.css"

    playlists = var(None)
    liked_songs = var(None)
    selected_playlists = var(set())
    selected_liked_songs = var(False)
    spotdl_settings = var(None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Button("⚙️ Settings", id="btn-settings")
        with Container(id="app-content"):
            with Container(id="link-container"):
                yield Static("Add Playlist by URL:", classes="input-label")
                with Horizontal():
                    yield Input(placeholder="Paste Spotify playlist link here...", id="playlist-link")
                    yield Button("Add", id="btn-add-playlist", variant="primary")
                
            with Horizontal(id="main-panes"):
                with VerticalScroll(id="selection-pane"):
                    # Add section with "Select All" button and Liked Songs button
                    with Horizontal(id="playlist-controls"):
                        yield Button("Select All Playlists", id="btn-select-all", variant="default")
                    
                    yield Static("Playlists", classes="pane-title")
                    yield Container(id="playlist-list")
                    
                    # Liked Songs section with its own title
                    yield Static("Liked Songs", classes="pane-title")
                    yield Container(id="liked-songs-container")
                
                with VerticalScroll(id="log-pane"):
                     yield Static("Logs / Status", classes="pane-title")
                     yield Log(id="log", auto_scroll=True)
                 
            with Container(id="controls-pane"):
                 yield Button("Refresh Data", id="btn-refresh", variant="primary")
                 yield Button("Start Download", id="btn-download", variant="success", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.query_one(Log).write_line("App started. Press 'R' to refresh data.")
        # Load spotdl settings
        self.load_spotdl_settings()
        asyncio.create_task(self.action_refresh_data())

    def load_spotdl_settings(self):
        """Load spotdl settings from file."""
        settings_file = os.path.join("config", "spotdl_settings.json")
        default_settings = {
            "format": "mp3",
            "bitrate": "auto",
            "output": "{title}.{output-ext}",
            "lyrics": "genius",
            "audio": "youtube",
            "generate_lrc": False,
            "sponsor_block": False,
            "playlist_numbering": False
        }
        
        try:
            if os.path.exists(settings_file):
                with open(settings_file, "r") as f:
                    self.spotdl_settings = json.load(f)
            else:
                self.spotdl_settings = default_settings
        except Exception:
            self.spotdl_settings = default_settings

    async def action_open_settings(self) -> None:
        """Open the settings modal."""
        settings_screen = SpotdlSettingsModal(initial_settings=self.spotdl_settings)
        result = await self.push_screen(settings_screen)
        if result:
            self.spotdl_settings = result
            self.query_one(Log).write_line("Settings updated.")

    async def action_refresh_data(self) -> None:
        """Fetch playlists and liked songs from Spotify using API calls."""
        log = self.query_one(Log)
        log.write_line("Fetching data from Spotify...")
        self.query_one("#btn-refresh").disabled = True
        
        # Clear the selection containers
        playlist_container = self.query_one("#playlist-list")
        liked_songs_container = self.query_one("#liked-songs-container")
        playlist_container.remove_children()
        liked_songs_container.remove_children()
        
        # Add loading indicators
        playlist_container.mount(Static("Loading playlists...", id="playlist-loading"))
        liked_songs_container.mount(Static("Loading liked songs...", id="liked-loading"))
        
        try:
            # Fetch playlist and liked songs data
            self.playlists = await asyncio.to_thread(get_user_playlists)
            self.liked_songs = await asyncio.to_thread(get_user_liked_tracks)
            
            if self.playlists is None:
                log.write_line("[bold red]Error fetching playlists from Spotify API.[/]")
            else:
                log.write_line("Data fetched successfully.")
                
            # Update containers with the fetched data
            await self.populate_playlist_container()
            await self.populate_liked_songs_container()
            
        except Exception as e:
            log.write_line(f"[bold red]Error during data refresh: {e}[/]")
            # Create empty data structures if needed
            if self.playlists is None: self.playlists = {'items': []}
            if self.liked_songs is None: self.liked_songs = {'items': []}
            
            # Update containers with empty data
            await self.populate_playlist_container()
            await self.populate_liked_songs_container()
        finally:
            self.query_one("#btn-refresh").disabled = False

    async def populate_playlist_container(self):
        """Populate the playlist container with the fetched playlists."""
        playlist_container = self.query_one("#playlist-list")
        playlist_container.remove_children()  # Clear previous content
        
        if not self.playlists or not isinstance(self.playlists.get('items'), list) or not self.playlists.get('items'):
            playlist_container.mount(Static("[i]No playlists found.[/]"))
            return
        
        # Create a list of playlists to mount
        items = []
        for playlist in self.playlists['items']:
            if not playlist or 'id' not in playlist or 'name' not in playlist:
                continue
                
            tracks_count = playlist.get('tracks', {}).get('total', 0)
            item = PlaylistItem(
                playlist_id=playlist['id'],
                name=playlist['name'],
                tracks_count=tracks_count,
                is_playlist=True
            )
            items.append(item)
        
        # Mount all items at once if any
        if items:
            playlist_container.mount(*items)
        else:
            playlist_container.mount(Static("[i]No valid playlists found.[/]"))
            
    async def populate_liked_songs_container(self):
        """Populate the liked songs container with the liked songs info."""
        liked_container = self.query_one("#liked-songs-container")
        liked_container.remove_children()  # Clear previous content
        
        if not self.liked_songs or not self.liked_songs.get('items'):
            liked_container.mount(Static("[i]No liked songs found.[/]"))
            return
        
        # Create the liked songs entry with additional styling and info
        tracks_count = len(self.liked_songs['items'])
        item = PlaylistItem(
            playlist_id='liked_songs',
            name='Liked Songs',
            tracks_count=tracks_count,
            is_playlist=False,
            is_liked_songs=True
        )
        
        liked_container.mount(item)
        
        # Display a message indicating how many liked songs were found
        if tracks_count > 0:
            self.query_one(Log).write_line(f"Found {tracks_count} liked tracks.")

    async def action_start_download(self) -> None:
        """Start the download process for selected items."""
        log = self.query_one(Log)
        if not self.selected_playlists and not self.selected_liked_songs:
            log.write_line("[yellow]No playlists or liked songs selected for download.[/]")
            return

        # Disable buttons during download
        self.query_one("#btn-download").disabled = True
        self.query_one("#btn-refresh").disabled = True
        log.write_line("-" * 30) # Separator
        
        # Count how many items we're downloading
        playlist_count = len(self.selected_playlists)
        liked_count = len(self.liked_songs.get('items', [])) if self.selected_liked_songs else 0
        
        liked_msg = f" + {liked_count} Liked Songs" if self.selected_liked_songs else ""
        log.write_line(f"Starting download for {playlist_count} playlists{liked_msg}...")

        # --- Gather selected objects ---
        selected_playlist_objects = []
        if self.playlists and isinstance(self.playlists.get('items'), list):
            selected_playlist_objects = [
                pl for pl in self.playlists['items'] if pl and pl.get('id') in self.selected_playlists
            ]

        liked_songs_object = None
        if self.selected_liked_songs and self.liked_songs:
            liked_songs_object = self.liked_songs
        # --- End Gather ---

        try:
            # Run the blocking download process in a separate thread
            await asyncio.to_thread(
                process_downloads,
                selected_playlist_objects,
                liked_songs_object,
                log_callback=log.write_line
            )
        except Exception as e:
            log.write_line(f"[bold red]An unexpected error occurred during the download process: {e}[/]")
            log.write_line("[bold red]Download process failed.[/]")
        finally:
            # Re-enable buttons
            self.query_one("#btn-download").disabled = False
            self.query_one("#btn-refresh").disabled = False
            log.write_line("-" * 30) # Separator

    async def action_select_all(self) -> None:
        """Select all playlists in the list."""
        log = self.query_one(Log)
        log.write_line("Selecting all playlists...")
        
        # Find all playlist checkboxes (excluding liked songs)
        playlist_container = self.query_one("#playlist-list")
        checkboxes = playlist_container.query(Checkbox)
        
        # Check all checkboxes
        for checkbox in checkboxes:
            if not checkbox.value:
                checkbox.value = True
        
        log.write_line(f"Selected {len(checkboxes)} playlists.")

    async def add_playlist_from_link(self, link_text):
        """Add a playlist from a Spotify link using API call."""
        log = self.query_one(Log)
        playlist_id = None
        playlist_patterns = [
            r'spotify:playlist:([a-zA-Z0-9]+)',
            r'open\.spotify\.com/playlist/([a-zA-Z0-9]+)',
        ]
        
        for pattern in playlist_patterns:
            match = re.search(pattern, link_text)
            if match:
                playlist_id = match.group(1)
                break
        
        if not playlist_id:
            log.write_line("[red]Invalid Spotify playlist link format.[/]")
            return

        log.write_line(f"Fetching details for playlist ID: {playlist_id}")

        try:
            playlist_info = await asyncio.to_thread(get_playlist_by_id, playlist_id)

            if not playlist_info:
                log.write_line(f"[red]Could not fetch details for playlist {playlist_id}.[/]")
                return

            if not self.playlists or not isinstance(self.playlists.get('items'), list):
                self.playlists = {'items': []}

            exists = any(p['id'] == playlist_id for p in self.playlists['items'])
            if not exists:
                self.playlists['items'].append(playlist_info)
                log.write_line(f"[green]Added playlist: {playlist_info['name']}[/]")
                
                # Update just the playlist container 
                await self.populate_playlist_container()
            else:
                log.write_line("[yellow]Playlist already in your list.[/]")

        except Exception as e:
            log.write_line(f"[bold red]Error adding playlist from link: {e}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-refresh":
            asyncio.create_task(self.action_refresh_data())
        elif button_id == "btn-download":
            self.run_action("start_download")
        elif button_id == "btn-add-playlist":
            link_input = self.query_one("#playlist-link")
            if link_input.value:
                asyncio.create_task(self.add_playlist_from_link(link_input.value))
                link_input.value = ""
        elif button_id == "btn-select-all":
            self.run_action("select_all")
        elif button_id == "btn-settings":
            self.run_action("open_settings")
        elif button_id and button_id.startswith("view-"):
            playlist_id = button_id[5:]  # Remove "view-" prefix
            playlist_items = self.playlists.get('items', []) if self.playlists else []
            for playlist in playlist_items:
                if playlist['id'] == playlist_id:
                    self.app.push_screen(PlaylistSongsModal(playlist_id, playlist['name']))
                    break

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes to update selected sets."""
        checkbox_id = event.checkbox.id
        is_selected = event.value
        
        if checkbox_id and checkbox_id.startswith("cb-"):
            # Check if this is the liked songs checkbox
            if checkbox_id == "cb-liked-songs":
                self.selected_liked_songs = is_selected
            # Otherwise it's a regular playlist
            elif "cb-pl-" in checkbox_id:
                item_id = checkbox_id[6:]  # Remove "cb-pl-" prefix
                if is_selected:
                    self.selected_playlists.add(item_id)
                else:
                    self.selected_playlists.discard(item_id)
        
        # Update download button state
        can_download = bool(self.selected_playlists or self.selected_liked_songs)
        self.query_one("#btn-download").disabled = not can_download

if __name__ == "__main__":
    app = SpotifyDownloaderTUI()
    app.run()
