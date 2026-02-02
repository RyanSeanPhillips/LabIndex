"""
Generic data file handler.

Handles common scientific data file formats (ABF, SMRX, EDF, MAT, etc.).
Extracts metadata from file paths and any available content.
"""

import re
from typing import List, Dict, Optional, Any, Set

from .base import FileTypeHandler, ReferenceContext, ContentSignature
from ...domain.models import FileRecord, ContentRecord
from ...domain.enums import FileCategory


class GenericDataHandler(FileTypeHandler):
    """
    Handler for scientific data files.

    Handles common data formats used in physiology/neuroscience research:
    - ABF (Axon Binary Format)
    - SMRX/SMR (Spike2)
    - EDF (European Data Format)
    - MAT (MATLAB)
    - NWB/H5 (Neurodata Without Borders)
    - NPZ (NumPy arrays - often processed data)

    Data files don't usually contain text references to other files,
    but we can extract metadata from:
    - File paths (dates, animal IDs, session numbers)
    - Extracted content (if available from extractors)
    """

    name = "generic_data"
    description = "Handler for scientific data files"
    file_extensions = {"abf", "smrx", "smr", "edf", "mat", "nwb", "h5", "hdf5", "npz"}
    file_categories = {FileCategory.DATA}

    # Pattern for date in filename (YYYYMMDD or YYYY-MM-DD or similar)
    DATE_IN_NAME_PATTERNS = [
        re.compile(r'(\d{8})'),           # 20240115
        re.compile(r'(\d{4}-\d{2}-\d{2})'),  # 2024-01-15
        re.compile(r'(\d{4}_\d{2}_\d{2})'),  # 2024_01_15
    ]

    # Pattern for numeric suffix (session/recording number)
    SUFFIX_PATTERN = re.compile(r'(\d{3})\.(?:abf|smrx?|edf)$', re.IGNORECASE)

    # Animal ID patterns in paths
    ANIMAL_ID_IN_PATH = [
        re.compile(r'(?:animal|mouse|rat)[_\-\s]*(\d{3,5})', re.IGNORECASE),
        re.compile(r'/(\d{3,4})/', re.IGNORECASE),  # Folder named with ID
        re.compile(r'[_\-](\d{3,4})[_\-]'),  # ID in filename
    ]

    # NPZ-specific patterns for original file reference
    NPZ_ORIGINAL_PATTERNS = [
        re.compile(r'Original Data File:\s*(\S+)', re.IGNORECASE),
        re.compile(r'Original Path:.*?([^\\/]+\.(?:abf|smrx|smr|edf))', re.IGNORECASE),
    ]

    def can_handle(self, file: FileRecord, content: Optional[ContentRecord] = None) -> float:
        """
        Check if this handler can handle the file.
        """
        # Check extension first - high confidence for known data extensions
        if self._check_extension(file):
            return 0.8

        # Check category
        if file.category == FileCategory.DATA:
            return 0.7

        return 0.0

    def extract_metadata(
        self,
        file: FileRecord,
        content: ContentRecord
    ) -> Dict[str, Any]:
        """
        Extract metadata from data file.

        For data files, metadata comes primarily from:
        - File path structure
        - Extracted content (from ABF/SMRX extractors)
        """
        metadata = {
            "recording_date": None,
            "animal_id": None,
            "session_number": None,
            "channels": [],
            "original_source": None,  # For NPZ files
        }

        # Extract date from filename
        for pattern in self.DATE_IN_NAME_PATTERNS:
            match = pattern.search(file.name)
            if match:
                metadata["recording_date"] = match.group(1)
                break

        # Extract numeric suffix (session number)
        suffix_match = self.SUFFIX_PATTERN.search(file.name)
        if suffix_match:
            metadata["session_number"] = suffix_match.group(1)

        # Extract animal ID from path
        for pattern in self.ANIMAL_ID_IN_PATH:
            match = pattern.search(file.path)
            if match:
                metadata["animal_id"] = match.group(1)
                break

        # If content is available, extract more metadata
        if content and content.full_text:
            # Check for NPZ original file reference
            for pattern in self.NPZ_ORIGINAL_PATTERNS:
                match = pattern.search(content.full_text)
                if match:
                    metadata["original_source"] = match.group(1)
                    break

            # Extract channel info if present
            channel_match = re.findall(
                r'channel[s]?[:\s]*([^\n]+)',
                content.full_text,
                re.IGNORECASE
            )
            if channel_match:
                metadata["channels"] = channel_match[:10]

        # Extract metadata from entities if available
        if content and content.entities:
            if "date" in content.entities:
                metadata["recording_date"] = content.entities["date"][0]
            if "animal_id" in content.entities:
                metadata["animal_id"] = content.entities["animal_id"][0]

        return metadata

    def find_references(
        self,
        file: FileRecord,
        content: ContentRecord,
        context_lines: int = 20
    ) -> List[ReferenceContext]:
        """
        Find references in data file content.

        Data files typically don't reference other files, but NPZ files
        (processed data) may contain references to their source files.
        """
        references = []

        if not content or not content.full_text:
            return references

        text = content.full_text
        lines = text.splitlines()

        # NPZ files: look for original file reference
        if file.ext.lower() == "npz":
            for pattern in self.NPZ_ORIGINAL_PATTERNS:
                for line_num, line in enumerate(lines):
                    match = pattern.search(line)
                    if match:
                        start = max(0, line_num - context_lines)
                        end = min(len(lines), line_num + context_lines + 1)

                        references.append(ReferenceContext(
                            reference=match.group(1),
                            line_number=line_num + 1,
                            before_lines=lines[start:line_num],
                            after_lines=lines[line_num + 1:end],
                            full_context="\n".join(lines[start:end]),
                            extracted_metadata={},
                            reference_type="source_file",
                            confidence=0.95,  # Very high confidence for NPZ sources
                        ))

        return references

    def get_relationship_hints(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None
    ) -> List[str]:
        """Get relationship hints for data files."""
        hints = []

        # NPZ files are typically analysis outputs
        if file.ext.lower() == "npz":
            hints = ["analysis_of", "derived_from", "same_session"]
        else:
            # Raw data files
            hints = ["source_for", "same_session", "same_animal"]

        return hints


