"""Audio processing service for analysis and track detection."""

from pathlib import Path
from typing import List
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import split_on_silence
import pyloudnorm as pyln

from .models import AudioQuality, Track
from ..core.exceptions import ProcessingError, QualityAnalysisError
from ..core.config import SilenceDetection


class AudioProcessor:
    """Handles audio analysis and processing operations."""

    def analyze_quality(self, audio_data: np.ndarray, sample_rate: int) -> AudioQuality:
        """Analyze audio quality metrics."""
        try:
            # Convert to mono if stereo for analysis
            if len(audio_data.shape) > 1:
                data_mono = np.mean(audio_data, axis=1)
            else:
                data_mono = audio_data

            # Ensure we have valid audio data
            if len(data_mono) == 0:
                raise QualityAnalysisError("Audio data is empty")

            # Peak level (dBFS)
            max_abs = np.max(np.abs(audio_data))
            if max_abs == 0:
                peak_level = -float("inf")
            else:
                peak_level = 20 * np.log10(max_abs)

            # RMS level
            rms = np.sqrt(np.mean(audio_data**2))
            if rms == 0:
                rms_level = -float("inf")
            else:
                rms_level = 20 * np.log10(rms)

            # Dynamic range (simplified - peak to RMS ratio)
            if rms_level == -float("inf") or peak_level == -float("inf"):
                dynamic_range = 0
            else:
                dynamic_range = peak_level - rms_level

            # Loudness measurement
            try:
                meter = pyln.Meter(sample_rate)
                loudness = meter.integrated_loudness(audio_data)
            except Exception:
                # If loudness measurement fails, use a fallback calculation
                loudness = -23.0  # Default LUFS value

            # Clipping detection (samples at or near maximum)
            clipped_samples = np.sum(np.abs(audio_data) >= 0.99)
            clipping_percentage = (clipped_samples / len(audio_data.flatten())) * 100

            return AudioQuality(
                peak_db=round(peak_level, 2),
                rms_db=round(rms_level, 2),
                dynamic_range=round(dynamic_range, 2),
                loudness_lufs=round(loudness, 2),
                clipping_percent=round(clipping_percentage, 4),
                sample_rate=sample_rate,
                duration_seconds=len(audio_data) / sample_rate,
            )

        except Exception as e:
            raise QualityAnalysisError(
                "Failed to analyze audio quality", details=str(e)
            )

    def analyze_quality_from_file(self, audio_file: Path) -> AudioQuality:
        """Analyze audio quality from a file."""
        try:
            data, sample_rate = sf.read(str(audio_file))
            return self.analyze_quality(data, sample_rate)
        except Exception as e:
            raise QualityAnalysisError(
                "Failed to analyze audio file",
                file_path=str(audio_file),
                details=str(e),
            )

    def detect_tracks(
        self,
        audio_file: Path,
        silence_thresh: int = SilenceDetection.DEFAULT_SILENCE_THRESH_DB,
        min_silence_len: int = SilenceDetection.DEFAULT_MIN_SILENCE_LEN_MS,
        min_track_len: int = SilenceDetection.DEFAULT_MIN_TRACK_LEN_MS,
        keep_silence: int = SilenceDetection.DEFAULT_KEEP_SILENCE_MS,
    ) -> List[Track]:
        """Detect track boundaries using silence detection."""
        try:
            # Load audio file
            audio = AudioSegment.from_file(str(audio_file))

            if len(audio) == 0:
                raise ProcessingError("Audio file is empty")

            # Split on silence
            segments = split_on_silence(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                keep_silence=keep_silence,
            )

            if not segments:
                return []

            # Filter segments and create Track objects
            tracks = []
            current_time = 0

            for i, segment in enumerate(segments):
                if len(segment) >= min_track_len:
                    track = Track(
                        number=i + 1,
                        duration_ms=len(segment),
                        start_time=current_time / 1000.0,  # Convert to seconds
                        end_time=(current_time + len(segment)) / 1000.0,
                    )
                    tracks.append(track)

                current_time += len(segment)

            return tracks

        except Exception as e:
            raise ProcessingError(
                "Failed to detect tracks", file_path=str(audio_file), details=str(e)
            )

    def detect_vinyl_tracks(self, audio_file: Path) -> List[Track]:
        """Detect track boundaries for vinyl records with smart side detection."""
        try:
            # Load audio file
            audio = AudioSegment.from_file(str(audio_file))

            if len(audio) == 0:
                raise ProcessingError("Audio file is empty")

            # First pass: detect all silence periods
            silence_thresh = SilenceDetection.DEFAULT_SILENCE_THRESH_DB
            min_silence_len = 500  # Very short to catch all gaps
            keep_silence = SilenceDetection.DEFAULT_KEEP_SILENCE_MS

            # Get all silence periods
            segments = split_on_silence(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                keep_silence=keep_silence,
            )

            if not segments:
                return []

            # Analyze gaps between segments to classify them
            tracks = []
            current_time = 0
            current_side = "A"
            track_number_in_side = 1
            global_track_number = 1

            for i, segment in enumerate(segments):
                if len(segment) >= SilenceDetection.DEFAULT_MIN_TRACK_LEN_MS:
                    # Calculate gap before this segment (if not first)
                    gap_before = 0
                    if i > 0:
                        # Calculate silence between previous segment and this one
                        gap_before = current_time - sum(len(s) for s in segments[:i])

                    # Determine if this is a side change (gap > 10 seconds)
                    if gap_before > 10000 and global_track_number > 1:
                        # Switch to next side
                        if current_side == "A":
                            current_side = "B"
                        elif current_side == "B":
                            current_side = "C"
                        elif current_side == "C":
                            current_side = "D"
                        track_number_in_side = 1

                    track = Track(
                        number=global_track_number,
                        duration_ms=len(segment),
                        start_time=current_time / 1000.0,
                        end_time=(current_time + len(segment)) / 1000.0,
                        side=current_side,
                    )
                    tracks.append(track)

                    global_track_number += 1
                    track_number_in_side += 1

                current_time += len(segment)

            return tracks

        except Exception as e:
            raise ProcessingError(
                "Failed to detect vinyl tracks",
                file_path=str(audio_file),
                details=str(e),
            )

    def get_audio_info(self, audio_file: Path) -> dict:
        """Get basic audio file information."""
        try:
            info = sf.info(str(audio_file))
            return {
                "duration": info.duration,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "frames": info.frames,
                "format": info.format,
                "subtype": info.subtype,
            }
        except Exception as e:
            raise ProcessingError(
                "Failed to read audio file info",
                file_path=str(audio_file),
                details=str(e),
            )

    def validate_audio_file(self, audio_file: Path) -> bool:
        """Validate that a file is a readable audio file."""
        try:
            # Check if file exists
            if not audio_file.exists():
                return False

            # Try to read file info
            sf.info(str(audio_file))
            return True
        except Exception:
            return False
