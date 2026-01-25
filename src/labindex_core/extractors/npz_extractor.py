"""
NPZ file metadata extractor.

Extracts metadata from NumPy .npz files, with special handling for
PhysioMetrics analysis files (.pleth.npz, .ml.npz).
"""

from pathlib import Path
import json
from typing import Dict, Any, List

from .base import TextExtractor, ExtractionResult


class NPZExtractor(TextExtractor):
    """Extract metadata from NPZ files, especially PhysioMetrics analysis files."""

    EXTENSIONS = ['.npz']

    def _extract_impl(self, path: Path) -> ExtractionResult:
        """Extract metadata from NPZ file."""
        try:
            import numpy as np
        except ImportError:
            return ExtractionResult.failure("numpy not installed")

        try:
            # Load the NPZ file
            npz = np.load(str(path), allow_pickle=True)

            # Get list of arrays in the file
            array_names = list(npz.keys())

            metadata: Dict[str, Any] = {
                'array_count': len(array_names),
                'arrays': array_names[:50],  # Limit to first 50 for metadata
            }

            text_parts = [f"NPZ Archive: {path.name}"]

            # Check if this is a PhysioMetrics file
            is_physiometrics = self._detect_physiometrics(npz, array_names)

            if is_physiometrics:
                text_parts.append("Type: PhysioMetrics Analysis File")
                pm_meta, pm_text = self._extract_physiometrics(npz, path)
                metadata.update(pm_meta)
                text_parts.extend(pm_text)
            else:
                # Generic NPZ - just list arrays with shapes
                text_parts.append(f"Arrays: {len(array_names)}")
                for name in array_names[:20]:
                    arr = npz[name]
                    if hasattr(arr, 'shape'):
                        text_parts.append(f"  {name}: {arr.shape} {arr.dtype}")
                    else:
                        text_parts.append(f"  {name}: scalar")

            npz.close()

            return ExtractionResult(
                text='\n'.join(text_parts),
                metadata=metadata,
                sources={'header': '\n'.join(text_parts)}
            )

        except Exception as e:
            return ExtractionResult.failure(f"NPZ read error: {e}")

    def _detect_physiometrics(self, npz, array_names: List[str]) -> bool:
        """Check if this is a PhysioMetrics analysis file."""
        # PhysioMetrics files have specific keys
        pm_keys = ['version', 'original_file_path', 'analyze_chan', 'sr_hz']
        return any(key in array_names for key in pm_keys)

    def _extract_physiometrics(self, npz, path: Path) -> tuple:
        """Extract PhysioMetrics-specific metadata."""
        metadata = {}
        text_parts = []

        # Version
        if 'version' in npz:
            version = str(npz['version'])
            metadata['physiometrics_version'] = version
            text_parts.append(f"PhysioMetrics Version: {version}")

        # Original file reference (important for linking!)
        if 'original_file_path' in npz:
            original = str(npz['original_file_path'])
            metadata['original_file'] = original
            # Extract just the filename for searchability
            original_name = Path(original).name
            metadata['original_filename'] = original_name
            text_parts.append(f"Original Data File: {original_name}")
            text_parts.append(f"Original Path: {original}")

        # Saved timestamp
        if 'saved_timestamp' in npz:
            timestamp = str(npz['saved_timestamp'])
            metadata['saved_timestamp'] = timestamp
            text_parts.append(f"Saved: {timestamp}")

        # Channel info
        if 'analyze_chan' in npz:
            channel = str(npz['analyze_chan'])
            metadata['analyze_channel'] = channel
            text_parts.append(f"Analysis Channel: {channel}")

        if 'stim_chan' in npz:
            stim = str(npz['stim_chan'])
            if stim and stim != 'None':
                metadata['stim_channel'] = stim
                text_parts.append(f"Stimulus Channel: {stim}")

        # Sampling rate
        if 'sr_hz' in npz:
            sr = float(npz['sr_hz'])
            metadata['sampling_rate_hz'] = sr
            text_parts.append(f"Sampling Rate: {sr} Hz")

        # Filter settings
        filter_info = []
        if 'use_low' in npz and npz['use_low']:
            low_hz = float(npz.get('low_hz', 0))
            filter_info.append(f"low-pass {low_hz} Hz")
        if 'use_high' in npz and npz['use_high']:
            high_hz = float(npz.get('high_hz', 0))
            filter_info.append(f"high-pass {high_hz} Hz")
        if filter_info:
            metadata['filters'] = filter_info
            text_parts.append(f"Filters: {', '.join(filter_info)}")

        # Peak/sweep counts
        if 'peak_sweep_indices' in npz:
            sweep_indices = npz['peak_sweep_indices']
            metadata['sweep_count'] = len(sweep_indices)
            text_parts.append(f"Sweeps Analyzed: {len(sweep_indices)}")

            # Count total peaks
            total_peaks = 0
            for sweep_idx in sweep_indices:
                key = f'peaks_sweep_{sweep_idx}'
                if key in npz:
                    peaks = npz[key]
                    if hasattr(peaks, '__len__'):
                        total_peaks += len(peaks)
            metadata['total_peaks'] = total_peaks
            text_parts.append(f"Total Peaks: {total_peaks}")

        # Multi-file info
        if 'file_info_json' in npz:
            try:
                file_info = json.loads(str(npz['file_info_json']))
                file_names = [Path(fi['path']).name for fi in file_info]
                metadata['concatenated_files'] = file_names
                text_parts.append(f"Concatenated Files: {', '.join(file_names)}")
            except:
                pass

        # Check for breath type classification
        breath_types = set()
        for key in npz.keys():
            if 'breath_type_class' in key:
                try:
                    classes = npz[key]
                    if hasattr(classes, 'tolist'):
                        breath_types.update(set(classes.tolist()))
                except:
                    pass
        if breath_types:
            # Filter out empty/null values
            breath_types = {str(t) for t in breath_types if t}
            if breath_types:
                metadata['breath_types'] = list(breath_types)
                text_parts.append(f"Breath Types: {', '.join(breath_types)}")

        # File type based on extension
        if '.pleth.npz' in path.name:
            metadata['file_type'] = 'analysis_session'
            text_parts.insert(1, "File Type: Analysis Session")
        elif '.ml.npz' in path.name:
            metadata['file_type'] = 'ml_training'
            text_parts.insert(1, "File Type: ML Training Data")

        return metadata, text_parts