class PhotometryDataHandler(FileTypeHandler):
    """
    Specialized handler for fiber photometry data files.

    Identifies photometry data by:
    - Folder patterns (FP_data, photometry, etc.)
    - Content signatures (415nm, 470nm, GCaMP, etc.)
    - File patterns (CSV/Excel with specific columns)
    """

    name = "photometry_data"
    description = "Handler for fiber photometry data"
    file_extensions = {"csv", "xlsx", "xls", "mat"}
    file_patterns = ["*FP_data*", "*photometry*", "*fiber*", "*doric*"]

    content_signatures = [
        ContentSignature(
            keywords=["415nm", "470nm", "GCaMP", "isosbestic", "signal", "control"],
            required_count=2,
            confidence_boost=0.4,
        ),
        ContentSignature(
            keywords=["dF/F", "z-score", "detrend", "bleaching", "ROI"],
            required_count=2,
            confidence_boost=0.3,
        ),
    ]

    # Photometry-specific patterns
    PHOTOMETRY_FOLDER_PATTERN = re.compile(
        r'(?:FP[_\-]?data|photometry|fiber[_\-]?photo)',
        re.IGNORECASE
    )

    CHANNEL_PATTERNS = [
        re.compile(r'(\d{3})[_\-]?nm', re.IGNORECASE),  # 415nm, 470nm
        re.compile(r'(GCaMP|tdTomato|mCherry)', re.IGNORECASE),
        re.compile(r'(signal|control|isosbestic)', re.IGNORECASE),
    ]

    def can_handle(self, file: FileRecord, content: Optional[ContentRecord] = None) -> float:
        """Check if this is a photometry data file."""
        confidence = 0.0

        # Check folder pattern
        if self.PHOTOMETRY_FOLDER_PATTERN.search(file.path):
            confidence += 0.4

        # Check file patterns
        if self._check_patterns(file):
            confidence += 0.3

        # Check content signatures
        if content and content.full_text:
            confidence += self._score_by_signatures(content.full_text)

        return min(confidence, 1.0)

    def extract_metadata(
        self,
        file: FileRecord,
        content: ContentRecord
    ) -> Dict[str, Any]:
        """Extract photometry-specific metadata."""
        metadata = {
            "channels": [],
            "indicators": [],
            "is_raw": True,
            "animal_id": None,
            "session": None,
        }

        # Find channels/wavelengths
        if content and content.full_text:
            for pattern in self.CHANNEL_PATTERNS:
                matches = pattern.findall(content.full_text)
                for match in matches:
                    if match not in metadata["channels"]:
                        metadata["channels"].append(match)

            # Check if processed data
            if any(kw in content.full_text.lower() for kw in ["df/f", "z-score", "detrend"]):
                metadata["is_raw"] = False

        # Extract animal ID from path
        animal_match = re.search(r'(?:animal|mouse)[_\-]?(\d{3,5})', file.path, re.IGNORECASE)
        if animal_match:
            metadata["animal_id"] = animal_match.group(1)

        return metadata

    def find_references(
        self,
        file: FileRecord,
        content: ContentRecord,
        context_lines: int = 20
    ) -> List[ReferenceContext]:
        """
        Photometry data files rarely reference other files directly.
        Return empty list.
        """
        return []

    def get_relationship_hints(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None
    ) -> List[str]:
        """Photometry files are typically sources for notes/analysis."""
        return ["source_for_notes", "same_session", "paired_with_behavior"]
