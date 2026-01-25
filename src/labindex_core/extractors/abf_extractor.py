"""
ABF file metadata extractor.

Uses pyabf to extract protocol, channel, and recording metadata from
Axon Binary Format files (.abf).
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from .base import TextExtractor, ExtractionResult


class ABFExtractor(TextExtractor):
    """Extract metadata from ABF (Axon Binary Format) files."""

    EXTENSIONS = ['.abf']

    def _extract_impl(self, path: Path) -> ExtractionResult:
        """Extract metadata from ABF file."""
        try:
            import pyabf
        except ImportError:
            return ExtractionResult.failure("pyabf not installed")

        try:
            abf = pyabf.ABF(str(path), loadData=False)  # Don't load data, just header

            # Build metadata dict
            metadata: Dict[str, Any] = {
                'abf_version': abf.abfVersion,
                'protocol': abf.protocol,
                'protocol_path': abf.protocolPath,
                'channel_count': abf.channelCount,
                'channel_list': abf.channelList,
                'adc_names': abf.adcNames,
                'adc_units': abf.adcUnits,
                'dac_names': abf.dacNames,
                'sampling_rate_hz': abf.sampleRate,
                'sweep_count': abf.sweepCount,
                'sweep_length_sec': abf.sweepLengthSec,
                'total_duration_sec': abf.sweepCount * abf.sweepLengthSec,
                'data_points_per_sweep': abf.sweepPointCount,
            }

            # Recording date/time
            if hasattr(abf, 'abfDateTime') and abf.abfDateTime:
                metadata['recording_datetime'] = abf.abfDateTime.isoformat()
                metadata['recording_date'] = abf.abfDateTime.strftime('%Y-%m-%d')
                metadata['recording_time'] = abf.abfDateTime.strftime('%H:%M:%S')

            # Comments/tags if present
            if hasattr(abf, 'tagComments') and abf.tagComments:
                metadata['tags'] = abf.tagComments
            if hasattr(abf, 'tagTimesMin') and abf.tagTimesMin:
                metadata['tag_times_min'] = abf.tagTimesMin

            # File creator info
            if hasattr(abf, 'creator'):
                metadata['creator'] = abf.creator
            if hasattr(abf, 'creatorVersion'):
                metadata['creator_version'] = str(abf.creatorVersion)

            # Build searchable text from metadata
            text_parts = [
                f"ABF Recording: {path.name}",
                f"Protocol: {abf.protocol}",
                f"Channels: {', '.join(abf.adcNames)}",
                f"Units: {', '.join(abf.adcUnits)}",
                f"Sampling Rate: {abf.sampleRate} Hz",
                f"Sweeps: {abf.sweepCount}",
                f"Duration: {metadata['total_duration_sec']:.1f} seconds",
            ]

            if metadata.get('recording_datetime'):
                text_parts.append(f"Recorded: {metadata['recording_datetime']}")

            if metadata.get('tags'):
                text_parts.append(f"Tags: {', '.join(metadata['tags'])}")

            # Add channel details
            for i, (name, unit) in enumerate(zip(abf.adcNames, abf.adcUnits)):
                text_parts.append(f"Channel {i}: {name} ({unit})")

            text = '\n'.join(text_parts)

            return ExtractionResult(
                text=text,
                metadata=metadata,
                sources={'header': text}
            )

        except Exception as e:
            return ExtractionResult.failure(f"ABF read error: {e}")
