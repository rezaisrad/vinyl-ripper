"""Discogs API service for fetching release metadata."""

import os
from typing import List, Optional, Dict, Any, Tuple

import discogs_client

from .models import AlbumMetadata, DiscogsTrack
from ..core.exceptions import VinylRipperError
from .database import MetadataDatabase


class DiscogsServiceError(VinylRipperError):
    """Error with Discogs API operations."""

    pass


class DiscogsService:
    """Service for interacting with Discogs API and managing metadata."""

    def __init__(self, api_token: Optional[str] = None):
        """Initialize with optional API token."""
        self.api_token = api_token or os.getenv("DISCOGS_API_TOKEN")
        if not self.api_token:
            raise DiscogsServiceError("DISCOGS_API_TOKEN environment variable required")

        self.client = discogs_client.Client(
            "VinylRipper/1.0", user_token=self.api_token
        )
        self.db = MetadataDatabase()

    def search_releases(
        self, query: str, release_type: str = "release", limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for releases using Discogs API."""
        try:
            results = self.client.search(query, type=release_type)

            formatted_results = []
            for i, result in enumerate(results[:limit]):
                formatted_results.append(
                    {
                        "id": result.id,
                        "title": result.title,
                        "artist": result.artist
                        if hasattr(result, "artist")
                        else "Unknown",
                        "year": result.year if hasattr(result, "year") else None,
                        "format": result.format if hasattr(result, "format") else None,
                        "label": result.label if hasattr(result, "label") else None,
                        "catno": result.catno if hasattr(result, "catno") else None,
                        "country": result.country
                        if hasattr(result, "country")
                        else None,
                    }
                )

            return formatted_results

        except Exception as e:
            raise DiscogsServiceError(f"Failed to search Discogs: {e}")

    def get_release_metadata(
        self, release_id: int
    ) -> Tuple[AlbumMetadata, List[DiscogsTrack]]:
        """Get metadata for a specific release ID."""
        try:
            release = self.client.release(release_id)
            metadata = self._parse_release_to_metadata(release)
            tracks = self._parse_release_to_tracks(release)

            # Store in database for future reference
            self.db.store_release_metadata(metadata, tracks)

            return metadata, tracks

        except Exception as e:
            raise DiscogsServiceError(f"Failed to get release metadata: {e}")

    def get_user_collection(
        self, username: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get user's collection. If no username, get authenticated user's collection."""
        try:
            if not username:
                me = self.client.identity()
                username = me.username

            user = self.client.user(username)
            collection = user.collection_folders[0].releases  # "All" folder

            formatted_collection = []
            for i, item in enumerate(collection[:limit]):
                basic_info = item.basic_information
                formatted_collection.append(
                    {
                        "id": basic_info.id,
                        "instance_id": item.instance_id,
                        "title": basic_info.title,
                        "artist": basic_info.artists[0].name
                        if basic_info.artists
                        else "Unknown",
                        "year": basic_info.year,
                        "format": basic_info.formats[0]["name"]
                        if basic_info.formats
                        else None,
                        "label": basic_info.labels[0].name
                        if basic_info.labels
                        else None,
                        "catno": basic_info.labels[0].catno
                        if basic_info.labels
                        else None,
                    }
                )

            return formatted_collection

        except Exception as e:
            raise DiscogsServiceError(f"Failed to get user collection: {e}")

    def _parse_release_to_metadata(self, release) -> AlbumMetadata:
        """Convert discogs_client Release to AlbumMetadata."""
        try:
            # Extract basic info
            primary_artist = release.artists[0].name if release.artists else "Unknown"
            all_artists = (
                [artist.name for artist in release.artists] if release.artists else None
            )

            # Extract label info
            primary_label = release.labels[0].name if release.labels else None
            catalog_number = release.labels[0].catno if release.labels else None
            all_labels = None
            if release.labels:
                all_labels = [
                    {"name": label.name, "catno": label.catno, "id": label.id}
                    for label in release.labels
                ]

            # Extract format info
            format_name = None
            format_details = None
            if release.formats:
                format_info = release.formats[0]
                format_name = format_info.get("name")
                format_details = format_info.get("descriptions", [])

            # Count actual tracks (not index tracks or headings)
            tracks = [t for t in release.tracklist if t.data.get("type_") == "track"]
            track_titles = [track.title for track in tracks]

            # Extract community stats
            community_have = None
            community_want = None
            if hasattr(release, "community") and release.community:
                community_have = getattr(release.community, "in_collection", None)
                community_want = getattr(release.community, "in_wantlist", None)

            return AlbumMetadata(
                # Core fields
                artist=primary_artist,
                album=release.title,
                year=release.year if hasattr(release, "year") else None,
                # Extended fields
                discogs_id=release.id,
                master_id=release.master.id
                if hasattr(release, "master") and release.master
                else None,
                artist_sort=getattr(release, "artists_sort", None),
                all_artists=all_artists,
                # Genre/Style
                genres=release.genres if hasattr(release, "genres") else None,
                styles=release.styles if hasattr(release, "styles") else None,
                primary_genre=release.genres[0]
                if hasattr(release, "genres") and release.genres
                else None,
                primary_style=release.styles[0]
                if hasattr(release, "styles") and release.styles
                else None,
                # Label/Release info
                label=primary_label,
                catalog_number=catalog_number,
                all_labels=all_labels,
                # Physical/Format info
                country=getattr(release, "country", None),
                format_name=format_name,
                format_details=format_details,
                # Track info
                total_tracks=len(tracks),
                track_titles=track_titles,
                # Quality/Community
                data_quality=getattr(release, "data_quality", None),
                community_have=community_have,
                community_want=community_want,
                # Media
                thumb_url=getattr(release, "thumb", None),
                notes=getattr(release, "notes", None),
            )

        except Exception as e:
            raise DiscogsServiceError(f"Failed to parse release metadata: {e}")

    def _parse_release_to_tracks(self, release) -> List[DiscogsTrack]:
        """Convert discogs_client Release tracklist to DiscogsTrack objects."""
        try:
            tracks = []
            track_counter = 1

            for track_item in release.tracklist:
                track_data = track_item.data

                # Only process actual tracks, skip index tracks, headings, etc.
                if track_data.get("type_") == "track":
                    # Extract track-specific artists if any
                    track_artists = None
                    if hasattr(track_item, "artists") and track_item.artists:
                        track_artists = [artist.name for artist in track_item.artists]
                    elif "extraartists" in track_data:
                        track_artists = [
                            artist["name"] for artist in track_data["extraartists"]
                        ]

                    track = DiscogsTrack(
                        track_id=track_counter,
                        position=track_data.get("position", f"{track_counter}"),
                        title=track_data.get("title", f"Track {track_counter}"),
                        duration=track_data.get("duration"),
                        artists=track_artists,
                    )

                    tracks.append(track)
                    track_counter += 1

            return tracks

        except Exception as e:
            raise DiscogsServiceError(f"Failed to parse release tracks: {e}")

    def get_authenticated_username(self) -> str:
        """Get the username of the authenticated user."""
        try:
            identity = self.client.identity()
            return identity.username
        except Exception as e:
            raise DiscogsServiceError(f"Failed to get authenticated username: {e}")

    def validate_api_connection(self) -> bool:
        """Test if API connection is working."""
        try:
            self.client.identity()
            return True
        except Exception:
            return False
