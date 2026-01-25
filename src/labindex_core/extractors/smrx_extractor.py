"""
SMRX/SMR file metadata extractor.

Uses sonpy to extract channel and recording metadata from
Spike2 data files (.smrx, .smr).
"""

from pathlib import Path
from typing import Dict, Any

from .base import TextExtractor, ExtractionResult


class SMRXExtractor(TextExtractor):
    """Extract metadata from Spike2 SMRX/SMR files."""

    EXTENSIONS = ['.smrx', '.smr']

    def _extract_impl(self, path: Path) -> ExtractionResult:
        """Extract metadata from SMRX/SMR file."""
        try:
            import sonpy
        except ImportError:
            return ExtractionResult.failure("sonpy not installed")

        try:
            # Open the file
            f = sonpy.lib.SonFile(str(path), True)  # True = read-only

            if f.GetOpenError() != 0:
                return ExtractionResult.failure(f"Failed to open file: error {f.GetOpenError()}")

            # Get basic file info
            metadata: Dict[str, Any] = {
                'time_base': f.GetTimeBase(),
                'max_time_ticks': f.MaxTime(),
                'channel_count': f.MaxChannels(),
            }

            # Calculate duration
            if metadata['time_base'] > 0:
                metadata['total_duration_sec'] = metadata['max_time_ticks'] * metadata['time_base']

            # Get channel information
            channels = []
            channel_names = []
            channel_units = []

            for ch in range(f.MaxChannels()):
                ch_type = f.ChannelType(ch)
                if ch_type != sonpy.lib.DataType.Off:  # Channel exists
                    ch_info = {
                        'number': ch,
                        'title': f.GetChannelTitle(ch),
                        'units': f.GetChannelUnits(ch),
                        'type': str(ch_type),
                    }

                    # Get sampling rate for waveform channels
                    if ch_type in (sonpy.lib.DataType.Adc, sonpy.lib.DataType.RealWave):
                        divide = f.ChannelDivide(ch)
                        if divide > 0 and metadata['time_base'] > 0:
                            ch_info['sampling_rate_hz'] = 1.0 / (divide * metadata['time_base'])

                    channels.append(ch_info)
                    if ch_info['title']:
                        channel_names.append(ch_info['title'])
                    if ch_info['units']:
                        channel_units.append(ch_info['units'])

            metadata['channels'] = channels
            metadata['channel_names'] = channel_names
            metadata['channel_units'] = channel_units

            # Get file comment if available
            try:
                comment = f.GetFileComment(0)
                if comment:
                    metadata['comment'] = comment
            except:
                pass

            # Build searchable text
            text_parts = [
                f"Spike2 Recording: {path.name}",
                f"Active Channels: {len(channels)}",
            ]

            if metadata.get('total_duration_sec'):
                text_parts.append(f"Duration: {metadata['total_duration_sec']:.1f} seconds")

            if channel_names:
                text_parts.append(f"Channels: {', '.join(channel_names)}")

            if channel_units:
                unique_units = list(set(channel_units))
                text_parts.append(f"Units: {', '.join(unique_units)}")

            if metadata.get('comment'):
                text_parts.append(f"Comment: {metadata['comment']}")

            # Add channel details
            for ch in channels:
                rate_str = f", {ch['sampling_rate_hz']:.0f} Hz" if 'sampling_rate_hz' in ch else ""
                text_parts.append(
                    f"Channel {ch['number']}: {ch['title']} ({ch['units']}) - {ch['type']}{rate_str}"
                )

            text = '\n'.join(text_parts)

            f.Close()

            return ExtractionResult(
                text=text,
                metadata=metadata,
                sources={'header': text}
            )

        except Exception as e:
            return ExtractionResult.failure(f"SMRX read error: {e}")
