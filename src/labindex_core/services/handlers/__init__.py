"""
File Type Handlers for the Adaptive Linking System.

This module provides extensible handlers for different file types,
enabling intelligent reference detection and metadata extraction.

Core Classes:
- FileTypeHandler: Abstract base class for all handlers
- HandlerRegistry: Manages and routes files to handlers
- ReferenceContext: Context around a found reference
- ContentSignature: Keywords that identify file types

Built-in Handlers:
- GenericTextHandler: Fallback for text files
- GenericDataHandler: For scientific data files (ABF, SMRX, etc.)
- SpreadsheetHandler: For Excel/CSV with column parsing
- PhotometryDataHandler: Specialized for fiber photometry

Usage:
    from labindex_core.services.handlers import (
        create_default_registry,
        HandlerRegistry,
        ReferenceContext,
    )

    # Create registry with default handlers
    registry = create_default_registry()

    # Find best handler for a file
    handler = registry.get_handler(file_record, content_record)

    # Extract references with context
    if handler:
        references = handler.find_references(file_record, content_record)
"""

from .base import (
    FileTypeHandler,
    HandlerRegistry,
    ReferenceContext,
    ContentSignature,
    create_default_registry,
)

from .generic_text import GenericTextHandler
from .generic_data import GenericDataHandler, PhotometryDataHandler
from .spreadsheet import SpreadsheetHandler


__all__ = [
    # Base classes
    "FileTypeHandler",
    "HandlerRegistry",
    "ReferenceContext",
    "ContentSignature",
    "create_default_registry",
    # Handlers
    "GenericTextHandler",
    "GenericDataHandler",
    "PhotometryDataHandler",
    "SpreadsheetHandler",
]
