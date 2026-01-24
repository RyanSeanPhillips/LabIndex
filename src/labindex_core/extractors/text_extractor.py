"""
Plain text file extractor.

Handles .txt, .md, .csv, .log, .json, .xml, .html, .py, .m, .r, etc.
"""

from pathlib import Path

from .base import TextExtractor, ExtractionResult


class PlainTextExtractor(TextExtractor):
    """Extract text from plain text files."""

    EXTENSIONS = [
        # Text files
        '.txt', '.md', '.rst', '.log',
        # Data formats
        '.csv', '.tsv', '.json', '.xml', '.yaml', '.yml',
        # Code files
        '.py', '.m', '.r', '.js', '.html', '.css',
        '.c', '.cpp', '.h', '.hpp', '.java',
        # Config files
        '.ini', '.cfg', '.conf', '.toml',
    ]

    # Text files can be read even if large
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    def _extract_impl(self, path: Path) -> ExtractionResult:
        """Read text file contents."""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                text = path.read_text(encoding=encoding)
                return ExtractionResult(
                    text=text,
                    metadata={'encoding': encoding},
                    sources={'file': text[:500]}  # First 500 chars as preview
                )
            except UnicodeDecodeError:
                continue

        return ExtractionResult.failure("Could not decode text with any supported encoding")
