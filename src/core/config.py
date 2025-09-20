"""Configuration constants and settings for the vinyl ripper."""

from enum import Enum
from pathlib import Path


class AudioConfig:
    """Audio recording configuration constants."""

    DEFAULT_SAMPLE_RATE = 44100
    DEFAULT_CHANNELS = 2
    DEFAULT_TEST_DURATION = 10
    MAX_SAMPLE_RATE = 200000  # Professional interface supports up to 200kHz
    MIN_SAMPLE_RATE = 8000
    MAX_CHANNELS = 8
    MIN_CHANNELS = 1

    # High-resolution sample rates
    SAMPLE_RATE_44_1 = 44100
    SAMPLE_RATE_48 = 48000
    SAMPLE_RATE_88_2 = 88200
    SAMPLE_RATE_96 = 96000
    SAMPLE_RATE_176_4 = 176400
    SAMPLE_RATE_192 = 192000

    # Standard sample rates list
    STANDARD_SAMPLE_RATES = [44100, 48000, 88200, 96000, 176400, 192000]

    # Bit depth constants
    DEFAULT_BIT_DEPTH = 24
    SUPPORTED_BIT_DEPTHS = [16, 24, 32]  # 32 = 32-bit float

    # Armed recording threshold
    ARM_GAIN_DB = -24


class FileConfig:
    """File handling configuration."""

    SUPPORTED_INPUT_FORMATS = [".wav", ".flac", ".aiff", ".mp3"]
    SUPPORTED_OUTPUT_FORMATS = [
        ".wav",
        ".flac",
        ".aiff",
    ]  # Removed MP3 from primary outputs
    PRIMARY_RECORDING_FORMAT = ".wav"
    ARCHIVAL_FORMAT = ".flac"
    DEFAULT_OUTPUT_FORMAT = ".wav"
    MAX_FILENAME_LENGTH = 255


class QualityThresholds:
    """Audio quality assessment thresholds."""

    PEAK_WARNING_DB = -1.0
    PEAK_GOOD_DB = -3.0
    DYNAMIC_RANGE_LOW_DB = 8.0
    DYNAMIC_RANGE_GOOD_DB = 14.0
    CLIPPING_MINOR_PERCENT = 0.0
    CLIPPING_SIGNIFICANT_PERCENT = 0.1


class SilenceDetection:
    """Track splitting silence detection parameters."""

    DEFAULT_SILENCE_THRESH_DB = -50
    DEFAULT_MIN_SILENCE_LEN_MS = 2000
    DEFAULT_MIN_TRACK_LEN_MS = 10000
    DEFAULT_KEEP_SILENCE_MS = 500


class OutputFormat(Enum):
    """Supported output formats."""

    WAV = "wav"
    FLAC = "flac"
    AIFF = "aiff"

    @property
    def extension(self) -> str:
        """File extension for this format."""
        return f".{self.value}"


class BitDepth(Enum):
    """Supported bit depths."""

    BIT_16 = 16
    BIT_24 = 24
    BIT_32_FLOAT = 32

    @property
    def numpy_dtype(self) -> str:
        """Corresponding numpy dtype for recording."""
        if self.value == 16:
            return "int16"
        elif self.value == 24:
            return "int32"  # sounddevice uses int32 for 24-bit
        elif self.value == 32:
            return "float32"
        else:
            return "int16"


class ProgressConfig:
    """Progress bar and display configuration."""

    PROGRESS_UPDATE_INTERVAL_MS = 100
    SPINNER_STYLE = "dots"
    PROGRESS_BAR_WIDTH = 40


class AppInfo:
    """Application metadata."""

    NAME = "vinyl-ripper"
    VERSION = "1.0.0"
    DESCRIPTION = "Vinyl ripping and audio processing tool"
    AUTHOR = ""


class Paths:
    """Default paths and directories."""

    @staticmethod
    def get_output_dir() -> Path:
        """Get default output directory."""
        return Path.cwd() / "output"

    @staticmethod
    def get_temp_dir() -> Path:
        """Get temporary files directory."""
        return Path.cwd() / "temp"

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """Ensure directory exists and return it."""
        path.mkdir(parents=True, exist_ok=True)
        return path
