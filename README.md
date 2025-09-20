# Ripper

Vinyl recording and processing tool for digitizing records.

## Features

- Records audio from vinyl at up to 192kHz/32-bit
- Detects track boundaries using silence analysis
- Integrates with Discogs API for metadata
- Outputs to WAV, FLAC, or AIFF formats
- Tags files with ID3 metadata

## Requirements

- Python 3.13+
- Audio input device
- Discogs API token (for metadata features)

## Installation

```bash
uv sync
```

## Usage

### List audio devices
```bash
uv run python main.py devices
```

### Record vinyl
```bash
uv run python main.py arm-record --device 1 --sample-rate 96000 --bit-depth 24 --format flac
```

The recording starts automatically when audio exceeds threshold (-24dB default).

### Split recording into tracks
```bash
uv run python main.py split recording.wav --preview
uv run python main.py split recording.wav --release-id 12345678 --format flac
```

### Tag files with metadata
```bash
uv run python main.py metadata search "artist album"
uv run python main.py metadata from-id 12345678 --tag-files
```

## Configuration

Set your Discogs API token:
```bash
export DISCOGS_API_TOKEN=your_token_here
```

## Project Structure

- `src/recording/` - Audio device management and recording
- `src/processing/` - Audio analysis and track detection
- `src/metadata/` - Discogs integration and tagging
- `src/storage/` - File operations and metadata
- `src/interface/` - CLI commands and display

## Development

```bash
uv run ruff check
uv run ruff format
uv run pytest
```