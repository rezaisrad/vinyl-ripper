"""CLI commands for the vinyl ripper application."""

from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console

from ..recording.services import AudioRecorder
from ..recording.models import RecordingConfig
from ..core.config import AppInfo, AudioConfig, BitDepth, OutputFormat
from .display import AudioDisplay, ProgressTracker, InteractivePrompts
from ..core.exceptions import (
    VinylRipperError,
    AudioDeviceError,
    RecordingError,
)
from ..metadata.services import DiscogsService, DiscogsServiceError
from ..storage.services import FileManager
from ..processing.services import AudioProcessor
from ..processing.models import Track
from ..core.exceptions import ProcessingError

# Initialize Rich console and Typer app
console = Console()
app = typer.Typer(
    name=AppInfo.NAME,
    help=AppInfo.DESCRIPTION,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Initialize display components
display = AudioDisplay(console)
progress = ProgressTracker(console)
prompts = InteractivePrompts(console)


def handle_error(error: Exception) -> None:
    """Centralized error handling."""
    if isinstance(error, VinylRipperError):
        display.show_error_message(str(error))
        if hasattr(error, "details") and error.details:
            console.print(f"[dim]Details: {error.details}[/dim]")
    else:
        display.show_error_message(f"Unexpected error: {str(error)}")

    raise typer.Exit(1)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory for files"
    ),
):
    """Professional vinyl ripping and audio processing tool."""
    # Store global configuration in context
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["output_dir"] = output_dir

    # Show app header only for non-help commands
    if ctx.invoked_subcommand and ctx.invoked_subcommand != "--help":
        display.show_app_header()


@app.command()
def devices():
    """List all available audio input devices."""
    try:
        recorder = AudioRecorder()
        audio_devices = recorder.discover_devices()
        display.show_devices_table(audio_devices)

    except AudioDeviceError as e:
        handle_error(e)


@app.command("arm-record")
def arm_record(
    device_id: Optional[int] = typer.Option(
        None, "--device", "-d", help="Audio input device ID"
    ),
    sample_rate: int = typer.Option(
        AudioConfig.DEFAULT_SAMPLE_RATE, "--sample-rate", "-s", help="Sample rate in Hz"
    ),
    channels: int = typer.Option(
        AudioConfig.DEFAULT_CHANNELS, "--channels", "-c", help="Number of channels"
    ),
    bit_depth: int = typer.Option(
        AudioConfig.DEFAULT_BIT_DEPTH,
        "--bit-depth",
        "-b",
        help="Bit depth (16, 24, 32)",
    ),
    output_format: str = typer.Option(
        "wav", "--format", "-f", help="Output format (wav, flac, aiff)"
    ),
    threshold_db: float = typer.Option(
        AudioConfig.ARM_GAIN_DB,
        "--threshold",
        "-t",
        help="dB threshold to start recording",
    ),
    buffer_size: Optional[int] = typer.Option(
        None, "--buffer", help="Audio buffer size"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output filename"
    ),
):
    """Record audio with armed mode - starts automatically when signal exceeds threshold."""
    try:
        # Convert string format to enum
        try:
            format_enum = OutputFormat(output_format.lower())
        except ValueError:
            display.show_error_message(f"Unsupported format: {output_format}")
            raise typer.Exit(1)

        # Convert bit depth to enum
        try:
            if bit_depth == 16:
                depth_enum = BitDepth.BIT_16
            elif bit_depth == 24:
                depth_enum = BitDepth.BIT_24
            elif bit_depth == 32:
                depth_enum = BitDepth.BIT_32_FLOAT
            else:
                raise ValueError(f"Unsupported bit depth: {bit_depth}")
        except ValueError as e:
            display.show_error_message(str(e))
            raise typer.Exit(1)

        # Create recording configuration
        config = RecordingConfig(
            device_id=device_id,
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=depth_enum,
            output_format=format_enum,
            buffer_size=buffer_size,
            armed=True,
            arm_threshold_db=threshold_db,
        )

        # Initialize recorder
        recorder = AudioRecorder()

        # Show configuration
        display.show_armed_config(
            device_id=device_id,
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=bit_depth,
            output_format=output_format,
            threshold_db=threshold_db,
            buffer_size=buffer_size,
        )

        # Show armed status
        display.show_armed_status(threshold_db)

        # Start armed recording
        audio_data = recorder.record_with_arm(config)

        # Show completion
        duration = len(audio_data) / sample_rate
        display.show_success_message(
            f"Recording complete! Duration: {duration:.1f} seconds"
        )

        # Save file if output specified
        if output_file:
            # TODO: Implement file saving with StorageService
            display.show_info_message(f"Audio data ready to save to: {output_file}")
        else:
            display.show_info_message(
                "Audio data captured successfully (use --output to save)"
            )

    except (AudioDeviceError, RecordingError) as e:
        handle_error(e)


