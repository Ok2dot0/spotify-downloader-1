"""Enhanced methods for spotify_burner.py"""

def enhanced_search_music(self, query):
    """Search for music on Spotify.
    
    Args:
        query: Search query string
        
    Returns:
        dict: Selected item data or None if cancelled
    """
    import os
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich import box
    
    console.clear()
    self.show_header()
    
    # Create a title with themed styling
    title_text = "[bold cyan]SPOTIFY SEARCH[/bold cyan]"
    console.print(self.center_text(title_text))
    console.print(self.center_text(f"[{{app_state['theme']['border']}]{'═' * 60}[/{{app_state['theme']['border']}]]"))
    console.print("")
    
    # Create a search query panel
    query_panel = Panel(
        f"[yellow]Searching for:[/yellow] [bold white]{query}[/bold white]",
        title="Search Query",
        title_align="left",
        border_style="cyan",
        box=app_state["theme"]["box"],
        expand=False
    )
    console.print(self.center_text(query_panel))
    console.print("")
    
    if not self.spotify:
        if not self.initialize_spotify():
            error_panel = Panel(
                "[bold red]Failed to initialize Spotify API connection.[/bold red]\n"
                "[yellow]Please check your internet connection and API credentials.[/yellow]",
                title="Connection Error",
                border_style="red",
                box=app_state["theme"]["box"],
                expand=False
            )
            console.print(self.center_text(error_panel))
            return None
    
    try:
        # Display searching progress with a custom spinner
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[cyan]Searching Spotify...[/cyan]"),
            BarColumn(bar_width=40, complete_style="green", finished_style="green"),
            TextColumn("[yellow]Please wait[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("search", total=100)
            
            # Update progress while searching
            progress.update(task, advance=30)
            track_results = self.spotify.search(query, limit=5, type='track')
            progress.update(task, advance=35)
            album_results = self.spotify.search(query, limit=5, type='album')
            progress.update(task, advance=35)
            
        # Process results
        tracks = track_results.get('tracks', {}).get('items', [])
        albums = album_results.get('albums', {}).get('items', [])
        
        if not tracks and not albums:
            # No results panel with suggestions
            no_results_panel = Panel(
                "[bold yellow]No results found for your search.[/bold yellow]\n\n"
                "[white]Suggestions:[/white]\n"
                "• Check for spelling mistakes\n"
                "• Try using fewer or different keywords\n"
                "• Try searching by artist name or album title only",
                title="No Results",
                border_style="yellow",
                box=app_state["theme"]["box"],
                expand=False
            )
            console.print(self.center_text(no_results_panel))
            return None
            
        # Create results table with alternating row styles
        table = Table(
            title="Search Results", 
            box=app_state["theme"]["box"], 
            title_style="bold cyan",
            header_style="bold",
            border_style=app_state["theme"]["border"],
            row_styles=["", "dim"],
            highlight=True,
            width=90,
            expand=False
        )
        
        table.add_column("#", style="cyan", justify="right", width=3)
        table.add_column("Type", style="green", width=10)
        table.add_column("Title", style="white")
        table.add_column("Artist", style="yellow")
        table.add_column("Duration/Tracks", style="magenta", justify="right", width=15)
        
        # Add tracks to table with icons
        result_items = []
        idx = 1
        
        # Add tracks with 🎵 icon
        for track in tracks[:5]:
            duration_ms = track.get('duration_ms', 0)
            duration_str = self.format_duration(duration_ms)
            artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
            
            table.add_row(
                str(idx),
                "🎵 Track",
                track.get('name', 'Unknown'),
                artists,
                duration_str
            )
            result_items.append({"type": "track", "item": track})
            idx += 1
            
        # Add albums with 💿 icon
        for album in albums[:5]:
            album_type = album.get('album_type', 'Album').capitalize()
            artists = ", ".join([artist['name'] for artist in album.get('artists', [])])
            total_tracks = album.get('total_tracks', 0)
            
            table.add_row(
                str(idx),
                f"💿 {album_type}",
                album.get('name', 'Unknown'),
                artists,
                f"{total_tracks} tracks"
            )
            result_items.append({"type": "album", "item": album})
            idx += 1
            
        # Wrap results table in a panel
        results_panel = Panel(
            table,
            border_style=app_state["theme"]["border"],
            box=app_state["theme"]["box"],
            padding=(1, 2),
            expand=False
        )
        console.print(self.center_text(results_panel))
        console.print("")
        
        # Instructions panel for selection
        instruction_panel = Panel(
            "Select a number to view details, or [bold]C[/bold] to cancel and return to menu",
            border_style="blue",
            box=box.ROUNDED,
            expand=False
        )
        console.print(self.center_text(instruction_panel))
        
        # Center the prompt and make it more visible
        console.print("")
        console.print(self.center_text("[white]Your selection:[/white]"))
        
        # Centralize the input prompt
        selection = Prompt.ask(
            self.center_text(""),
            choices=[str(i) for i in range(1, len(result_items) + 1)] + ["C", "c"],
            default="1"
        )
        
        if selection.upper() == "C":
            return None
            
        selected_idx = int(selection) - 1
        return result_items[selected_idx]
        
    except Exception as e:
        logger.error(f"Error searching music: {e}")
        error_panel = Panel(
            f"[bold red]Error while searching:[/bold red]\n[white]{str(e)}[/white]",
            title="Search Error",
            border_style="red",
            box=app_state["theme"]["box"],
            expand=False
        )
        console.print(self.center_text(error_panel))
        return None

def enhanced_metadata(self, selection, output_dir):
    """Enhance metadata of downloaded files.
    
    Args:
        selection: Selected music item data
        output_dir: Output directory with downloaded files
    """
    import os
    import requests
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    
    console.clear()
    self.show_header()
    
    # Create a title with themed styling
    title_text = "[bold green]METADATA ENHANCEMENT[/bold green]"
    console.print(self.center_text(title_text))
    console.print(self.center_text(f"[{{app_state['theme']['border']}]{'═' * 60}[/{{app_state['theme']['border']}]]"))
    console.print("")
    
    if not self.metadata_settings.get("overwrite_metadata", True):
        # Show skipped panel when metadata enhancement is disabled
        skipped_panel = Panel(
            "[yellow]Metadata enhancement has been disabled in settings.[/yellow]\n"
            "[white]You can enable it in the application settings menu.[/white]",
            title="Process Skipped",
            title_align="center",
            border_style="yellow",
            box=app_state["theme"]["box"],
            expand=False,
            width=80
        )
        console.print(self.center_text(skipped_panel))
        return
        
    try:
        # Only process if directory exists
        if not os.path.exists(output_dir):
            # Show error panel for missing directory
            error_panel = Panel(
                f"[bold red]The directory does not exist:[/bold red]\n"
                f"[white]{output_dir}[/white]\n\n"
                "[yellow]Please check if the download completed successfully.[/yellow]",
                title="Directory Not Found",
                title_align="center",
                border_style="red",
                box=app_state["theme"]["box"],
                expand=False,
                width=80
            )
            console.print(self.center_text(error_panel))
            return

        # Create a progress panel showing the current operation
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold cyan]Processing metadata...[/bold cyan]"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
            transient=True
        ) as progress:
            # Add a main task
            task = progress.add_task("Processing", total=100)
            
            # Get all audio files in the directory
            progress.update(task, advance=20, description="Scanning files")
            audio_files = [f for f in os.listdir(output_dir) 
                           if f.endswith((".mp3", ".flac", ".ogg", ".m4a", ".opus", ".wav"))]
        
            # No files to process
            if not audio_files:
                empty_panel = Panel(
                    f"[bold yellow]No audio files were found in the output directory.[/bold yellow]\n\n"
                    f"[white]Directory path:[/white] [italic]{output_dir}[/italic]\n\n"
                    "[yellow]Possible causes:[/yellow]\n"
                    "• Download may have failed\n"
                    "• Files may have been moved or deleted\n"
                    "• Wrong output directory specified",
                    title="No Files Found",
                    title_align="center",
                    border_style="yellow",
                    box=app_state["theme"]["box"],
                    expand=False,
                    width=80
                )
                console.print(self.center_text(empty_panel))
                return

            # Display album info before processing
            progress.update(task, advance=10, description="Getting album info")
            album_info_panel = Panel(
                f"[cyan]Processing metadata for:[/cyan] [bold white]{os.path.basename(output_dir)}[/bold white]\n"
                f"[cyan]Files found:[/cyan] [bold white]{len(audio_files)} audio files[/bold white]\n"
                f"[cyan]Directory:[/cyan] [white]{output_dir}[/white]",
                title="Album Information",
                title_align="center",
                border_style=app_state["theme"]["border"],
                box=app_state["theme"]["box"],
                expand=False,
                width=80
            )
            console.print(self.center_text(album_info_panel))
            console.print("")
            
            # Create a status table for metadata operations with improved styling
            progress.update(task, advance=20, description="Setting up metadata operations")
            status_table = Table(
                box=app_state["theme"]["box"],
                border_style=app_state["theme"]["border"],
                title="Metadata Operations",
                title_style="bold green",
                header_style="bold",
                row_styles=["dim", ""],
                highlight=True,
                expand=False,
                width=80
            )
            status_table.add_column("🔧 Operation", style="cyan")
            status_table.add_column("📊 Status", style="green", justify="center")
            status_table.add_column("📝 Details", style="white")
        
            # Process album art with enhanced visuals
            progress.update(task, advance=20, description="Processing album artwork")
            art_status = "✅ Success"
            art_details = "Album artwork saved as folder.jpg"
            
            if self.metadata_settings.get("save_album_art", True):
                # Try to download album art if it's an album
                if selection["type"] == "album":
                    album_images = selection["item"].get("images", [])
                    if album_images:
                        # Get the highest quality image
                        album_art_url = album_images[0].get("url")
                        if album_art_url:
                            # Download and save album art
                            try:
                                art_path = os.path.join(output_dir, "folder.jpg")
                                response = requests.get(album_art_url)
                                if response.status_code == 200:
                                    with open(art_path, 'wb') as f:
                                        f.write(response.content)
                                else:
                                    art_status = "❌ Failed"
                                    art_details = f"Server returned status {response.status_code}"
                            except Exception as e:
                                art_status = "❌ Failed"
                                art_details = f"Error: {str(e)}"
                        else:
                            art_status = "ℹ️ Skipped"
                            art_details = "No album art URL found"
                    else:
                        art_status = "ℹ️ Skipped"
                        art_details = "No album images available"
                else:
                    art_status = "ℹ️ Skipped"
                    art_details = "Not an album download"
            else:
                art_status = "ℹ️ Disabled"
                art_details = "Album art saving is disabled in settings"
                
            status_table.add_row("Album Artwork", art_status, art_details)
            
            # Handle lyrics embedding with enhanced visuals
            progress.update(task, advance=15, description="Processing lyrics")
            lyrics_status = "ℹ️ Skipped"
            lyrics_details = "Lyrics embedding is not yet implemented"
            
            if self.metadata_settings.get("embed_lyrics", False):
                status_table.add_row("Lyrics Embedding", lyrics_status, lyrics_details)

            # Handle file count information with enhanced visuals
            progress.update(task, advance=15, description="Validating files")
            file_status = "✅ Success"
            file_details = f"Found {len(audio_files)} audio files in {os.path.basename(output_dir)}"
            status_table.add_row("File Validation", file_status, file_details)

            # Complete progress
            progress.update(task, completed=100, description="Completed")

            # Create a panel containing the status table with enhanced styling
            status_panel = Panel(
                status_table,
                title="Metadata Operations Summary",
                title_align="center",
                title_style="bold green",
                border_style=app_state["theme"]["border"],
                box=app_state["theme"]["box"],
                padding=(1, 2),
                expand=False,
                width=80
            )
            console.print("")
            console.print(self.center_text(status_panel))
            
            # Summary panel with enhanced visuals
            console.print("")
            completion_message = (
                "[bold green]✅ Metadata enhancement completed successfully![/bold green]\n\n"
                f"[cyan]Album:[/cyan] [white]{os.path.basename(output_dir)}[/white]\n"
                f"[cyan]Directory:[/cyan] [white]{output_dir}[/white]"
            )
            summary_panel = Panel(
                completion_message,
                title="Process Complete",
                title_align="center",
                border_style="green",
                box=box.ROUNDED,
                expand=False,
                width=80
            )
            console.print(self.center_text(summary_panel))
            
    except Exception as e:
        logger.error(f"Error enhancing metadata: {e}")
        error_panel = Panel(
            f"[bold red]Error occurred while enhancing metadata:[/bold red]\n\n"
            f"[white]{str(e)}[/white]",
            title="Error",
            title_align="center",
            border_style="red",
            box=app_state["theme"]["box"],
            expand=False,
            width=80
        )
        console.print(self.center_text(error_panel))
