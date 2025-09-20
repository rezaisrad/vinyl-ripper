"""Storage domain models."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from ..processing.models import AudioQuality, Track


@dataclass
class TrackFile:
    """Represents a saved track file."""

    track_number: int
    file_path: Path
    duration: str
    title: Optional[str] = None

    @property
    def filename(self) -> str:
        """Just the filename without path."""
        return self.file_path.name


@dataclass
class ProcessingResult:
    """Result of audio processing operations."""

    success: bool
    message: str
    output_files: List[Path] = None
    quality_data: Optional[AudioQuality] = None
    tracks: Optional[List[Track]] = None

    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.output_files is None:
            self.output_files = []
