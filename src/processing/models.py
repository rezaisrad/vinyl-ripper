"""Processing domain models."""

from dataclasses import dataclass


@dataclass
class AudioQuality:
    """Audio quality analysis results."""

    peak_db: float
    rms_db: float
    dynamic_range: float
    loudness_lufs: float
    clipping_percent: float
    sample_rate: int
    duration_seconds: float

    @property
    def peak_assessment(self) -> str:
        """Assessment of peak level quality."""
        if self.peak_db > -1:
            return "⚠️  Peak level is very high (may be clipped)"
        elif self.peak_db > -3:
            return "⚠️  Peak level is high"
        else:
            return "✓ Peak level is good"

    @property
    def dynamic_range_assessment(self) -> str:
        """Assessment of dynamic range quality."""
        if self.dynamic_range < 8:
            return "⚠️  Low dynamic range (heavily compressed)"
        elif self.dynamic_range < 14:
            return "⚠️  Moderate dynamic range"
        else:
            return "✓ Good dynamic range"

    @property
    def clipping_assessment(self) -> str:
        """Assessment of clipping level."""
        if self.clipping_percent > 0.1:
            return "⚠️  Significant clipping detected"
        elif self.clipping_percent > 0:
            return "⚠️  Minor clipping detected"
        else:
            return "✓ No clipping detected"


@dataclass
class Track:
    """Represents a single audio track."""

    number: int
    duration_ms: int
    start_time: float = 0.0
    end_time: float = 0.0
    side: str = "A"

    @property
    def duration_str(self) -> str:
        """Human-readable duration string."""
        minutes = self.duration_ms // 60000
        seconds = (self.duration_ms % 60000) // 1000
        return f"{minutes}:{seconds:02d}"

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ms / 1000.0
