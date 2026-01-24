"""
Base classes for text extraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class ExtractionResult:
    """Result of text extraction from a file."""

    # Extracted text content (for FTS indexing)
    text: str

    # Structured metadata extracted (optional)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Whether extraction was successful
    success: bool = True

    # Error message if extraction failed
    error: Optional[str] = None

    # Source locations for provenance (sheet/page/section -> text)
    sources: Dict[str, str] = field(default_factory=dict)

    @property
    def text_length(self) -> int:
        """Length of extracted text."""
        return len(self.text)

    @classmethod
    def failure(cls, error: str) -> 'ExtractionResult':
        """Create a failed extraction result."""
        return cls(text="", success=False, error=error)

    @classmethod
    def empty(cls) -> 'ExtractionResult':
        """Create an empty but successful result."""
        return cls(text="", success=True)


class TextExtractor(ABC):
    """Base class for text extractors.

    Each extractor handles one or more file extensions.
    Extractors are stateless and should be thread-safe.
    """

    # File extensions this extractor handles (lowercase, with dot)
    EXTENSIONS: List[str] = []

    # Maximum file size to extract (bytes) - 50MB default
    MAX_FILE_SIZE: int = 50 * 1024 * 1024

    # Maximum text length to return - 1MB of text
    MAX_TEXT_LENGTH: int = 1024 * 1024

    def can_extract(self, path: Path) -> bool:
        """Check if this extractor can handle the given file."""
        return path.suffix.lower() in self.EXTENSIONS

    def extract(self, path: Path) -> ExtractionResult:
        """Extract text from a file.

        This is the main entry point. It handles size checks
        and delegates to _extract_impl for the actual work.
        """
        try:
            # Check file exists
            if not path.exists():
                return ExtractionResult.failure(f"File not found: {path}")

            # Check file size
            size = path.stat().st_size
            if size > self.MAX_FILE_SIZE:
                return ExtractionResult.failure(
                    f"File too large: {size / 1024 / 1024:.1f}MB > {self.MAX_FILE_SIZE / 1024 / 1024:.1f}MB limit"
                )

            if size == 0:
                return ExtractionResult.empty()

            # Do the actual extraction
            result = self._extract_impl(path)

            # Truncate if too long
            if result.success and len(result.text) > self.MAX_TEXT_LENGTH:
                result.text = result.text[:self.MAX_TEXT_LENGTH]

            return result

        except Exception as e:
            return ExtractionResult.failure(f"Extraction error: {e}")

    @abstractmethod
    def _extract_impl(self, path: Path) -> ExtractionResult:
        """Implement the actual extraction logic.

        Subclasses must implement this method.
        """
        pass
