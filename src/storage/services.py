"""File management service for saving and organizing audio files."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import soundfile as sf
import numpy as np
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TRCK, TDRC, TCON, TPUB, COMM
from mutagen.flac import FLAC
from mutagen.aiff import AIFF

from ..processing.models import Track
from .models import TrackFile
from ..metadata.models import AlbumMetadata
from ..core.exceptions import FileOperationError, MetadataError
from ..core.config import FileConfig, OutputFormat, BitDepth


class FileManager:
    """Handles all file operations for audio data."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize with optional output directory."""
        self.output_dir = output_dir or Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_filename(
        self, prefix: str = "recording", extension: str = "wav", timestamp: bool = True
    ) -> str:
        """Generate a timestamp-based filename."""
        if timestamp:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{prefix}_{timestamp_str}.{extension}"
        else:
            return f"{prefix}.{extension}"

    def save_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        output_path: Optional[Path] = None,
        filename: Optional[str] = None,
        output_format: OutputFormat = OutputFormat.WAV,
        bit_depth: Optional[BitDepth] = None,
    ) -> Path:
        """Save audio data to a file."""
        try:
            if output_path is None:
                if filename is None:
                    base_name = self.generate_filename(extension=output_format.value)
                    filename = base_name
                else:
                    # Ensure correct extension
                    filename_path = Path(filename)
                    filename = f"{filename_path.stem}.{output_format.value}"
                output_path = self.output_dir / filename

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Determine the subtype for the format
            subtype = self._get_subtype_for_format(output_format, bit_depth)

            # Save the audio file with appropriate format and subtype
            sf.write(
                str(output_path),
                audio_data,
                sample_rate,
                format=output_format.value.upper(),
                subtype=subtype,
            )

            if not output_path.exists():
                raise FileOperationError(f"Failed to create file: {output_path}")

            return output_path

        except Exception as e:
            raise FileOperationError(
                "Failed to save audio file",
                file_path=str(output_path) if output_path else None,
                operation="save",
                details=str(e),
            )

    def split_tracks(
        self,
        audio_file: Path,
        tracks: List[Track],
        output_dir: Optional[Path] = None,
        prefix: str = "track",
    ) -> List[TrackFile]:
        """Split audio file into individual track files."""
        if output_dir is None:
            output_dir = self.output_dir

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Load the audio file
            audio = AudioSegment.from_file(str(audio_file))
            saved_files = []

            for track in tracks:
                # Extract the track segment
                start_ms = int(track.start_time * 1000)
                end_ms = int(track.end_time * 1000)
                track_segment = audio[start_ms:end_ms]

                # Generate filename
                filename = (
                    f"{prefix}_{track.number:02d}_{self.generate_filename('', 'wav')}"
                )
                output_path = output_dir / filename

                # Export the track
                track_segment.export(str(output_path), format="wav")

                track_file = TrackFile(
                    track_number=track.number,
                    file_path=output_path,
                    duration=track.duration_str,
                )
                saved_files.append(track_file)

            return saved_files

        except Exception as e:
            raise FileOperationError(
                "Failed to split tracks",
                file_path=str(audio_file),
                operation="split",
                details=str(e),
            )

    def split_vinyl_tracks(
        self,
        audio_file: Path,
        tracks: List[Track],
        album_metadata: Optional[AlbumMetadata] = None,
        track_titles: Optional[List[str]] = None,
        output_format: OutputFormat = OutputFormat.WAV,
        output_dir: Optional[Path] = None,
    ) -> List[TrackFile]:
        """Split vinyl recording into individual track files with proper organization."""
        try:
            # Determine base output directory
            if output_dir is None:
                output_dir = self.output_dir

            # Create album directory name
            if album_metadata:
                album_dir_name = f"{album_metadata.artist} - {album_metadata.album}"
                # Sanitize directory name
                album_dir_name = self._sanitize_filename(album_dir_name)
            else:
                album_dir_name = "Unknown Artist - Unknown Album"

            # Create the album directory
            album_dir = output_dir / album_dir_name
            album_dir.mkdir(parents=True, exist_ok=True)

            # Load the audio file
            audio = AudioSegment.from_file(str(audio_file))
            saved_files = []

            for i, track in enumerate(tracks):
                # Extract the track segment
                start_ms = int(track.start_time * 1000)
                end_ms = int(track.end_time * 1000)
                track_segment = audio[start_ms:end_ms]

                # Determine track title
                if track_titles and i < len(track_titles):
                    track_title = track_titles[i]
                elif (
                    album_metadata
                    and hasattr(album_metadata, "tracks")
                    and i < len(album_metadata.tracks)
                ):
                    track_title = album_metadata.tracks[i].title
                else:
                    track_title = f"Track {track.number:02d}"

                # Sanitize filename
                safe_title = self._sanitize_filename(track_title)
                filename = f"{safe_title}.{output_format.value}"
                output_path = album_dir / filename

                # Export the track in specified format
                track_segment.export(str(output_path), format=output_format.value)

                track_file = TrackFile(
                    track_number=track.number,
                    file_path=output_path,
                    duration=track.duration_str,
                    title=track_title,
                )
                saved_files.append(track_file)

            return saved_files

        except Exception as e:
            raise FileOperationError(
                "Failed to split vinyl tracks",
                file_path=str(audio_file),
                operation="vinyl_split",
                details=str(e),
            )

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename by removing/replacing invalid characters."""
        # Remove or replace characters that are problematic for filenames
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "")

        # Replace multiple spaces with single space and strip
        filename = " ".join(filename.split())

        # Limit length to avoid filesystem issues
        if len(filename) > 200:
            filename = filename[:200]

        return filename.strip()

    def add_metadata(
        self,
        file_path: Path,
        metadata: AlbumMetadata,
        track_title: Optional[str] = None,
        track_number: Optional[int] = None,
    ) -> Path:
        """Add metadata to an audio file based on its format."""
        try:
            file_extension = file_path.suffix.lower()

            if file_extension == ".flac":
                self._add_flac_metadata(file_path, metadata, track_title, track_number)
            elif file_extension == ".aiff":
                self._add_aiff_metadata(file_path, metadata, track_title, track_number)
            elif file_extension == ".wav":
                # WAV files don't support metadata like FLAC/AIFF
                # We'll add BWF (Broadcast Wave Format) info if needed
                self._add_wav_metadata(file_path, metadata, track_title, track_number)
            elif file_extension == ".mp3":
                self._add_mp3_metadata(file_path, metadata, track_title, track_number)
            else:
                # Unsupported format, skip metadata
                pass

            return file_path

        except Exception as e:
            raise MetadataError(
                "Failed to add metadata", file_path=str(file_path), details=str(e)
            )

    def batch_add_metadata(
        self,
        track_files: List[TrackFile],
        album_metadata: AlbumMetadata,
        track_titles: Optional[List[str]] = None,
    ) -> List[TrackFile]:
        """Add metadata to multiple track files."""
        updated_files = []

        for i, track_file in enumerate(track_files):
            title = None
            if track_titles and i < len(track_titles):
                title = track_titles[i]
            elif not title:
                title = f"Track {track_file.track_number}"

            try:
                updated_path = self.add_metadata(
                    track_file.file_path,
                    album_metadata,
                    track_title=title,
                    track_number=track_file.track_number,
                )

                updated_file = TrackFile(
                    track_number=track_file.track_number,
                    file_path=updated_path,
                    duration=track_file.duration,
                    title=title,
                )
                updated_files.append(updated_file)

            except MetadataError as e:
                # Log error but continue with other files
                print(f"Warning: Failed to add metadata to {track_file.file_path}: {e}")
                updated_files.append(track_file)

        return updated_files

    def _get_subtype_for_format(
        self, output_format: OutputFormat, bit_depth: Optional[BitDepth]
    ) -> str:
        """Get the appropriate subtype for the output format and bit depth."""
        if output_format == OutputFormat.WAV:
            if bit_depth == BitDepth.BIT_16:
                return "PCM_16"
            elif bit_depth == BitDepth.BIT_24:
                return "PCM_24"
            elif bit_depth == BitDepth.BIT_32_FLOAT:
                return "FLOAT"
            else:
                return "PCM_24"  # Default to 24-bit
        elif output_format == OutputFormat.FLAC:
            # FLAC supports 16 and 24-bit PCM
            if bit_depth == BitDepth.BIT_16:
                return "PCM_16"
            else:
                return "PCM_24"  # FLAC doesn't support 32-bit float, use 24-bit
        elif output_format == OutputFormat.AIFF:
            if bit_depth == BitDepth.BIT_16:
                return "PCM_16"
            elif bit_depth == BitDepth.BIT_24:
                return "PCM_24"
            elif bit_depth == BitDepth.BIT_32_FLOAT:
                return "FLOAT"
            else:
                return "PCM_24"  # Default to 24-bit
        else:
            return "PCM_16"  # Safe default

    def _add_flac_metadata(
        self,
        file_path: Path,
        metadata: AlbumMetadata,
        track_title: Optional[str] = None,
        track_number: Optional[int] = None,
    ) -> None:
        """Add enhanced metadata to FLAC file."""
        audio_file = FLAC(str(file_path))

        # Core fields
        if track_title:
            audio_file["TITLE"] = track_title
        if metadata.artist:
            audio_file["ARTIST"] = metadata.artist
            audio_file["ALBUMARTIST"] = metadata.artist
        if metadata.album:
            audio_file["ALBUM"] = metadata.album
        if track_number:
            if metadata.total_tracks:
                audio_file["TRACKNUMBER"] = f"{track_number}/{metadata.total_tracks}"
            else:
                audio_file["TRACKNUMBER"] = str(track_number)
        if metadata.year:
            audio_file["DATE"] = str(metadata.year)

        # Extended fields
        if metadata.primary_genre:
            audio_file["GENRE"] = metadata.primary_genre
        if metadata.genre_string:
            audio_file["STYLE"] = metadata.genre_string
        if metadata.label:
            audio_file["LABEL"] = metadata.label
        if metadata.primary_label_with_catno:
            audio_file["ORGANIZATION"] = metadata.primary_label_with_catno
        if metadata.catalog_number:
            audio_file["CATALOGNUMBER"] = metadata.catalog_number
        if metadata.country:
            audio_file["RELEASECOUNTRY"] = metadata.country
        if metadata.discogs_id:
            audio_file["DISCOGS_RELEASE_ID"] = str(metadata.discogs_id)
        if metadata.notes:
            # Truncate notes for FLAC comments
            notes_truncated = (
                metadata.notes[:500] + "..."
                if len(metadata.notes) > 500
                else metadata.notes
            )
            audio_file["COMMENT"] = notes_truncated

        audio_file.save()

    def _add_aiff_metadata(
        self,
        file_path: Path,
        metadata: AlbumMetadata,
        track_title: Optional[str] = None,
        track_number: Optional[int] = None,
    ) -> None:
        """Add enhanced metadata to AIFF file."""
        audio_file = AIFF(str(file_path))

        # AIFF uses ID3 tags similar to MP3
        try:
            audio_file.add_tags()
        except Exception:
            pass  # Tags already exist

        # Core fields
        if track_title:
            audio_file.tags.add(TIT2(encoding=3, text=track_title))
        if metadata.artist:
            audio_file.tags.add(TPE1(encoding=3, text=metadata.artist))
            audio_file.tags.add(TPE2(encoding=3, text=metadata.artist))  # Album artist
        if metadata.album:
            audio_file.tags.add(TALB(encoding=3, text=metadata.album))
        if track_number:
            if metadata.total_tracks:
                audio_file.tags.add(
                    TRCK(encoding=3, text=f"{track_number}/{metadata.total_tracks}")
                )
            else:
                audio_file.tags.add(TRCK(encoding=3, text=str(track_number)))
        if metadata.year:
            audio_file.tags.add(TDRC(encoding=3, text=str(metadata.year)))

        # Extended fields
        if metadata.primary_genre:
            audio_file.tags.add(TCON(encoding=3, text=metadata.primary_genre))
        if metadata.primary_label_with_catno:
            audio_file.tags.add(
                TPUB(encoding=3, text=metadata.primary_label_with_catno)
            )
        if metadata.notes:
            # Truncate notes for ID3 comments
            notes_truncated = (
                metadata.notes[:500] + "..."
                if len(metadata.notes) > 500
                else metadata.notes
            )
            audio_file.tags.add(
                COMM(encoding=3, lang="eng", desc="Comment", text=notes_truncated)
            )

        audio_file.save()

    def _add_wav_metadata(
        self,
        file_path: Path,
        metadata: AlbumMetadata,
        track_title: Optional[str] = None,
        track_number: Optional[int] = None,
    ) -> None:
        """Add basic metadata to WAV file (limited support)."""
        # WAV has limited metadata support
        # For now, we'll just log that metadata was requested but not added
        # In the future, we could implement BWF (Broadcast Wave Format) support
        pass

    def _add_mp3_metadata(
        self,
        file_path: Path,
        metadata: AlbumMetadata,
        track_title: Optional[str] = None,
        track_number: Optional[int] = None,
    ) -> None:
        """Add enhanced ID3 metadata to MP3 file."""
        audio_file = MP3(str(file_path), ID3=ID3)

        # Add ID3 tag if it doesn't exist
        try:
            audio_file.add_tags()
        except Exception:
            pass  # Tags already exist

        # Core fields
        if track_title:
            audio_file.tags.add(TIT2(encoding=3, text=track_title))
        if metadata.artist:
            audio_file.tags.add(TPE1(encoding=3, text=metadata.artist))
            audio_file.tags.add(TPE2(encoding=3, text=metadata.artist))  # Album artist
        if metadata.album:
            audio_file.tags.add(TALB(encoding=3, text=metadata.album))
        if track_number:
            if metadata.total_tracks:
                audio_file.tags.add(
                    TRCK(encoding=3, text=f"{track_number}/{metadata.total_tracks}")
                )
            else:
                audio_file.tags.add(TRCK(encoding=3, text=str(track_number)))
        if metadata.year:
            audio_file.tags.add(TDRC(encoding=3, text=str(metadata.year)))

        # Extended fields
        if metadata.primary_genre:
            audio_file.tags.add(TCON(encoding=3, text=metadata.primary_genre))
        if metadata.primary_label_with_catno:
            audio_file.tags.add(
                TPUB(encoding=3, text=metadata.primary_label_with_catno)
            )
        if metadata.notes:
            # Truncate notes for ID3 comments
            notes_truncated = (
                metadata.notes[:500] + "..."
                if len(metadata.notes) > 500
                else metadata.notes
            )
            audio_file.tags.add(
                COMM(encoding=3, lang="eng", desc="Comment", text=notes_truncated)
            )

        audio_file.save()

    def find_audio_files(self, directory: Path) -> List[Path]:
        """Find all audio files in a directory."""
        if not directory.exists():
            raise FileOperationError(f"Directory does not exist: {directory}")

        audio_files = []
        for extension in FileConfig.SUPPORTED_INPUT_FORMATS:
            pattern = f"*{extension}"
            audio_files.extend(directory.glob(pattern))

        return sorted(audio_files)

    def cleanup_temp_files(self, temp_dir: Path) -> None:
        """Clean up temporary files."""
        try:
            if temp_dir.exists() and temp_dir.is_dir():
                for file in temp_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                temp_dir.rmdir()
        except Exception as e:
            # Don't fail the main operation if cleanup fails
            print(f"Warning: Failed to cleanup temporary files: {e}")

    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get basic information about a file."""
        try:
            stat = file_path.stat()
            return {
                "name": file_path.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "extension": file_path.suffix.lower(),
            }
        except Exception as e:
            raise FileOperationError(
                "Failed to get file information",
                file_path=str(file_path),
                details=str(e),
            )
