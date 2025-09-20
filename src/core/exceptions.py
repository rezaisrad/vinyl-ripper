"""Custom exceptions for the vinyl ripper application."""


class VinylRipperError(Exception):
    """Base exception for all vinyl ripper errors."""

    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class AudioDeviceError(VinylRipperError):
    """Raised when there are issues with audio devices."""

    def __init__(self, message: str, device_id: int = None, details: str = None):
        super().__init__(message, details)
        self.device_id = device_id


class RecordingError(VinylRipperError):
    """Raised when audio recording fails."""

    def __init__(self, message: str, device_id: int = None, details: str = None):
        super().__init__(message, details)
        self.device_id = device_id


class ProcessingError(VinylRipperError):
    """Raised when audio processing operations fail."""

    def __init__(self, message: str, file_path: str = None, details: str = None):
        super().__init__(message, details)
        self.file_path = file_path


class FileOperationError(VinylRipperError):
    """Raised when file operations fail."""

    def __init__(
        self,
        message: str,
        file_path: str = None,
        operation: str = None,
        details: str = None,
    ):
        super().__init__(message, details)
        self.file_path = file_path
        self.operation = operation


class ConfigurationError(VinylRipperError):
    """Raised when there are configuration issues."""

    def __init__(self, message: str, parameter: str = None, details: str = None):
        super().__init__(message, details)
        self.parameter = parameter


class MetadataError(VinylRipperError):
    """Raised when metadata operations fail."""

    def __init__(
        self, message: str, file_path: str = None, tag: str = None, details: str = None
    ):
        super().__init__(message, details)
        self.file_path = file_path
        self.tag = tag


class QualityAnalysisError(VinylRipperError):
    """Raised when audio quality analysis fails."""

    def __init__(
        self,
        message: str,
        file_path: str = None,
        analysis_type: str = None,
        details: str = None,
    ):
        super().__init__(message, details)
        self.file_path = file_path
        self.analysis_type = analysis_type
