"""
Extractor registry - manages available text extractors.
"""

from pathlib import Path
from typing import Dict, Optional, List, Type

from .base import TextExtractor, ExtractionResult


class ExtractorRegistry:
    """Registry of available text extractors.

    Maps file extensions to extractors and provides a unified interface.
    """

    def __init__(self):
        self._extractors: Dict[str, TextExtractor] = {}
        self._register_default_extractors()

    def _register_default_extractors(self):
        """Register all built-in extractors."""
        # Import here to avoid circular imports
        from .text_extractor import PlainTextExtractor
        from .excel_extractor import ExcelExtractor
        from .word_extractor import WordExtractor
        from .pdf_extractor import PDFExtractor
        from .pptx_extractor import PowerPointExtractor

        # Document extractors (always available)
        document_extractors = [
            PlainTextExtractor,
            ExcelExtractor,
            WordExtractor,
            PDFExtractor,
            PowerPointExtractor,
        ]

        # Data file extractors (may not have dependencies installed)
        data_extractors = []

        # ABF extractor (requires pyabf)
        try:
            from .abf_extractor import ABFExtractor
            data_extractors.append(ABFExtractor)
        except ImportError:
            pass

        # SMRX extractor (requires sonpy)
        try:
            from .smrx_extractor import SMRXExtractor
            data_extractors.append(SMRXExtractor)
        except ImportError:
            pass

        # NPZ extractor (requires numpy - usually available)
        try:
            from .npz_extractor import NPZExtractor
            data_extractors.append(NPZExtractor)
        except ImportError:
            pass

        # Register all extractors
        for extractor_class in document_extractors + data_extractors:
            extractor = extractor_class()
            for ext in extractor.EXTENSIONS:
                self._extractors[ext.lower()] = extractor

    def register(self, extractor: TextExtractor):
        """Register a custom extractor."""
        for ext in extractor.EXTENSIONS:
            self._extractors[ext.lower()] = extractor

    def get_extractor(self, path: Path) -> Optional[TextExtractor]:
        """Get the extractor for a file path."""
        ext = path.suffix.lower()
        return self._extractors.get(ext)

    def can_extract(self, path: Path) -> bool:
        """Check if we can extract text from this file."""
        return self.get_extractor(path) is not None

    def extract(self, path: Path) -> ExtractionResult:
        """Extract text from a file using the appropriate extractor."""
        extractor = self.get_extractor(path)
        if extractor is None:
            return ExtractionResult.failure(f"No extractor for {path.suffix}")
        return extractor.extract(path)

    def supported_extensions(self) -> List[str]:
        """List all supported extensions."""
        return sorted(self._extractors.keys())


# Global registry instance
_registry: Optional[ExtractorRegistry] = None


def get_registry() -> ExtractorRegistry:
    """Get the global extractor registry."""
    global _registry
    if _registry is None:
        _registry = ExtractorRegistry()
    return _registry


def get_extractor(path: Path) -> Optional[TextExtractor]:
    """Convenience function to get extractor for a path."""
    return get_registry().get_extractor(path)


def extract_text(path: Path) -> ExtractionResult:
    """Convenience function to extract text from a file."""
    return get_registry().extract(path)