@app.command()
def split(
    audio_file: Path = typer.Argument(help="Audio file to split into tracks"),
    release_id: Optional[int] = typer.Option(
        None, "--release-id", "-r", help="Discogs release ID for metadata"
    ),
    preview: bool = typer.Option(
        False, "--preview", "-p", help="Preview detected tracks without splitting"
    ),
    output_format: str = typer.Option(
        "wav", "--format", "-f", help="Output format (wav, flac, aiff)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory"
    ),
):
    """Split vinyl recording into individual track files with smart gap detection."""
    try:
        # Validate audio file
        if not audio_file.exists():
            display.show_error_message(f"Audio file not found: {audio_file}")
            raise typer.Exit(1)

        # Convert string format to enum
        try:
            format_enum = OutputFormat(output_format.lower())
        except ValueError:
            display.show_error_message(f"Unsupported format: {output_format}")
            raise typer.Exit(1)

        # Initialize services
        processor = AudioProcessor()
        file_manager = FileManager(output_dir)

        console.print(f"[blue]Analyzing audio file: {audio_file.name}[/blue]")

        # Detect tracks using smart vinyl detection
        with progress.processing_progress("Detecting track boundaries...") as (
            prog,
            task,
        ):
            tracks = processor.detect_vinyl_tracks(audio_file)

        if not tracks:
            console.print("[yellow]No tracks detected in the audio file.[/yellow]")
            return

        # Show detected track structure
        _show_track_preview(tracks)

        # If preview mode, stop here
        if preview:
            return

        # Get metadata if release ID provided
        album_metadata = None
        track_titles = None
        if release_id:
            try:
                discogs = DiscogsService()
                console.print(
                    f"[blue]Fetching metadata for release ID: {release_id}[/blue]"
                )

                with progress.processing_progress("Fetching release metadata...") as (
                    prog,
                    task,
                ):
                    album_metadata, discogs_tracks = discogs.get_release_metadata(
                        release_id
                    )

                # Extract track titles
                track_titles = (
                    [track.title for track in discogs_tracks]
                    if discogs_tracks
                    else None
                )

                console.print(
                    f"[green]✓[/green] Fetched metadata: {album_metadata.artist} - {album_metadata.album}"
                )

            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not fetch metadata: {e}[/yellow]"
                )
                console.print("[yellow]Proceeding with generic track names...[/yellow]")

        # Confirm splitting
        if not prompts.confirm(
            f"Split {len(tracks)} tracks to {format_enum.value.upper()} files?"
        ):
            return

        # Split tracks
        console.print(f"[blue]Splitting into {len(tracks)} track files...[/blue]")

        with progress.processing_progress("Splitting tracks...") as (prog, task):
            track_files = file_manager.split_vinyl_tracks(
                audio_file=audio_file,
                tracks=tracks,
                album_metadata=album_metadata,
                track_titles=track_titles,
                output_format=format_enum,
                output_dir=output_dir,
            )

        # Add metadata to files if available
        if album_metadata and track_files:
            console.print("[blue]Adding metadata to track files...[/blue]")

            with progress.processing_progress("Tagging files...") as (prog, task):
                file_manager.batch_add_metadata(
                    track_files, album_metadata, track_titles
                )

        # Show results
        console.print(
            f"[green]✓ Successfully split into {len(track_files)} track files[/green]"
        )

        if track_files:
            output_path = track_files[0].file_path.parent
            console.print(f"[green]Files saved to: {output_path}[/green]")

    except (ProcessingError, DiscogsServiceError) as e:
        handle_error(e)


