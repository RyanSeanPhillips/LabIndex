"""
Base classes for the extensible file type handler system.

The handler system provides:
1. FileTypeHandler ABC - Interface for all file type handlers
2. HandlerRegistry - Manages and routes files to appropriate handlers
3. ReferenceContext - Context around found references
4. ContentSignature - Keywords that identify file types
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any, Set

from ...domain.models import FileRecord, ContentRecord
from ...domain.enums import FileCategory


@dataclass
class ReferenceContext:
    """Context around a found reference in a file."""

    reference: str                      # The reference text (e.g., "000.abf" or "FP_data_1")
    line_number: int                    # Line where reference was found
    before_lines: List[str]             # N lines before the reference
    after_lines: List[str]              # N lines after the reference
    full_context: str                   # Combined text for analysis
    extracted_metadata: Dict[str, Any] = field(default_factory=dict)  # Parsed from context
    reference_type: str = "unknown"     # "filename", "short_ref", "folder", "id"
    confidence: float = 1.0             # How confident we are this is a real reference

    @property
    def context_summary(self) -> str:
        """Get a short summary of the context."""
        return self.full_context[:200] if len(self.full_context) > 200 else self.full_context


@dataclass
class ContentSignature:
    """
    Keywords that identify a file type.

    Used to automatically detect file types based on content patterns.
    """
    keywords: List[str]                     # Keywords to look for
    keyword_weights: Dict[str, float] = field(default_factory=dict)  # Optional weights
    required_count: int = 2                 # How many keywords must be present
    confidence_boost: float = 0.2           # How much this boosts file type confidence

    def score(self, content: str) -> float:
        """
        Score content against this signature.

        Args:
            content: Text content to score

        Returns:
            Score between 0.0 and confidence_boost
        """
        content_lower = content.lower()

        if self.keyword_weights:
            # Weighted scoring
            total_weight = 0.0
            for keyword, weight in self.keyword_weights.items():
                if keyword.lower() in content_lower:
                    total_weight += weight
            # Normalize by max possible weight
            max_weight = sum(self.keyword_weights.values())
            if max_weight > 0:
                return (total_weight / max_weight) * self.confidence_boost
            return 0.0
        else:
            # Simple count-based scoring
            matches = sum(1 for kw in self.keywords if kw.lower() in content_lower)
            if matches >= self.required_count:
                return self.confidence_boost * min(1.0, matches / len(self.keywords))
            return 0.0


class FileTypeHandler(ABC):
    """
    Base class for all file type handlers.

    Handlers are responsible for:
    1. Identifying if they can handle a file
    2. Extracting metadata specific to the file type
    3. Finding references to other files with context
    4. Suggesting relationship types
    """

    # Handler metadata (should be overridden by subclasses)
    name: str = "base_handler"
    description: str = "Base handler"
    file_patterns: List[str] = []           # Glob patterns: ["*.csv", "FP_data*"]
    file_extensions: Set[str] = set()       # Extensions: {"txt", "csv"}
    file_categories: Set[FileCategory] = set()  # Categories this handler supports
    content_signatures: List[ContentSignature] = []  # Content patterns

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the handler.

        Args:
            config: Optional configuration dict
        """
        self.config = config or {}

    @abstractmethod
    def can_handle(self, file: FileRecord, content: Optional[ContentRecord] = None) -> float:
        """
        Return confidence 0-1 that this handler applies to the file.

        Args:
            file: File record to check
            content: Optional content record for deeper analysis

        Returns:
            Confidence score between 0.0 and 1.0
        """
        pass

    @abstractmethod
    def extract_metadata(
        self,
        file: FileRecord,
        content: ContentRecord
    ) -> Dict[str, Any]:
        """
        Extract structured metadata specific to this file type.

        Args:
            file: File record
            content: Content record with extracted text

        Returns:
            Dict of extracted metadata (varies by handler)
        """
        pass

    @abstractmethod
    def find_references(
        self,
        file: FileRecord,
        content: ContentRecord,
        context_lines: int = 20
    ) -> List[ReferenceContext]:
        """
        Find references to other files with surrounding context.

        Args:
            file: File record
            content: Content record with extracted text
            context_lines: Number of lines before/after to include

        Returns:
            List of ReferenceContext objects
        """
        pass

    def get_relationship_hints(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None
    ) -> List[str]:
        """
        What relationship types might this file have?

        Default implementation returns common relationships.
        Subclasses can override for more specific hints.

        Args:
            file: File record
            content: Optional content record

        Returns:
            List of relationship type names
        """
        return ["notes_for", "related_to", "mentions"]

    def _score_by_signatures(self, content: str) -> float:
        """
        Score content against all content signatures.

        Args:
            content: Text content to score

        Returns:
            Total signature score (0.0 to 1.0)
        """
        if not self.content_signatures:
            return 0.0

        total_score = sum(sig.score(content) for sig in self.content_signatures)
        return min(1.0, total_score)

    def _check_patterns(self, file: FileRecord) -> bool:
        """
        Check if file matches any of the handler's patterns.

        Args:
            file: File record to check

        Returns:
            True if any pattern matches
        """
        from fnmatch import fnmatch

        for pattern in self.file_patterns:
            if fnmatch(file.name.lower(), pattern.lower()):
                return True
            if fnmatch(file.path.lower(), pattern.lower()):
                return True
        return False

    def _check_extension(self, file: FileRecord) -> bool:
        """
        Check if file extension matches handler's supported extensions.

        Args:
            file: File record to check

        Returns:
            True if extension matches
        """
        if not self.file_extensions:
            return False
        return file.ext.lower() in self.file_extensions

    def _check_category(self, file: FileRecord) -> bool:
        """
        Check if file category matches handler's supported categories.

        Args:
            file: File record to check

        Returns:
            True if category matches
        """
        if not self.file_categories:
            return False
        return file.category in self.file_categories


