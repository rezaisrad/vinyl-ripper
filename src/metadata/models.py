"""Metadata domain models."""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class AlbumMetadata:
    """Album Metadata"""

    # Core fields (existing)
    artist: str
    album: str
    year: Optional[int] = None

    # Extended Discogs fields
    discogs_id: Optional[int] = None
    master_id: Optional[int] = None
    artist_sort: Optional[str] = None
    all_artists: Optional[List[str]] = None

    # Genre/Style
    genres: Optional[List[str]] = None
    styles: Optional[List[str]] = None
    primary_genre: Optional[str] = None
    primary_style: Optional[str] = None

    # Label/Release info
    label: Optional[str] = None
    catalog_number: Optional[str] = None
    all_labels: Optional[List[dict]] = None

    # Physical/Format info
    country: Optional[str] = None
    format_name: Optional[str] = None
    format_details: Optional[List[str]] = None

    # Track info
    total_tracks: Optional[int] = None
    track_titles: Optional[List[str]] = None

    # Quality/Community
    data_quality: Optional[str] = None
    community_have: Optional[int] = None
    community_want: Optional[int] = None

    # Media
    thumb_url: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        """Validate metadata."""
        if not self.artist.strip():
            raise ValueError("Artist cannot be empty")
        if not self.album.strip():
            raise ValueError("Album cannot be empty")
        if self.year is not None and (self.year < 1900 or self.year > 2100):
            raise ValueError("Year must be between 1900 and 2100")

    @property
    def primary_label_with_catno(self) -> Optional[str]:
        """Get label with catalog number if available."""
        if self.label and self.catalog_number:
            return f"{self.label} - {self.catalog_number}"
        return self.label

    @property
    def genre_string(self) -> Optional[str]:
        """Get combined genre/style string."""
        parts = []
        if self.primary_genre:
            parts.append(self.primary_genre)
        if self.primary_style and self.primary_style != self.primary_genre:
            parts.append(self.primary_style)
        return " / ".join(parts) if parts else None


@dataclass
class DiscogsTrack:
    """Track info from Discogs."""

    track_id: int
    position: str
    title: str
    duration: Optional[str] = None
    artists: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None
