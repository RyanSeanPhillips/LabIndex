"""
Generic text file handler.

This is the fallback handler for text-based files (txt, md, docx content, etc.).
It provides basic reference detection and metadata extraction for any
text-containing file.
"""

import re
from typing import List, Dict, Optional, Any, Set

from .base import FileTypeHandler, ReferenceContext, ContentSignature
from ...domain.models import FileRecord, ContentRecord
from ...domain.enums import FileCategory


class GenericTextHandler(FileTypeHandler):
    """
    Fallback handler for text-based files.

    Handles any file with extracted text content. Provides:
    - Basic filename reference detection
    - Short reference patterns (000, 001, etc.)
    - Date extraction
    - Animal/subject ID extraction
    """

    name = "generic_text"
    description = "Fallback handler for text files"
    file_extensions = {"txt", "md", "log", "rtf"}
    file_categories = {FileCategory.DOCUMENTS, FileCategory.OTHER}

    # Common data file extensions to look for in text
    DATA_FILE_PATTERN = re.compile(
        r'\b([\w\-]+\.(?:abf|smrx|smr|edf|mat|nwb|h5|csv|xlsx?))\b',
        re.IGNORECASE
    )

    # Short reference patterns (e.g., "000", "001" referring to files)
    SHORT_REF_PATTERN = re.compile(r'\b(\d{3})(?:\.abf)?\b')

    # Date patterns in text
    DATE_PATTERNS = [
        re.compile(r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b'),      # 2024-01-15
        re.compile(r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b'),      # 01/15/2024
        re.compile(r'\b(\d{8})\b'),                          # 20240115
    ]

    # Animal/subject ID patterns
    ANIMAL_ID_PATTERNS = [
        re.compile(r'(?:animal|mouse|rat|subject)[_\-\s]*(\d{3,5})', re.IGNORECASE),
        re.compile(r'(?:id)[_\-\s]*(\d{3,5})', re.IGNORECASE),
        re.compile(r'\b([A-Z]{2,3}\d{3,5})\b'),  # e.g., GR982, ABC1234
    ]

    def can_handle(self, file: FileRecord, content: Optional[ContentRecord] = None) -> float:
        """
        Check if this handler can handle the file.

        Generic text handler is the fallback, so returns low confidence
        for any file with text content.
        """
        # Check extension first
        if self._check_extension(file):
            return 0.6

        # Check category
        if file.category == FileCategory.DOCUMENTS:
            return 0.5

        # If there's content, we can handle it with low confidence
        if content and content.full_text:
            return 0.2

        return 0.0

    def extract_metadata(
        self,
        file: FileRecord,
        content: ContentRecord
    ) -> Dict[str, Any]:
        """
        Extract basic metadata from text content.

        Returns dict with:
        - dates: List of dates found
        - animal_ids: List of animal/subject IDs found
        - file_references: List of filenames mentioned
        - line_count: Number of lines
        """
        text = content.full_text or ""
        metadata = {
            "dates": [],
            "animal_ids": [],
            "file_references": [],
            "line_count": len(text.splitlines()),
        }

        # Extract dates
        for pattern in self.DATE_PATTERNS:
            metadata["dates"].extend(pattern.findall(text))
        metadata["dates"] = list(set(metadata["dates"]))[:10]  # Limit

        # Extract animal IDs
        for pattern in self.ANIMAL_ID_PATTERNS:
            matches = pattern.findall(text)
            metadata["animal_ids"].extend(matches)
        metadata["animal_ids"] = list(set(metadata["animal_ids"]))[:10]

        # Extract file references
        matches = self.DATA_FILE_PATTERN.findall(text)
        metadata["file_references"] = list(set(matches))[:20]

        return metadata

    def find_references(
        self,
        file: FileRecord,
        content: ContentRecord,
        context_lines: int = 20
    ) -> List[ReferenceContext]:
        """
        Find references to other files with surrounding context.
        """
        references = []
        text = content.full_text or ""
        lines = text.splitlines()

        if not lines:
            return references

        # Find explicit file references
        references.extend(
            self._find_explicit_references(lines, context_lines)
        )

        # Find short references (000, 001, etc.)
        references.extend(
            self._find_short_references(lines, context_lines)
        )

        return references

    def _find_explicit_references(
        self,
        lines: List[str],
        context_lines: int
    ) -> List[ReferenceContext]:
        """Find explicit filename references."""
        references = []

        for line_num, line in enumerate(lines):
            matches = self.DATA_FILE_PATTERN.findall(line)
            for match in matches:
                # Get context
                start = max(0, line_num - context_lines)
                end = min(len(lines), line_num + context_lines + 1)

                before = lines[start:line_num]
                after = lines[line_num + 1:end]
                full_context = "\n".join(lines[start:end])

                # Extract metadata from context
                metadata = self._extract_context_metadata(full_context)

                references.append(ReferenceContext(
                    reference=match,
                    line_number=line_num + 1,
                    before_lines=before,
                    after_lines=after,
                    full_context=full_context,
                    extracted_metadata=metadata,
                    reference_type="filename",
                    confidence=0.9,  # High confidence for explicit filename
                ))

        return references

    def _find_short_references(
        self,
        lines: List[str],
        context_lines: int
    ) -> List[ReferenceContext]:
        """Find short numeric references (000, 001, etc.)."""
        references = []

        for line_num, line in enumerate(lines):
            matches = self.SHORT_REF_PATTERN.findall(line)
            for match in matches:
                # Skip if this looks like a page number or other noise
                if self._is_likely_noise(line, match):
                    continue

                # Get context
                start = max(0, line_num - context_lines)
                end = min(len(lines), line_num + context_lines + 1)

                before = lines[start:line_num]
                after = lines[line_num + 1:end]
                full_context = "\n".join(lines[start:end])

                # Extract metadata from context
                metadata = self._extract_context_metadata(full_context)

                references.append(ReferenceContext(
                    reference=match,
                    line_number=line_num + 1,
                    before_lines=before,
                    after_lines=after,
                    full_context=full_context,
                    extracted_metadata=metadata,
                    reference_type="short_ref",
                    confidence=0.5,  # Lower confidence for short references
                ))

        return references

    def _extract_context_metadata(self, context: str) -> Dict[str, Any]:
        """Extract metadata from the context around a reference."""
        metadata = {}

        # Extract dates
        dates = []
        for pattern in self.DATE_PATTERNS:
            dates.extend(pattern.findall(context))
        if dates:
            metadata["dates"] = list(set(dates))[:5]

        # Extract animal IDs
        animal_ids = []
        for pattern in self.ANIMAL_ID_PATTERNS:
            animal_ids.extend(pattern.findall(context))
        if animal_ids:
            metadata["animal_ids"] = list(set(animal_ids))[:5]

        return metadata

    def _is_likely_noise(self, line: str, match: str) -> bool:
        """
        Check if a short reference is likely noise (page number, etc.).

        Args:
            line: The line containing the match
            match: The matched reference

        Returns:
            True if this is likely noise
        """
        line_lower = line.lower()

        # Common noise patterns
        noise_indicators = [
            "page",
            "figure",
            "table",
            "section",
            "chapter",
            "version",
            "revision",
        ]

        for indicator in noise_indicators:
            if indicator in line_lower:
                # Check if the number is near the indicator
                idx = line_lower.find(indicator)
                match_idx = line.find(match)
                if abs(match_idx - idx) < 20:
                    return True

        return False

    def get_relationship_hints(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None
    ) -> List[str]:
        """Get relationship hints based on file content."""
        hints = ["notes_for", "mentions", "related_to"]

        if content and content.full_text:
            text_lower = content.full_text.lower()

            # Check for specific document types
            if any(kw in text_lower for kw in ["surgery", "surgical", "procedure"]):
                hints.insert(0, "surgery_notes_for")
            elif any(kw in text_lower for kw in ["protocol", "method", "experiment"]):
                hints.insert(0, "protocol_for")
            elif any(kw in text_lower for kw in ["analysis", "result", "figure"]):
                hints.insert(0, "analysis_of")

        return hints
