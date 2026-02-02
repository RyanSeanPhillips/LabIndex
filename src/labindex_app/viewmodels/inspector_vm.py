"""
Inspector ViewModel for the file details panel.

Manages:
- Selected file information
- Extracted content
- Related files
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from PyQt6.QtCore import pyqtSignal

from .base import BaseViewModel
from labindex_core.ports.db_port import DBPort
from labindex_core.domain.models import FileRecord, ContentRecord, Edge


@dataclass
class RelatedFile:
    """A file related to the inspected file."""
    file_id: int
    name: str
    path: str
    direction: str  # "to" or "from"
    relation_type: str
    confidence: float
    evidence: str


class InspectorVM(BaseViewModel):
    """
    ViewModel for file inspection panel.

    Signals:
        file_changed: Emitted when inspected file changes
        content_loaded: Emitted when content is loaded

    State:
        file: Currently inspected file record
        content: Extracted content for the file
        related_files: List of related files (edges)
    """

    # Signals
    file_changed = pyqtSignal()
    content_loaded = pyqtSignal()

    def __init__(self, db: DBPort):
        """
        Initialize the ViewModel.

        Args:
            db: Database adapter
        """
        super().__init__()

        self._db = db

        # State
        self._file: Optional[FileRecord] = None
        self._content: Optional[ContentRecord] = None
        self._related_files: List[RelatedFile] = []
        self._root_path: Optional[str] = None

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def file(self) -> Optional[FileRecord]:
        """Get the currently inspected file."""
        return self._file

    @property
    def content(self) -> Optional[ContentRecord]:
        """Get the extracted content."""
        return self._content

    @property
    def related_files(self) -> List[RelatedFile]:
        """Get related files."""
        return self._related_files.copy()

    @property
    def has_file(self) -> bool:
        """Check if a file is loaded."""
        return self._file is not None

    @property
    def full_path(self) -> Optional[str]:
        """Get the full filesystem path."""
        if self._file and self._root_path:
            return str(Path(self._root_path) / self._file.path)
        return None

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def load_file(self, file_id: int, root_path: Optional[str] = None) -> bool:
        """
        Load a file for inspection.

        Args:
            file_id: ID of file to inspect
            root_path: Root path for building full path

        Returns:
            True if file was loaded
        """
        self._file = self._db.get_file(file_id)
        if not self._file:
            self.clear()
            return False

        self._root_path = root_path

        # Load content
        self._content = self._db.get_content(file_id)

        # Load related files
        self._load_related_files(file_id)

        self.file_changed.emit()
        self.content_loaded.emit()
        return True

    def clear(self) -> None:
        """Clear the inspector."""
        self._file = None
        self._content = None
        self._related_files = []
        self._root_path = None
        self.file_changed.emit()

    def open_file_external(self) -> bool:
        """
        Open the file in the default application.

        Returns:
            True if file was opened
        """
        import os

        full_path = self.full_path
        if full_path and Path(full_path).exists():
            os.startfile(full_path)
            return True
        return False

    def open_folder_external(self) -> bool:
        """
        Open the containing folder in file explorer.

        Returns:
            True if folder was opened
        """
        import os
        import subprocess

        full_path = self.full_path
        if full_path:
            folder = str(Path(full_path).parent)
            if Path(folder).exists():
                # Windows: explorer with /select
                subprocess.Popen(f'explorer /select,"{full_path}"')
                return True
        return False

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _load_related_files(self, file_id: int) -> None:
        """Load related files from edges."""
        self._related_files = []

        # Edges from this file
        edges_from = self._db.get_edges_from(file_id)
        for edge in sorted(edges_from, key=lambda e: e.confidence, reverse=True):
            other = self._db.get_file(edge.dst_file_id)
            if other:
                self._related_files.append(RelatedFile(
                    file_id=other.file_id,
                    name=other.name,
                    path=other.path,
                    direction="to",
                    relation_type=edge.relation_type.value,
                    confidence=edge.confidence,
                    evidence=edge.evidence or "",
                ))

        # Edges to this file
        edges_to = self._db.get_edges_to(file_id)
        for edge in sorted(edges_to, key=lambda e: e.confidence, reverse=True):
            other = self._db.get_file(edge.src_file_id)
            if other:
                self._related_files.append(RelatedFile(
                    file_id=other.file_id,
                    name=other.name,
                    path=other.path,
                    direction="from",
                    relation_type=edge.relation_type.value,
                    confidence=edge.confidence,
                    evidence=edge.evidence or "",
                ))

    # -------------------------------------------------------------------------
    # Display Helpers
    # -------------------------------------------------------------------------

    def format_size(self) -> str:
        """Format file size for display."""
        if not self._file:
            return ""

        size = self._file.size_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        else:
            return f"{size / 1024 / 1024 / 1024:.1f} GB"

    def build_details_html(self) -> str:
        """Build HTML content for file details dialog."""
        if not self._file:
            return ""

        html = f"""
        <h2>{self._file.name}</h2>
        <p><b>Path:</b> {self._file.path}</p>
        <p><b>Category:</b> {self._file.category.value}</p>
        <p><b>Size:</b> {self.format_size()}</p>
        <p><b>Status:</b> {self._file.status.value}</p>
        """

        # Extracted content
        if self._content and self._content.full_text:
            preview = self._content.full_text[:2000]
            if len(self._content.full_text) > 2000:
                preview += f"\n\n... ({len(self._content.full_text):,} chars total)"
            html += f"""
            <h3>Extracted Content</h3>
            <pre style="background: #2d2d30; padding: 8px; white-space: pre-wrap;">{preview}</pre>
            """

        # Related files
        if self._related_files:
            html += "<h3>Related Files</h3><ul>"
            for rel in self._related_files:
                arrow = "→" if rel.direction == "to" else "←"
                html += f"<li>{arrow} <b>{rel.name}</b> ({rel.relation_type}, {rel.confidence:.0%})"
                if rel.evidence:
                    html += f" - {rel.evidence}"
                html += "</li>"
            html += "</ul>"

        return html
