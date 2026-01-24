"""
PDF document extractor.

Handles .pdf files using PyMuPDF (fitz) or pdfplumber.
"""

from pathlib import Path
from typing import List

from .base import TextExtractor, ExtractionResult


class PDFExtractor(TextExtractor):
    """Extract text from PDF documents."""

    EXTENSIONS = ['.pdf']

    def _extract_impl(self, path: Path) -> ExtractionResult:
        """Extract text from PDF."""
        # Try PyMuPDF first (faster), fall back to pdfplumber
        result = self._extract_with_fitz(path)
        if result.success:
            return result

        return self._extract_with_pdfplumber(path)

    def _extract_with_fitz(self, path: Path) -> ExtractionResult:
        """Extract using PyMuPDF (fitz)."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ExtractionResult.failure("PyMuPDF not installed")

        try:
            doc = fitz.open(path)

            all_text: List[str] = []
            sources = {}

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text().strip()
                if text:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                    sources[f"page_{page_num + 1}"] = text[:500]

            doc.close()

            return ExtractionResult(
                text='\n\n'.join(all_text),
                metadata={'page_count': len(doc)},
                sources=sources
            )

        except Exception as e:
            return ExtractionResult.failure(f"PyMuPDF error: {e}")

    def _extract_with_pdfplumber(self, path: Path) -> ExtractionResult:
        """Extract using pdfplumber (fallback)."""
        try:
            import pdfplumber
        except ImportError:
            return ExtractionResult.failure("Neither PyMuPDF nor pdfplumber installed")

        try:
            all_text: List[str] = []
            sources = {}

            with pdfplumber.open(path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        text = text.strip()
                        all_text.append(f"[Page {page_num + 1}]\n{text}")
                        sources[f"page_{page_num + 1}"] = text[:500]

            return ExtractionResult(
                text='\n\n'.join(all_text),
                metadata={'page_count': len(all_text)},
                sources=sources
            )

        except Exception as e:
            return ExtractionResult.failure(f"pdfplumber error: {e}")
