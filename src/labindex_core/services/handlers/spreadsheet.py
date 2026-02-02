"""
Spreadsheet file handler.

Handles Excel and CSV files with intelligent column parsing.
Particularly good at finding:
- Data file references in "file" columns
- Animal/subject ID columns
- Date columns
- Session/recording metadata
"""

import re
from typing import List, Dict, Optional, Any, Set, Tuple

from .base import FileTypeHandler, ReferenceContext, ContentSignature
from ...domain.models import FileRecord, ContentRecord
from ...domain.enums import FileCategory


class SpreadsheetHandler(FileTypeHandler):
    """
    Handler for spreadsheet files (Excel, CSV).

    Spreadsheets are often used as metadata logs that link to data files.
    This handler:
    1. Parses extracted text looking for table structure
    2. Identifies columns that likely contain file references
    3. Extracts references with row context (other columns in same row)
    """

    name = "spreadsheet"
    description = "Handler for Excel/CSV files with column parsing"
    file_extensions = {"csv", "xlsx", "xls", "tsv"}
    file_categories = {FileCategory.SPREADSHEETS}

    # Column headers that likely contain file references
    FILE_COLUMN_PATTERNS = [
        re.compile(r'(?:pleth|data|recording|abf|file)[_\s]*(file|name)?', re.IGNORECASE),
        re.compile(r'filename', re.IGNORECASE),
    ]

    # Column headers for animal IDs
    ANIMAL_COLUMN_PATTERNS = [
        re.compile(r'(?:animal|mouse|rat|subject)[_\s]*(id)?', re.IGNORECASE),
        re.compile(r'\bid\b', re.IGNORECASE),
    ]

    # Column headers for dates
    DATE_COLUMN_PATTERNS = [
        re.compile(r'date', re.IGNORECASE),
        re.compile(r'(?:recording|surgery|experiment)[_\s]*date', re.IGNORECASE),
    ]

    # Column headers for notes/comments
    NOTES_COLUMN_PATTERNS = [
        re.compile(r'(?:notes?|comments?|description)', re.IGNORECASE),
    ]

    # Data file pattern in cells
    DATA_FILE_PATTERN = re.compile(
        r'\b([\w\-]+\.(?:abf|smrx|smr|edf|mat|nwb|h5))\b',
        re.IGNORECASE
    )

    # Short reference pattern in cells
    SHORT_REF_PATTERN = re.compile(r'^(\d{3})$')

    def can_handle(self, file: FileRecord, content: Optional[ContentRecord] = None) -> float:
        """Check if this handler applies to the file."""
        # Check extension
        if self._check_extension(file):
            return 0.9

        # Check category
        if file.category == FileCategory.SPREADSHEETS:
            return 0.85

        return 0.0

    def extract_metadata(
        self,
        file: FileRecord,
        content: ContentRecord
    ) -> Dict[str, Any]:
        """
        Extract metadata from spreadsheet.

        Returns:
        - columns: Detected column headers
        - row_count: Estimated number of data rows
        - has_file_column: Whether a file reference column was found
        - has_animal_column: Whether an animal ID column was found
        - has_date_column: Whether a date column was found
        """
        metadata = {
            "columns": [],
            "row_count": 0,
            "has_file_column": False,
            "has_animal_column": False,
            "has_date_column": False,
            "column_mappings": {},  # column_name -> column_type
        }

        if not content or not content.full_text:
            return metadata

        # Try to parse table structure
        lines = content.full_text.splitlines()
        if not lines:
            return metadata

        # Find potential header row (usually first non-empty row)
        header_line = None
        for line in lines[:5]:  # Check first 5 lines
            if line.strip():
                header_line = line
                break

        if not header_line:
            return metadata

        # Split by common delimiters
        columns = self._split_row(header_line)
        metadata["columns"] = columns

        # Classify columns
        for col in columns:
            col_lower = col.lower().strip()
            col_type = self._classify_column(col)
            if col_type:
                metadata["column_mappings"][col] = col_type
                if col_type == "file":
                    metadata["has_file_column"] = True
                elif col_type == "animal_id":
                    metadata["has_animal_column"] = True
                elif col_type == "date":
                    metadata["has_date_column"] = True

        # Count data rows
        metadata["row_count"] = max(0, len(lines) - 1)

        return metadata

    def find_references(
        self,
        file: FileRecord,
        content: ContentRecord,
        context_lines: int = 20
    ) -> List[ReferenceContext]:
        """
        Find file references in spreadsheet with row context.

        For spreadsheets, context is the entire row containing the reference,
        which includes related metadata (animal ID, date, notes, etc.).
        """
        references = []

        if not content or not content.full_text:
            return references

        lines = content.full_text.splitlines()
        if len(lines) < 2:
            return references

        # Parse header
        header = self._split_row(lines[0])

        # Find file column index
        file_col_idx = self._find_file_column(header)

        # Classify all columns for metadata extraction
        column_types = {i: self._classify_column(col) for i, col in enumerate(header)}

        # Process data rows
        for line_num, line in enumerate(lines[1:], start=2):
            if not line.strip():
                continue

            cells = self._split_row(line)

            # Look for file references
            refs_in_row = self._find_references_in_row(cells, header, file_col_idx)

            for ref, col_idx in refs_in_row:
                # Build row context (metadata from other columns)
                row_metadata = self._extract_row_metadata(cells, header, column_types)

                # Get surrounding rows for additional context
                start = max(1, line_num - context_lines)
                end = min(len(lines), line_num + context_lines)
                full_context = "\n".join(lines[start-1:end])

                # Determine reference type and confidence
                ref_type = "cell_filename" if "." in ref else "cell_short_ref"
                confidence = 0.85 if ref_type == "cell_filename" else 0.6

                # Boost confidence if from identified file column
                if col_idx == file_col_idx:
                    confidence = min(confidence + 0.1, 0.95)

                references.append(ReferenceContext(
                    reference=ref,
                    line_number=line_num,
                    before_lines=lines[max(0, line_num-3):line_num-1],
                    after_lines=lines[line_num:min(len(lines), line_num+2)],
                    full_context=full_context,
                    extracted_metadata=row_metadata,
                    reference_type=ref_type,
                    confidence=confidence,
                ))

        return references

    def _split_row(self, line: str) -> List[str]:
        """
        Split a row into cells.

        Handles common delimiters: comma, tab, pipe.
        """
        # Try tab first (common in extracted Excel)
        if "\t" in line:
            return [c.strip() for c in line.split("\t")]

        # Try comma (but be careful of quoted values)
        if "," in line:
            # Simple split - doesn't handle quoted commas
            return [c.strip().strip('"') for c in line.split(",")]

        # Try pipe
        if "|" in line:
            return [c.strip() for c in line.split("|")]

        # Fallback: split on multiple spaces
        return [c.strip() for c in re.split(r'\s{2,}', line)]

    def _classify_column(self, header: str) -> Optional[str]:
        """
        Classify a column by its header.

        Returns: "file", "animal_id", "date", "notes", or None
        """
        header = header.strip()

        for pattern in self.FILE_COLUMN_PATTERNS:
            if pattern.search(header):
                return "file"

        for pattern in self.ANIMAL_COLUMN_PATTERNS:
            if pattern.search(header):
                return "animal_id"

        for pattern in self.DATE_COLUMN_PATTERNS:
            if pattern.search(header):
                return "date"

        for pattern in self.NOTES_COLUMN_PATTERNS:
            if pattern.search(header):
                return "notes"

        return None

    def _find_file_column(self, header: List[str]) -> Optional[int]:
        """Find the index of the file reference column."""
        for i, col in enumerate(header):
            for pattern in self.FILE_COLUMN_PATTERNS:
                if pattern.search(col):
                    return i
        return None

    def _find_references_in_row(
        self,
        cells: List[str],
        header: List[str],
        file_col_idx: Optional[int]
    ) -> List[Tuple[str, int]]:
        """
        Find file references in a row.

        Returns list of (reference, column_index) tuples.
        """
        references = []

        for col_idx, cell in enumerate(cells):
            cell = cell.strip()
            if not cell:
                continue

            # Check for explicit filename
            match = self.DATA_FILE_PATTERN.search(cell)
            if match:
                references.append((match.group(1), col_idx))
                continue

            # Check for short reference (only in file column or if looks like sequence)
            if file_col_idx is not None and col_idx == file_col_idx:
                short_match = self.SHORT_REF_PATTERN.match(cell)
                if short_match:
                    references.append((short_match.group(1), col_idx))

        return references

    def _extract_row_metadata(
        self,
        cells: List[str],
        header: List[str],
        column_types: Dict[int, Optional[str]]
    ) -> Dict[str, Any]:
        """
        Extract metadata from a row based on column classifications.
        """
        metadata = {}

        for col_idx, cell in enumerate(cells):
            col_type = column_types.get(col_idx)
            if not col_type or not cell.strip():
                continue

            cell = cell.strip()

            if col_type == "animal_id":
                metadata["animal_id"] = cell
            elif col_type == "date":
                metadata["date"] = cell
            elif col_type == "notes":
                metadata["notes"] = cell[:200]  # Limit length

        # Also include column headers for context
        if header:
            metadata["row_header"] = " | ".join(header[:10])

        return metadata

    def get_relationship_hints(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None
    ) -> List[str]:
        """Spreadsheets are typically metadata/logs for data files."""
        return ["notes_for", "metadata_for", "log_for"]
