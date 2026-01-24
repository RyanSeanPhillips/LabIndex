"""
Text extractors for Tier 1 content indexing.

Extracts searchable text from various document formats.
"""

from .base import TextExtractor, ExtractionResult
from .registry import ExtractorRegistry, get_extractor

__all__ = [
    'TextExtractor',
    'ExtractionResult',
    'ExtractorRegistry',
    'get_extractor',
]
