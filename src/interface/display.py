"""Rich console display components for the vinyl ripper application."""

from contextlib import contextmanager
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.text import Text
from rich.align import Align

from ..recording.models import AudioDevice
from ..processing.models import AudioQuality, Track
from ..storage.models import TrackFile, ProcessingResult
from ..metadata.models import AlbumMetadata, DiscogsTrack
from ..core.config import AppInfo


class AudioDisplay:
    """Handles all rich console output for audio operations."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize with optional console instance."""
        self.console = console or Console()

    def show_app_header(self) -> None:
        """Display application header with branding."""
        header_text = Text()
        header_text.append(AppInfo.NAME.upper(), style="bold blue")
        header_text.append(f" v{AppInfo.VERSION}", style="dim")
        header_text.append(f"\n{AppInfo.DESCRIPTION}", style="italic")

        panel = Panel(Align.center(header_text), border_style="blue", padding=(1, 2))
        self.console.print(panel)

    def show_devices_table(self, devices: List[AudioDevice]) -> None:
        """Display available audio devices in a formatted table."""
        table = Table(title="Available Audio Input Devices")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Device Name", style="magenta")
        table.add_column("Channels", justify="right", style="green")
        table.add_column("Default Rate", justify="right", style="yellow")
        table.add_column("Supported Rates", style="dim")
        table.add_column("Bit Depths", style="dim")

        for device in devices:
            # Format supported sample rates
            supported_rates = ""
            if device.supported_sample_rates:
                rates_khz = [
                    f"{rate // 1000}k" if rate >= 1000 else f"{rate}"
                    for rate in device.supported_sample_rates
                ]
                supported_rates = ", ".join(rates_khz)
            else:
                supported_rates = "Unknown"

            # Format supported bit depths
            supported_depths = ""
            if device.supported_bit_depths:
                depths = [f"{depth}b" for depth in device.supported_bit_depths]
                supported_depths = ", ".join(depths)
            else:
                supported_depths = "Unknown"

            table.add_row(
                str(device.id),
                device.name,
                str(device.max_channels),
                f"{device.sample_rate:.0f} Hz",
                supported_rates,
                supported_depths,
            )

        self.console.print(table)

        if devices:
            self.console.print(
                f"\n[green]Found {len(devices)} audio input device(s)[/green]"
            )
        else:
            self.console.print("[red]No audio input devices found![/red]")

    def show_recording_config(
        self,
        device_id: Optional[int],
        sample_rate: int,
        channels: int,
        duration: Optional[int] = None,
        bit_depth: Optional[int] = None,
        output_format: Optional[str] = None,
        buffer_size: Optional[int] = None,
    ) -> None:
        """Display recording configuration."""
        config_lines = []

        if device_id is not None:
            config_lines.append(f"Device: {device_id}")

        config_lines.append(f"Sample Rate: {sample_rate}Hz")
        config_lines.append(f"Channels: {channels}")

        if bit_depth is not None:
            depth_str = f"{bit_depth}-bit"
            if bit_depth == 32:
                depth_str += " float"
            config_lines.append(f"Bit Depth: {depth_str}")

        if output_format is not None:
            config_lines.append(f"Format: {output_format.upper()}")

        if duration is not None:
            config_lines.append(f"Duration: {duration}s")

        if buffer_size is not None:
            config_lines.append(f"Buffer: {buffer_size}")

        config_text = " | ".join(config_lines)
        panel = Panel.fit(
            f"[bold blue]Recording Configuration[/bold blue]\n{config_text}",
            border_style="blue",
        )
        self.console.print(panel)

    def show_quality_report(
        self, quality: AudioQuality, filename: Optional[str] = None
    ) -> None:
        """Display audio quality report."""
        title = "Audio Quality Report"
        if filename:
            title += f": {filename}"

        table = Table(title=title)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_column("Assessment", style="yellow")

        # Basic info
        table.add_row("Duration", f"{quality.duration_seconds:.1f} seconds", "")
        table.add_row("Sample Rate", f"{quality.sample_rate} Hz", "")

        # Quality metrics with assessments
        table.add_row("Peak Level", f"{quality.peak_db} dBFS", quality.peak_assessment)
        table.add_row("RMS Level", f"{quality.rms_db} dBFS", "")
        table.add_row(
            "Dynamic Range",
            f"{quality.dynamic_range} dB",
            quality.dynamic_range_assessment,
        )
        table.add_row("Loudness", f"{quality.loudness_lufs} LUFS", "")
        table.add_row(
            "Clipping", f"{quality.clipping_percent}%", quality.clipping_assessment
        )

        self.console.print(table)

    def show_tracks_table(self, tracks: List[Track]) -> None:
        """Display detected tracks in a formatted table."""
        table = Table(title="Detected Tracks")
        table.add_column("Track", justify="right", style="cyan")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Start Time", justify="right", style="yellow")
        table.add_column("End Time", justify="right", style="yellow")

        for track in tracks:
            table.add_row(
                str(track.number),
                track.duration_str,
                f"{track.start_time:.1f}s",
                f"{track.end_time:.1f}s",
            )

        self.console.print(table)

    def show_saved_files(self, files: List[TrackFile]) -> None:
        """Display saved track files."""
        table = Table(title="Saved Track Files")
        table.add_column("Track", justify="right", style="cyan")
        table.add_column("Filename", style="magenta")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Title", style="yellow")

        for file in files:
            title = file.title or "—"
            table.add_row(str(file.track_number), file.filename, file.duration, title)

        self.console.print(table)

    def show_success_message(self, message: str) -> None:
        """Display a success message."""
        self.console.print(f"[green]✓ {message}[/green]")

    def show_warning_message(self, message: str) -> None:
        """Display a warning message."""
        self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def show_error_message(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[red]✗ {message}[/red]")

    def show_info_message(self, message: str) -> None:
        """Display an informational message."""
        self.console.print(f"[blue]ℹ {message}[/blue]")

    def show_processing_result(self, result: ProcessingResult) -> None:
        """Display the result of a processing operation."""
        if result.success:
            self.show_success_message(result.message)

            if result.output_files:
                self.console.print(
                    f"[dim]Output files: {len(result.output_files)}[/dim]"
                )
                for file_path in result.output_files:
                    self.console.print(f"  [dim]- {file_path.name}[/dim]")
        else:
            self.show_error_message(result.message)

    def show_armed_status(self, threshold_db: float) -> None:
        """Display armed recording status."""
        panel = Panel.fit(
            f"[bold yellow]🎯 ARMED FOR RECORDING[/bold yellow]\n"
            f"Threshold: {threshold_db} dB\n"
            f"[dim]Waiting for audio signal to exceed threshold...\n"
            f"Press Enter to stop once recording begins[/dim]",
            border_style="yellow",
            title="Armed Recording",
        )
        self.console.print(panel)

    def show_recording_triggered(self) -> None:
        """Display that recording has been triggered."""
        self.console.print(
            "[bold green]🔴 RECORDING STARTED![/bold green] Press Enter to stop."
        )

    def show_armed_config(
        self,
        device_id: Optional[int],
        sample_rate: int,
        channels: int,
        bit_depth: Optional[int] = None,
        output_format: Optional[str] = None,
        threshold_db: float = -24,
        buffer_size: Optional[int] = None,
    ) -> None:
        """Display armed recording configuration."""
        config_lines = []

        if device_id is not None:
            config_lines.append(f"Device: {device_id}")

        config_lines.append(f"Sample Rate: {sample_rate}Hz")
        config_lines.append(f"Channels: {channels}")
        config_lines.append(f"[bold yellow]Threshold: {threshold_db} dB[/bold yellow]")

        if bit_depth is not None:
            depth_str = f"{bit_depth}-bit"
            if bit_depth == 32:
                depth_str += " float"
            config_lines.append(f"Bit Depth: {depth_str}")

        if output_format is not None:
            config_lines.append(f"Format: {output_format.upper()}")

        if buffer_size is not None:
            config_lines.append(f"Buffer: {buffer_size}")

        config_text = " | ".join(config_lines)
        panel = Panel.fit(
            f"[bold blue]Armed Recording Configuration[/bold blue]\n{config_text}",
            border_style="blue",
        )
        self.console.print(panel)


class ProgressTracker:
    """Manages progress bars and status updates."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize with optional console instance."""
        self.console = console or Console()

    @contextmanager
    def recording_progress(self, duration: int):
        """Context manager for recording progress."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                f"Recording for {duration} seconds...", total=duration * 10
            )

            try:
                # Yield the progress object so caller can update it
                yield progress, task
            finally:
                progress.update(task, description="✓ Recording complete!")

    @contextmanager
    def processing_progress(self, description: str, total: Optional[int] = None):
        """Context manager for general processing progress."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn() if total else TextColumn(""),
            TaskProgressColumn() if total else TextColumn(""),
            console=self.console,
        ) as progress:
            task = progress.add_task(description, total=total)

            try:
                yield progress, task
            finally:
                progress.update(
                    task, description=f"✓ {description.replace('...', ' complete!')}"
                )

    @contextmanager
    def batch_progress(self, items: List[str]):
        """Context manager for batch processing with item names."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Processing items...", total=len(items))

            try:
                yield progress, task
            finally:
                progress.update(task, description="✓ Batch processing complete!")

    def simple_progress(self, items: List[str], description: str = "Processing"):
        """Simple progress for iterating over items."""
        return self.console.status(description)


class InteractivePrompts:
    """Handles interactive user prompts with rich formatting."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize with optional console instance."""
        self.console = console or Console()

    def confirm(self, message: str, default: bool = True) -> bool:
        """Ask for yes/no confirmation."""
        suffix = " [Y/n]" if default else " [y/N]"
        response = (
            self.console.input(f"[yellow]{message}{suffix}:[/yellow] ").strip().lower()
        )

        if not response:
            return default

        return response in ("y", "yes", "true", "1")

    def get_text_input(self, prompt: str, default: str = "") -> str:
        """Get text input from user."""
        if default:
            prompt += f" [{default}]"

        response = self.console.input(f"[cyan]{prompt}:[/cyan] ").strip()
        return response or default

    def get_int_input(
        self,
        prompt: str,
        default: Optional[int] = None,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
    ) -> int:
        """Get integer input from user with validation."""
        while True:
            try:
                prompt_text = prompt
                if default is not None:
                    prompt_text += f" [{default}]"

                response = self.console.input(f"[cyan]{prompt_text}:[/cyan] ").strip()

                if not response and default is not None:
                    return default

                value = int(response)

                if min_val is not None and value < min_val:
                    self.console.print(f"[red]Value must be at least {min_val}[/red]")
                    continue

                if max_val is not None and value > max_val:
                    self.console.print(f"[red]Value must be at most {max_val}[/red]")
                    continue

                return value

            except ValueError:
                self.console.print("[red]Please enter a valid integer[/red]")
                continue

    def show_search_results(self, results: List[dict]) -> None:
        """Display Discogs search results in a formatted table."""
        table = Table(title="Discogs Search Results")
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Artist", style="magenta")
        table.add_column("Title", style="blue")
        table.add_column("Year", justify="right", style="green")
        table.add_column("Format", style="yellow")
        table.add_column("Label", style="dim")
        table.add_column("Country", style="dim")

        for i, result in enumerate(results, 1):
            table.add_row(
                str(i),
                result.get("artist", "Unknown"),
                result.get("title", "Unknown"),
                str(result.get("year", "")) if result.get("year") else "",
                result.get("format", ""),
                result.get("label", ""),
                result.get("country", ""),
            )

        self.console.print(table)

    def show_collection_list(self, collection: List[dict]) -> None:
        """Display user's Discogs collection in a formatted table."""
        table = Table(title="Discogs Collection")
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Artist", style="magenta")
        table.add_column("Title", style="blue")
        table.add_column("Year", justify="right", style="green")
        table.add_column("Format", style="yellow")
        table.add_column("Label", style="dim")

        for i, item in enumerate(collection, 1):
            table.add_row(
                str(i),
                item.get("artist", "Unknown"),
                item.get("title", "Unknown"),
                str(item.get("year", "")) if item.get("year") else "",
                item.get("format", ""),
                f"{item.get('label', '')} - {item.get('catno', '')}"
                if item.get("catno")
                else item.get("label", ""),
            )

        self.console.print(table)

    def show_release_details(
        self, metadata: AlbumMetadata, tracks: List[DiscogsTrack]
    ) -> None:
        """Display detailed release metadata."""
        # Create main info panel
        info_lines = []
        info_lines.append(
            f"[bold blue]{metadata.artist} - {metadata.album}[/bold blue]"
        )

        if metadata.year:
            info_lines.append(f"Year: [green]{metadata.year}[/green]")

        if metadata.primary_genre:
            info_lines.append(
                f"Genre: [yellow]{metadata.genre_string or metadata.primary_genre}[/yellow]"
            )

        if metadata.label:
            label_info = metadata.primary_label_with_catno or metadata.label
            info_lines.append(f"Label: [cyan]{label_info}[/cyan]")

        if metadata.country:
            info_lines.append(f"Country: [magenta]{metadata.country}[/magenta]")

        if metadata.format_name:
            format_info = metadata.format_name
            if metadata.format_details:
                format_info += f" ({', '.join(metadata.format_details)})"
            info_lines.append(f"Format: [white]{format_info}[/white]")

        if metadata.discogs_id:
            info_lines.append(f"Discogs ID: [dim]{metadata.discogs_id}[/dim]")

        info_panel = Panel(
            "\n".join(info_lines), title="Release Information", border_style="blue"
        )
        self.console.print(info_panel)

        # Create tracklist table
        if tracks:
            track_table = Table(title=f"Tracklist ({len(tracks)} tracks)")
            track_table.add_column("#", justify="right", style="cyan", no_wrap=True)
            track_table.add_column("Position", style="yellow")
            track_table.add_column("Title", style="blue")
            track_table.add_column("Duration", justify="right", style="green")

            for track in tracks:
                track_table.add_row(
                    str(track.track_id),
                    track.position,
                    track.title,
                    track.duration or "",
                )

            self.console.print(track_table)

        # Show notes if available
        if metadata.notes:
            notes_text = (
                metadata.notes[:300] + "..."
                if len(metadata.notes) > 300
                else metadata.notes
            )
            notes_panel = Panel(notes_text, title="Notes", border_style="dim")
            self.console.print(notes_panel)
