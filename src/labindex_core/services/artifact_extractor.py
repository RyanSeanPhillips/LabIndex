"""
Artifact Extractor - Extract sub-document anchors for evidence navigation.

Artifacts are precise locations within documents that provide evidence
for links. When a user clicks on link evidence, they can navigate
directly to the source location.

Supported artifact types:
- text_span: Line range in text files
- table_cell: Specific cell in spreadsheets
- table_row: Entire row in spreadsheets
- ppt_slide: Slide in PowerPoint presentations
- ipynb_cell: Cell in Jupyter notebooks
- pdf_page: Page in PDF documents
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from ..domain.models import Artifact, FileRecord, ContentRecord
from ..domain.enums import FileCategory, ArtifactType
from ..ports.db_port import DBPort


@dataclass
class TextSpanLocator:
    """Locator for text file spans."""
    line_start: int
    line_end: int
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_start": self.line_start,
            "line_end": self.line_end,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


@dataclass
class TableCellLocator:
    """Locator for spreadsheet cells."""
    sheet: str
    row: int
    col: int
    cell_ref: Optional[str] = None  # e.g., "A1", "B5"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sheet": self.sheet,
            "row": self.row,
            "col": self.col,
            "cell_ref": self.cell_ref,
        }


@dataclass
class TableRowLocator:
    """Locator for spreadsheet rows."""
    sheet: str
    row: int
    col_start: int = 0
    col_end: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sheet": self.sheet,
            "row": self.row,
            "col_start": self.col_start,
            "col_end": self.col_end,
        }


@dataclass
class SlideLocator:
    """Locator for PowerPoint slides."""
    slide_number: int
    shape_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_number": self.slide_number,
            "shape_id": self.shape_id,
        }


@dataclass
class NotebookCellLocator:
    """Locator for Jupyter notebook cells."""
    cell_index: int
    cell_type: str = "code"  # code, markdown
    output_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_index": self.cell_index,
            "cell_type": self.cell_type,
            "output_index": self.output_index,
        }


@dataclass
class PDFPageLocator:
    """Locator for PDF pages."""
    page_number: int
    bbox: Optional[Tuple[float, float, float, float]] = None  # x0, y0, x1, y1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "bbox": self.bbox,
        }


class ArtifactExtractor:
    """
    Extract and manage sub-document artifacts for evidence anchoring.

    Artifacts provide click-to-navigate functionality in the UI,
    allowing users to see exactly where linking evidence was found.
    """

    def __init__(self, db: DBPort):
        """Initialize with database access."""
        self.db = db

    def extract_text_span(
        self,
        file_id: int,
        line_start: int,
        line_end: int,
        excerpt: Optional[str] = None
    ) -> Artifact:
        """
        Create an artifact for a text file span.

        Args:
            file_id: ID of the source file
            line_start: Starting line number (1-indexed)
            line_end: Ending line number (inclusive)
            excerpt: Optional text excerpt

        Returns:
            Created Artifact
        """
        locator = TextSpanLocator(line_start=line_start, line_end=line_end)

        artifact = Artifact(
            artifact_id=0,
            file_id=file_id,
            artifact_type=ArtifactType.TEXT_SPAN.value,
            locator=locator.to_dict(),
            excerpt=excerpt,
        )

        return self.db.add_artifact(artifact)

    def extract_table_cell(
        self,
        file_id: int,
        sheet: str,
        row: int,
        col: int,
        excerpt: Optional[str] = None
    ) -> Artifact:
        """
        Create an artifact for a spreadsheet cell.

        Args:
            file_id: ID of the source file
            sheet: Sheet name
            row: Row number (0-indexed)
            col: Column number (0-indexed)
            excerpt: Optional cell content

        Returns:
            Created Artifact
        """
        # Convert to Excel-style cell reference
        col_letter = self._col_to_letter(col)
        cell_ref = f"{col_letter}{row + 1}"

        locator = TableCellLocator(
            sheet=sheet,
            row=row,
            col=col,
            cell_ref=cell_ref,
        )

        artifact = Artifact(
            artifact_id=0,
            file_id=file_id,
            artifact_type=ArtifactType.TABLE_CELL.value,
            locator=locator.to_dict(),
            excerpt=excerpt,
        )

        return self.db.add_artifact(artifact)

    def extract_table_row(
        self,
        file_id: int,
        sheet: str,
        row: int,
        excerpt: Optional[str] = None
    ) -> Artifact:
        """
        Create an artifact for an entire spreadsheet row.

        Args:
            file_id: ID of the source file
            sheet: Sheet name
            row: Row number (0-indexed)
            excerpt: Optional row summary

        Returns:
            Created Artifact
        """
        locator = TableRowLocator(sheet=sheet, row=row)

        artifact = Artifact(
            artifact_id=0,
            file_id=file_id,
            artifact_type=ArtifactType.TABLE_ROW.value,
            locator=locator.to_dict(),
            excerpt=excerpt,
        )

        return self.db.add_artifact(artifact)

    def extract_ppt_slide(
        self,
        file_id: int,
        slide_number: int,
        excerpt: Optional[str] = None
    ) -> Artifact:
        """
        Create an artifact for a PowerPoint slide.

        Args:
            file_id: ID of the source file
            slide_number: Slide number (1-indexed)
            excerpt: Optional slide title or content

        Returns:
            Created Artifact
        """
        locator = SlideLocator(slide_number=slide_number)

        artifact = Artifact(
            artifact_id=0,
            file_id=file_id,
            artifact_type=ArtifactType.PPT_SLIDE.value,
            locator=locator.to_dict(),
            excerpt=excerpt,
        )

        return self.db.add_artifact(artifact)

    def extract_notebook_cell(
        self,
        file_id: int,
        cell_index: int,
        cell_type: str = "code",
        excerpt: Optional[str] = None
    ) -> Artifact:
        """
        Create an artifact for a Jupyter notebook cell.

        Args:
            file_id: ID of the source file
            cell_index: Cell index (0-indexed)
            cell_type: "code" or "markdown"
            excerpt: Optional cell content

        Returns:
            Created Artifact
        """
        locator = NotebookCellLocator(cell_index=cell_index, cell_type=cell_type)

        artifact = Artifact(
            artifact_id=0,
            file_id=file_id,
            artifact_type=ArtifactType.IPYNB_CELL.value,
            locator=locator.to_dict(),
            excerpt=excerpt,
        )

        return self.db.add_artifact(artifact)

    def extract_pdf_page(
        self,
        file_id: int,
        page_number: int,
        excerpt: Optional[str] = None
    ) -> Artifact:
        """
        Create an artifact for a PDF page.

        Args:
            file_id: ID of the source file
            page_number: Page number (1-indexed)
            excerpt: Optional page content

        Returns:
            Created Artifact
        """
        locator = PDFPageLocator(page_number=page_number)

        artifact = Artifact(
            artifact_id=0,
            file_id=file_id,
            artifact_type=ArtifactType.PDF_PAGE.value,
            locator=locator.to_dict(),
            excerpt=excerpt,
        )

        return self.db.add_artifact(artifact)

    def find_text_match(
        self,
        file_id: int,
        search_text: str,
        content: Optional[ContentRecord] = None
    ) -> Optional[Artifact]:
        """
        Find where search text appears in a file and create an artifact.

        Args:
            file_id: ID of the file to search
            search_text: Text to find
            content: Optional pre-loaded content

        Returns:
            Artifact pointing to match location, or None if not found
        """
        if content is None:
            content = self.db.get_content(file_id)

        if not content or not content.full_text:
            return None

        # Find the text
        text = content.full_text
        match = re.search(re.escape(search_text), text, re.IGNORECASE)

        if not match:
            return None

        # Calculate line number
        lines_before = text[:match.start()].count('\n') + 1
        match_lines = search_text.count('\n') + 1

        # Get excerpt with context
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        excerpt = text[start:end].strip()
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."

        return self.extract_text_span(
            file_id=file_id,
            line_start=lines_before,
            line_end=lines_before + match_lines - 1,
            excerpt=excerpt,
        )

    def get_artifacts_for_file(self, file_id: int) -> List[Artifact]:
        """Get all artifacts for a file."""
        return self.db.list_artifacts_for_file(file_id)

    def get_artifact(self, artifact_id: int) -> Optional[Artifact]:
        """Get a specific artifact."""
        return self.db.get_artifact(artifact_id)

    def delete_artifact(self, artifact_id: int) -> bool:
        """Delete an artifact."""
        return self.db.delete_artifact(artifact_id)

    def format_locator_for_display(self, artifact: Artifact) -> str:
        """
        Format artifact locator for display in UI.

        Args:
            artifact: Artifact to format

        Returns:
            Human-readable location string
        """
        locator = artifact.locator
        artifact_type = artifact.artifact_type

        if artifact_type == ArtifactType.TEXT_SPAN.value:
            start = locator.get("line_start", 0)
            end = locator.get("line_end", start)
            if start == end:
                return f"Line {start}"
            return f"Lines {start}-{end}"

        elif artifact_type == ArtifactType.TABLE_CELL.value:
            sheet = locator.get("sheet", "Sheet1")
            cell_ref = locator.get("cell_ref", "A1")
            return f"{sheet}!{cell_ref}"

        elif artifact_type == ArtifactType.TABLE_ROW.value:
            sheet = locator.get("sheet", "Sheet1")
            row = locator.get("row", 0) + 1
            return f"{sheet}, Row {row}"

        elif artifact_type == ArtifactType.PPT_SLIDE.value:
            slide = locator.get("slide_number", 1)
            return f"Slide {slide}"

        elif artifact_type == ArtifactType.IPYNB_CELL.value:
            index = locator.get("cell_index", 0)
            cell_type = locator.get("cell_type", "code")
            return f"Cell [{index}] ({cell_type})"

        elif artifact_type == ArtifactType.PDF_PAGE.value:
            page = locator.get("page_number", 1)
            return f"Page {page}"

        return "Unknown location"

    def _col_to_letter(self, col: int) -> str:
        """Convert 0-indexed column number to Excel-style letter(s)."""
        result = ""
        while col >= 0:
            result = chr(65 + (col % 26)) + result
            col = col // 26 - 1
        return result