class HandlerRegistry:
    """
    Manages available handlers and routes files to appropriate handlers.

    The registry maintains a list of handlers ordered by priority.
    When asked to handle a file, it finds the best-matching handler
    (highest confidence) from all registered handlers.
    """

    def __init__(self):
        """Initialize the registry."""
        self._handlers: List[FileTypeHandler] = []
        self._handler_names: Set[str] = set()

    def register(self, handler: FileTypeHandler) -> None:
        """
        Register a handler.

        Args:
            handler: Handler to register

        Raises:
            ValueError: If handler with same name already registered
        """
        if handler.name in self._handler_names:
            raise ValueError(f"Handler '{handler.name}' already registered")

        self._handlers.append(handler)
        self._handler_names.add(handler.name)

    def unregister(self, name: str) -> bool:
        """
        Unregister a handler by name.

        Args:
            name: Name of handler to unregister

        Returns:
            True if handler was found and removed
        """
        for i, handler in enumerate(self._handlers):
            if handler.name == name:
                del self._handlers[i]
                self._handler_names.discard(name)
                return True
        return False

    def get_handler(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None
    ) -> Optional[FileTypeHandler]:
        """
        Find the best-matching handler for a file.

        Args:
            file: File record to match
            content: Optional content record for deeper analysis

        Returns:
            Best matching handler, or None if no handler applies
        """
        best_handler = None
        best_confidence = 0.0

        for handler in self._handlers:
            confidence = handler.can_handle(file, content)
            if confidence > best_confidence:
                best_confidence = confidence
                best_handler = handler

        # Only return if confidence is above threshold
        if best_confidence >= 0.1:
            return best_handler
        return None

    def get_all_matching_handlers(
        self,
        file: FileRecord,
        content: Optional[ContentRecord] = None,
        min_confidence: float = 0.1
    ) -> List[tuple]:
        """
        Get all handlers that can handle a file with their confidence scores.

        Args:
            file: File record to match
            content: Optional content record
            min_confidence: Minimum confidence threshold

        Returns:
            List of (handler, confidence) tuples, sorted by confidence descending
        """
        matches = []
        for handler in self._handlers:
            confidence = handler.can_handle(file, content)
            if confidence >= min_confidence:
                matches.append((handler, confidence))

        return sorted(matches, key=lambda x: x[1], reverse=True)

    def list_handlers(self) -> List[Dict[str, Any]]:
        """
        List all registered handlers.

        Returns:
            List of handler info dicts
        """
        return [
            {
                "name": h.name,
                "description": h.description,
                "patterns": h.file_patterns,
                "extensions": list(h.file_extensions),
            }
            for h in self._handlers
        ]

    @property
    def handler_count(self) -> int:
        """Get number of registered handlers."""
        return len(self._handlers)


def create_default_registry() -> HandlerRegistry:
    """
    Create a registry with default handlers.

    Returns:
        HandlerRegistry with generic handlers pre-registered
    """
    from .generic_text import GenericTextHandler
    from .generic_data import GenericDataHandler
    from .spreadsheet import SpreadsheetHandler

    registry = HandlerRegistry()

    # Register handlers in order of specificity (most specific first)
    registry.register(SpreadsheetHandler())
    registry.register(GenericDataHandler())
    registry.register(GenericTextHandler())  # Fallback handler last

    return registry
