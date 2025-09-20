"""Recording domain models."""

from dataclasses import dataclass
from typing import Optional, List

from ..core.config import BitDepth, OutputFormat


@dataclass
class AudioDevice:
    """Represents an audio input device."""

    id: int
    name: str
    max_channels: int
    sample_rate: float
    supported_sample_rates: Optional[List[int]] = None
    supported_bit_depths: Optional[List[int]] = None

    @property
    def display_name(self) -> str:
        """Human-readable device name with details."""
        return f"{self.name} ({self.max_channels}ch, {self.sample_rate:.0f}Hz)"

    def supports_sample_rate(self, sample_rate: int) -> bool:
        """Check if device supports the given sample rate."""
        if self.supported_sample_rates is None:
            return True  # Assume supported if not specified
        return sample_rate in self.supported_sample_rates

    def supports_bit_depth(self, bit_depth: int) -> bool:
        """Check if device supports the given bit depth."""
        if self.supported_bit_depths is None:
            return True  # Assume supported if not specified
        return bit_depth in self.supported_bit_depths


@dataclass
class RecordingConfig:
    """Configuration for audio recording operations."""

    device_id: Optional[int] = None
    sample_rate: int = 44100
    channels: int = 2
    duration: Optional[int] = None
    bit_depth: BitDepth = BitDepth.BIT_24
    output_format: OutputFormat = OutputFormat.WAV
    buffer_size: Optional[int] = None
    armed: bool = False
    arm_threshold_db: float = -24

    def __post_init__(self):
        """Validate configuration values."""
        if self.sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if self.channels <= 0:
            raise ValueError("Channels must be positive")
        if self.duration is not None and self.duration <= 0:
            raise ValueError("Duration must be positive")
        if self.buffer_size is not None and self.buffer_size <= 0:
            raise ValueError("Buffer size must be positive")

    @property
    def numpy_dtype(self) -> str:
        """Get numpy dtype for this bit depth."""
        return self.bit_depth.numpy_dtype

    @property
    def estimated_file_size_mb(self) -> float:
        """Estimate file size in MB for the given duration."""
        if self.duration is None:
            return 0.0

        bytes_per_sample = (
            self.bit_depth.value // 8 if self.bit_depth.value != 32 else 4
        )
        total_samples = self.sample_rate * self.channels * self.duration
        size_bytes = total_samples * bytes_per_sample

        # Add format overhead (approximate)
        if self.output_format == OutputFormat.FLAC:
            size_bytes *= 0.6  # FLAC compression ratio
        elif self.output_format == OutputFormat.AIFF:
            size_bytes *= 1.1  # AIFF has slightly more overhead than WAV

        return size_bytes / (1024 * 1024)
