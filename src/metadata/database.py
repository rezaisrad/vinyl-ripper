"""SQLite database service for storing and retrieving Discogs metadata."""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from .models import AlbumMetadata, DiscogsTrack
from ..core.exceptions import VinylRipperError


class MetadataDatabaseError(VinylRipperError):
    """Error with metadata database operations."""

    pass


class MetadataDatabase:
    """SQLite database for storing and retrieving Discogs metadata."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database with optional custom path."""
        self.db_path = db_path or Path.home() / ".ripper" / "metadata.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database with schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS discogs_metadata (
                    release_id INTEGER NOT NULL,
                    track_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    year INTEGER,
                    discogs_id INTEGER,
                    master_id INTEGER,
                    artist_sort TEXT,
                    all_artists TEXT,
                    genres TEXT,
                    styles TEXT,
                    primary_genre TEXT,
                    primary_style TEXT,
                    label TEXT,
                    catalog_number TEXT,
                    all_labels TEXT,
                    country TEXT,
                    format_name TEXT,
                    format_details TEXT,
                    track_title TEXT,
                    track_position TEXT,
                    track_duration TEXT,
                    track_artists TEXT,
                    total_tracks INTEGER,
                    data_quality TEXT,
                    community_have INTEGER,
                    community_want INTEGER,
                    thumb_url TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (release_id, track_id)
                )""")

                # Create indexes for better query performance
                conn.execute("""CREATE INDEX IF NOT EXISTS idx_discogs_id
                               ON discogs_metadata (discogs_id)""")
                conn.execute("""CREATE INDEX IF NOT EXISTS idx_album_artist
                               ON discogs_metadata (album, artist)""")

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to initialize database: {e}")

    def store_release_metadata(
        self, metadata: AlbumMetadata, tracks: List[DiscogsTrack]
    ):
        """Store complete release metadata with all tracks."""
        if not metadata.discogs_id:
            raise MetadataDatabaseError(
                "Release metadata must have discogs_id to store"
            )

        try:
            with sqlite3.connect(self.db_path) as conn:
                for track in tracks:
                    conn.execute(
                        """INSERT OR REPLACE INTO discogs_metadata
                        (release_id, track_id, title, artist, album, year, discogs_id, master_id,
                         artist_sort, all_artists, genres, styles, primary_genre, primary_style,
                         label, catalog_number, all_labels, country, format_name, format_details,
                         track_title, track_position, track_duration, track_artists, total_tracks,
                         data_quality, community_have, community_want, thumb_url, notes,
                         updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (
                            metadata.discogs_id,
                            track.track_id,
                            track.title,
                            metadata.artist,
                            metadata.album,
                            metadata.year,
                            metadata.discogs_id,
                            metadata.master_id,
                            metadata.artist_sort,
                            json.dumps(metadata.all_artists)
                            if metadata.all_artists
                            else None,
                            json.dumps(metadata.genres) if metadata.genres else None,
                            json.dumps(metadata.styles) if metadata.styles else None,
                            metadata.primary_genre,
                            metadata.primary_style,
                            metadata.label,
                            metadata.catalog_number,
                            json.dumps(metadata.all_labels)
                            if metadata.all_labels
                            else None,
                            metadata.country,
                            metadata.format_name,
                            json.dumps(metadata.format_details)
                            if metadata.format_details
                            else None,
                            track.title,
                            track.position,
                            track.duration,
                            json.dumps(track.artists) if track.artists else None,
                            metadata.total_tracks,
                            metadata.data_quality,
                            metadata.community_have,
                            metadata.community_want,
                            metadata.thumb_url,
                            metadata.notes,
                        ),
                    )

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to store release metadata: {e}")

    def get_release_metadata(self, release_id: int) -> Optional[AlbumMetadata]:
        """Get release metadata (without tracks) by release_id."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM discogs_metadata WHERE release_id = ? LIMIT 1",
                    (release_id,),
                ).fetchone()

                if not row:
                    return None

                return self._row_to_metadata(row)

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to get release metadata: {e}")

    def get_track_metadata(
        self, release_id: int, track_id: int
    ) -> Optional[Tuple[AlbumMetadata, DiscogsTrack]]:
        """Get specific track metadata."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM discogs_metadata WHERE release_id = ? AND track_id = ?",
                    (release_id, track_id),
                ).fetchone()

                if not row:
                    return None

                metadata = self._row_to_metadata(row)
                track = self._row_to_track(row)
                return metadata, track

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to get track metadata: {e}")

    def get_all_tracks(
        self, release_id: int
    ) -> List[Tuple[AlbumMetadata, DiscogsTrack]]:
        """Get all tracks for a release."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM discogs_metadata WHERE release_id = ? ORDER BY track_id",
                    (release_id,),
                ).fetchall()

                results = []
                for row in rows:
                    metadata = self._row_to_metadata(row)
                    track = self._row_to_track(row)
                    results.append((metadata, track))

                return results

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to get all tracks: {e}")

    def release_exists(self, release_id: int) -> bool:
        """Check if release metadata exists in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    "SELECT COUNT(*) FROM discogs_metadata WHERE release_id = ?",
                    (release_id,),
                ).fetchone()
                return result[0] > 0

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to check release existence: {e}")

    def _row_to_metadata(self, row) -> AlbumMetadata:
        """Convert database row to AlbumMetadata object."""
        return AlbumMetadata(
            artist=row["artist"],
            album=row["album"],
            year=row["year"],
            discogs_id=row["discogs_id"],
            master_id=row["master_id"],
            artist_sort=row["artist_sort"],
            all_artists=json.loads(row["all_artists"]) if row["all_artists"] else None,
            genres=json.loads(row["genres"]) if row["genres"] else None,
            styles=json.loads(row["styles"]) if row["styles"] else None,
            primary_genre=row["primary_genre"],
            primary_style=row["primary_style"],
            label=row["label"],
            catalog_number=row["catalog_number"],
            all_labels=json.loads(row["all_labels"]) if row["all_labels"] else None,
            country=row["country"],
            format_name=row["format_name"],
            format_details=json.loads(row["format_details"])
            if row["format_details"]
            else None,
            total_tracks=row["total_tracks"],
            track_titles=None,  # Populated separately if needed
            data_quality=row["data_quality"],
            community_have=row["community_have"],
            community_want=row["community_want"],
            thumb_url=row["thumb_url"],
            notes=row["notes"],
        )

    def _row_to_track(self, row) -> DiscogsTrack:
        """Convert database row to DiscogsTrack object."""
        return DiscogsTrack(
            track_id=row["track_id"],
            position=row["track_position"],
            title=row["track_title"],
            duration=row["track_duration"],
            artists=json.loads(row["track_artists"]) if row["track_artists"] else None,
        )

    def cleanup_old_entries(self, days: int = 30):
        """Remove entries older than specified days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    """
                    DELETE FROM discogs_metadata
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days)
                )
                return result.rowcount

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to cleanup old entries: {e}")

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                total_tracks = conn.execute(
                    "SELECT COUNT(*) FROM discogs_metadata"
                ).fetchone()[0]
                unique_releases = conn.execute(
                    "SELECT COUNT(DISTINCT release_id) FROM discogs_metadata"
                ).fetchone()[0]

                return {
                    "total_tracks": total_tracks,
                    "unique_releases": unique_releases,
                }

        except sqlite3.Error as e:
            raise MetadataDatabaseError(f"Failed to get database stats: {e}")
