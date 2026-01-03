"""Audio recording service for capturing audio from input devices."""

import threading
from typing import List
import numpy as np
import sounddevice as sd

from .models import AudioDevice, RecordingConfig
from ..core.exceptions import AudioDeviceError, RecordingError
from ..core.config import AudioConfig


class AudioRecorder:
    """Handles all audio recording operations."""

    def discover_devices(self) -> List[AudioDevice]:
        """Discover and return available audio input devices."""
        try:
            devices = sd.query_devices()
        except Exception as e:
            raise AudioDeviceError("Failed to query audio devices", details=str(e))

        input_devices = []
        for i, device in enumerate(devices):
            if device["max_input_channels"] > 0:
                # Test supported sample rates and bit depths
                supported_sample_rates = self._test_device_sample_rates(i)
                supported_bit_depths = self._test_device_bit_depths(i)

                audio_device = AudioDevice(
                    id=i,
                    name=device["name"],
                    max_channels=device["max_input_channels"],
                    sample_rate=device["default_samplerate"],
                    supported_sample_rates=supported_sample_rates,
                    supported_bit_depths=supported_bit_depths,
                )
                input_devices.append(audio_device)

        if not input_devices:
            raise AudioDeviceError("No audio input devices found")

        return input_devices

    def _test_device_sample_rates(self, device_id: int) -> List[int]:
        """Test which sample rates are supported by a device."""
        supported_rates = []
        for rate in AudioConfig.STANDARD_SAMPLE_RATES:
            try:
                sd.check_input_settings(device=device_id, channels=2, samplerate=rate)
                supported_rates.append(rate)
            except Exception:
                pass  # Rate not supported
        return supported_rates

    def _test_device_bit_depths(self, device_id: int) -> List[int]:
        """Test which bit depths are supported by a device."""
        supported_depths = []
        dtypes = {"int16": 16, "int32": 24, "float32": 32}

        for dtype, depth in dtypes.items():
            try:
                sd.check_input_settings(
                    device=device_id, channels=2, samplerate=48000, dtype=dtype
                )
                supported_depths.append(depth)
            except Exception:
                pass  # Bit depth not supported
        return supported_depths

    def record_for_duration(self, config: RecordingConfig) -> np.ndarray:
        """Record audio for a specific duration."""
        if config.duration is None:
            raise RecordingError("Duration must be specified for timed recording")

        # Validate configuration first
        self.validate_config(config)

        try:
            # Use the numpy dtype from the bit depth configuration
            audio_data = sd.rec(
                int(config.duration * config.sample_rate),
                samplerate=config.sample_rate,
                channels=config.channels,
                device=config.device_id,
                dtype=config.numpy_dtype,
                blocksize=config.buffer_size,
            )
            sd.wait()  # Wait until recording is finished
            return audio_data

        except sd.PortAudioError as e:
            raise RecordingError(
                "Audio recording failed", device_id=config.device_id, details=str(e)
            )
        except Exception as e:
            raise RecordingError(
                "Unexpected error during recording",
                device_id=config.device_id,
                details=str(e),
            )

    def record_with_interrupt(self, config: RecordingConfig) -> np.ndarray:
        """Record audio until manually stopped (press Enter)."""
        audio_chunks = []
        recording = threading.Event()
        recording.set()

        def audio_callback(indata, frames, time, status):
            if status:
                # Log status but don't fail - some status messages are informational
                pass
            if recording.is_set():
                audio_chunks.append(indata.copy())

        try:
            with sd.InputStream(
                device=config.device_id,
                channels=config.channels,
                samplerate=config.sample_rate,
                dtype=config.numpy_dtype,
                blocksize=config.buffer_size,
                callback=audio_callback,
            ):
                input()  # Wait for user to press Enter

            recording.clear()

            if not audio_chunks:
                raise RecordingError("No audio data was recorded")

            # Combine all audio chunks
            full_audio = np.concatenate(audio_chunks, axis=0)
            return full_audio

        except sd.PortAudioError as e:
            recording.clear()
            raise RecordingError(
                "Audio recording failed", device_id=config.device_id, details=str(e)
            )
        except KeyboardInterrupt:
            recording.clear()
            raise RecordingError("Recording interrupted by user")
        except Exception as e:
            recording.clear()
            raise RecordingError(
                "Unexpected error during recording",
                device_id=config.device_id,
                details=str(e),
            )

    def get_device_info(self, device_id: int) -> AudioDevice:
        """Get information about a specific device."""
        devices = self.discover_devices()
        for device in devices:
            if device.id == device_id:
                return device
        raise AudioDeviceError(
            f"Device with ID {device_id} not found", device_id=device_id
        )

    def validate_config(self, config: RecordingConfig) -> None:
        """Validate recording configuration against available devices."""
        # Validate sample rate
        if config.sample_rate not in AudioConfig.STANDARD_SAMPLE_RATES:
            if (
                config.sample_rate < AudioConfig.MIN_SAMPLE_RATE
                or config.sample_rate > AudioConfig.MAX_SAMPLE_RATE
            ):
                raise RecordingError(
                    f"Sample rate {config.sample_rate}Hz is not supported. "
                    f"Supported range: {AudioConfig.MIN_SAMPLE_RATE}-{AudioConfig.MAX_SAMPLE_RATE}Hz"
                )

        # Validate bit depth
        if config.bit_depth.value not in AudioConfig.SUPPORTED_BIT_DEPTHS:
            raise RecordingError(
                f"Bit depth {config.bit_depth.value} is not supported. "
                f"Supported depths: {AudioConfig.SUPPORTED_BIT_DEPTHS}"
            )

        if config.device_id is not None:
            # Check if device exists
            try:
                device = self.get_device_info(config.device_id)
                # Check if requested channels are supported
                if config.channels > device.max_channels:
                    raise RecordingError(
                        f"Device {device.name} supports maximum {device.max_channels} channels, "
                        f"but {config.channels} requested"
                    )

                # Test the actual configuration with sounddevice
                try:
                    sd.check_input_settings(
                        device=config.device_id,
                        channels=config.channels,
                        samplerate=config.sample_rate,
                        dtype=config.numpy_dtype,
                    )
                except Exception as e:
                    raise RecordingError(
                        f"Configuration not supported by device {device.name}: "
                        f"{config.sample_rate}Hz, {config.bit_depth.value}-bit, {config.channels}ch. "
                        f"Details: {str(e)}"
                    )

            except AudioDeviceError:
                raise RecordingError(f"Audio device {config.device_id} not available")

    def record_with_arm(self, config: RecordingConfig) -> np.ndarray:
        """Record audio with armed mode - starts automatically when signal exceeds threshold."""
        if not config.armed:
            raise RecordingError(
                "Recording configuration must be armed for armed recording"
            )

        # Validate configuration first
        self.validate_config(config)

        audio_chunks = []
        recording_state = threading.Event()
        armed_state = threading.Event()
        armed_state.set()  # Start in armed state

        def calculate_db_level(audio_data: np.ndarray) -> float:
            """Calculate dB level from audio data."""
            # Calculate RMS
            valid_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
            rms = np.sqrt(np.mean(valid_data**2))
            if rms > 0:
            if rms > 0:
                return 20 * np.log10(rms)
            else:
                return -float("inf")  # Silent audio

        def audio_callback(indata, frames, time, status):
            if status:
                # Log status but don't fail - some status messages are informational
                pass

            # Calculate current audio level
            db_level = calculate_db_level(indata)

            # Check if we should start recording
            if armed_state.is_set() and db_level >= config.arm_threshold_db:
                armed_state.clear()
                recording_state.set()
                # Don't miss this first chunk that triggered recording
                audio_chunks.append(indata.copy())
                return

            # Continue recording if already started
            if recording_state.is_set():
                audio_chunks.append(indata.copy())

        try:
            with sd.InputStream(
                device=config.device_id,
                channels=config.channels,
                samplerate=config.sample_rate,
                dtype=config.numpy_dtype,
                blocksize=config.buffer_size,
                callback=audio_callback,
            ):
                # Wait for user to press Enter to stop
                input()

            recording_state.clear()
            armed_state.clear()

            if not audio_chunks:
                raise RecordingError(
                    "No audio data was recorded - threshold may not have been reached"
                )

            # Combine all audio chunks
            full_audio = np.concatenate(audio_chunks, axis=0)
            return full_audio

        except sd.PortAudioError as e:
            recording_state.clear()
            armed_state.clear()
            raise RecordingError(
                "Audio recording failed", device_id=config.device_id, details=str(e)
            )
        except KeyboardInterrupt:
            recording_state.clear()
            armed_state.clear()
            raise RecordingError("Recording interrupted by user")
        except Exception as e:
            recording_state.clear()
            armed_state.clear()
            raise RecordingError(
                "Unexpected error during armed recording",
                device_id=config.device_id,
                details=str(e),
            )