def _show_track_preview(tracks: List[Track]) -> None:
    """Display preview of detected tracks."""
    from rich.table import Table

    table = Table(title="Detected Track Structure")
    table.add_column("Track", justify="center", style="cyan")
    table.add_column("Side", justify="center", style="magenta")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Start Time", justify="right", style="blue")

    for track in tracks:
        start_min = int(track.start_time // 60)
        start_sec = int(track.start_time % 60)

        table.add_row(
            str(track.number),
            track.side,
            track.duration_str,
            f"{start_min}:{start_sec:02d}",
        )

    console.print(table)

    # Show side summary
    sides = {}
    for track in tracks:
        if track.side not in sides:
            sides[track.side] = []
        sides[track.side].append(track)

    console.print(
        f"\n[green]Detected {len(sides)} side(s) with {len(tracks)} total tracks[/green]"
    )
    for side, side_tracks in sides.items():
        console.print(f"  Side {side}: {len(side_tracks)} tracks")


# Create metadata command group
metadata_app = typer.Typer(help="Fetch metadata from Discogs API")
app.add_typer(metadata_app, name="metadata")


@metadata_app.command("search")
def metadata_search(
    query: str = typer.Argument(help="Search query for releases"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of results"),
    tag_files: bool = typer.Option(
        False, "--tag-files", help="Tag files after selecting release"
    ),
    file_pattern: Optional[str] = typer.Option(
        None, "--files", help="File pattern to tag (e.g., '*.flac')"
    ),
):
    """Search for releases on Discogs and optionally tag audio files."""
    try:
        # Initialize services
        discogs = DiscogsService()
        file_manager = FileManager()

        console.print(f"[blue]Searching Discogs for: '{query}'[/blue]")

        with progress.processing_progress("Searching Discogs...") as (prog, task):
            results = discogs.search_releases(query, limit=limit)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        # Display results for selection
        display.show_search_results(results)

        # Get user selection
        try:
            selection = prompts.get_number_input(
                f"Select release (1-{len(results)})", min_val=1, max_val=len(results)
            )
            selected_release = results[selection - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")
            return

        # Get full metadata
        console.print(
            f"[blue]Fetching metadata for: {selected_release['artist']} - {selected_release['title']}[/blue]"
        )

        with progress.processing_progress("Fetching release metadata...") as (
            prog,
            task,
        ):
            metadata, tracks = discogs.get_release_metadata(selected_release["id"])

        # Display detailed metadata
        display.show_release_details(metadata, tracks)

        # Tag files if requested
        if tag_files:
            _tag_files_workflow(file_manager, metadata, tracks, file_pattern)

    except DiscogsServiceError as e:
        handle_error(e)


@metadata_app.command("from-id")
def metadata_from_id(
    release_id: int = typer.Argument(help="Discogs release ID"),
    tag_files: bool = typer.Option(
        False, "--tag-files", help="Tag files after fetching metadata"
    ),
    file_pattern: Optional[str] = typer.Option(
        None, "--files", help="File pattern to tag (e.g., '*.flac')"
    ),
):
    """Get metadata by Discogs release ID and optionally tag audio files."""
    try:
        # Initialize services
        discogs = DiscogsService()
        file_manager = FileManager()

        console.print(f"[blue]Fetching metadata for release ID: {release_id}[/blue]")

        with progress.processing_progress("Fetching release metadata...") as (
            prog,
            task,
        ):
            metadata, tracks = discogs.get_release_metadata(release_id)

        # Display detailed metadata
        display.show_release_details(metadata, tracks)

        # Tag files if requested
        if tag_files:
            _tag_files_workflow(file_manager, metadata, tracks, file_pattern)

    except DiscogsServiceError as e:
        handle_error(e)


@metadata_app.command("from-collection")
def metadata_from_collection(
    username: Optional[str] = typer.Option(
        None,
        "--username",
        help="Discogs username (uses authenticated user if not provided)",
    ),
    limit: int = typer.Option(
        50, "--limit", "-l", help="Maximum number of items to show"
    ),
    tag_files: bool = typer.Option(
        False, "--tag-files", help="Tag files after selecting release"
    ),
    file_pattern: Optional[str] = typer.Option(
        None, "--files", help="File pattern to tag (e.g., '*.flac')"
    ),
):
    """Browse user's Discogs collection and optionally tag audio files."""
    try:
        # Initialize services
        discogs = DiscogsService()
        file_manager = FileManager()

        if not username:
            username = discogs.get_authenticated_username()

        console.print(f"[blue]Fetching collection for user: {username}[/blue]")

        with progress.processing_progress("Fetching collection...") as (prog, task):
            collection = discogs.get_user_collection(username, limit=limit)

        if not collection:
            console.print("[yellow]No items found in collection.[/yellow]")
            return

        # Display collection for selection
        display.show_collection_list(collection)

        # Get user selection
        try:
            selection = prompts.get_number_input(
                f"Select release (1-{len(collection)})",
                min_val=1,
                max_val=len(collection),
            )
            selected_item = collection[selection - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")
            return

        # Get full metadata
        console.print(
            f"[blue]Fetching metadata for: {selected_item['artist']} - {selected_item['title']}[/blue]"
        )

        with progress.processing_progress("Fetching release metadata...") as (
            prog,
            task,
        ):
            metadata, tracks = discogs.get_release_metadata(selected_item["id"])

        # Display detailed metadata
        display.show_release_details(metadata, tracks)

        # Tag files if requested
        if tag_files:
            _tag_files_workflow(file_manager, metadata, tracks, file_pattern)

    except DiscogsServiceError as e:
        handle_error(e)


@metadata_app.command("tag-files")
def tag_files_command(
    release_id: int = typer.Argument(help="Discogs release ID"),
    file_pattern: str = typer.Option("*.flac", "--files", help="File pattern to tag"),
    directory: Optional[Path] = typer.Option(
        None, "--directory", "-d", help="Directory containing audio files"
    ),
):
    """Tag audio files with metadata from a specific Discogs release."""
    try:
        # Initialize services
        discogs = DiscogsService()
        file_manager = FileManager()

        # Use current directory if not specified
        if not directory:
            directory = Path.cwd()

        console.print(f"[blue]Fetching metadata for release ID: {release_id}[/blue]")

        with progress.processing_progress("Fetching release metadata...") as (
            prog,
            task,
        ):
            metadata, tracks = discogs.get_release_metadata(release_id)

        _tag_files_workflow(file_manager, metadata, tracks, file_pattern, directory)

    except DiscogsServiceError as e:
        handle_error(e)


def _tag_files_workflow(
    file_manager: FileManager,
    metadata,
    tracks,
    file_pattern: Optional[str] = None,
    directory: Optional[Path] = None,
):
    """Helper function for the file tagging workflow."""
    if not directory:
        directory = Path.cwd()

    if not file_pattern:
        file_pattern = "*.flac"

    # Find audio files
    console.print(
        f"[blue]Looking for files matching '{file_pattern}' in {directory}[/blue]"
    )
    audio_files = list(directory.glob(file_pattern))

    if not audio_files:
        console.print(
            f"[yellow]No files found matching pattern '{file_pattern}'[/yellow]"
        )
        return

    console.print(f"[green]Found {len(audio_files)} files[/green]")

    # Check if track count matches
    if len(audio_files) != len(tracks):
        console.print(
            f"[yellow]Warning: Found {len(audio_files)} files but release has {len(tracks)} tracks[/yellow]"
        )
        if not prompts.confirm("Continue anyway?"):
            return

    # Confirm tagging
    if not prompts.confirm(
        f"Tag {len(audio_files)} files with metadata from '{metadata.artist} - {metadata.album}'?"
    ):
        return

    # Tag files
    with progress.processing_progress("Tagging files...") as (prog, task):
        for i, file_path in enumerate(sorted(audio_files)):
            track_number = i + 1
            track_title = (
                tracks[i].title if i < len(tracks) else f"Track {track_number}"
            )

            try:
                file_manager.add_metadata(
                    file_path,
                    metadata,
                    track_title=track_title,
                    track_number=track_number,
                )
                console.print(f"[green]✓[/green] Tagged: {file_path.name}")
            except Exception as e:
                console.print(f"[red]✗[/red] Failed to tag {file_path.name}: {e}")

    console.print("[green]File tagging complete![/green]")
