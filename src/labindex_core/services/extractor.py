"""
Extraction Service - orchestrates text extraction from files.

This service:
1. Finds files that need extraction
2. Uses the appropriate extractor for each file type
3. Stores extracted content in the database
4. Updates FTS index for search
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from ..domain.models import FileRecord, ContentRecord
from ..domain.enums import IndexStatus, FileCategory
from ..ports.db_port import DBPort
from ..ports.fs_port import FSPort
from ..extractors.registry import get_registry, ExtractorRegistry


@dataclass
class ExtractionProgress:
    """Progress info for extraction callbacks."""
    files_processed: int
    files_total: int
    current_file: str
    success_count: int
    error_count: int
    skipped_count: int


@dataclass
class ExtractionStats:
    """Statistics from an extraction run."""
    files_processed: int
    success_count: int
    error_count: int
    skipped_count: int
    elapsed_seconds: float


class ExtractorService:
    """Service for extracting text content from files."""

    # Categories that support text extraction
    EXTRACTABLE_CATEGORIES = {
        FileCategory.DOCUMENTS,
        FileCategory.SPREADSHEETS,
        FileCategory.SLIDES,
        FileCategory.CODE,
    }

    # Maximum file size for extraction (50MB)
    MAX_EXTRACT_SIZE = 50 * 1024 * 1024

    # Maximum time to spend on a single file (seconds)
    MAX_EXTRACT_TIME = 30

    def __init__(self, fs: FSPort, db: DBPort):
        """
        Initialize the extractor service.

        Args:
            fs: Filesystem port for reading files
            db: Database port for storing content
        """
        self.fs = fs
        self.db = db
        self.registry = get_registry()

    def extract_file(self, file: FileRecord, root_path: str) -> Optional[ContentRecord]:
        """
        Extract content from a single file.

        Args:
            file: The file record to extract
            root_path: The root path to prepend

        Returns:
            ContentRecord if successful, None otherwise
        """
        # Build full path
        full_path = Path(root_path) / file.path

        # Check if we can extract this file type
        if not self.registry.can_extract(full_path):
            return None

        # Check file size
        if file.size_bytes > self.MAX_EXTRACT_SIZE:
            self.db.update_file_status(
                file.file_id, IndexStatus.SKIPPED,
                f"File too large for extraction: {file.size_bytes / 1024 / 1024:.1f}MB"
            )
            return None

        # Do the extraction with timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.registry.extract, full_path)
                result = future.result(timeout=self.MAX_EXTRACT_TIME)
        except FuturesTimeoutError:
            self.db.update_file_status(
                file.file_id, IndexStatus.SKIPPED,
                f"Extraction timed out after {self.MAX_EXTRACT_TIME}s"
            )
            return None
        except Exception as e:
            self.db.update_file_status(
                file.file_id, IndexStatus.ERROR, f"Extraction error: {e}"
            )
            return None

        if not result.success:
            self.db.update_file_status(
                file.file_id, IndexStatus.ERROR, result.error
            )
            return None

        # Create content record
        content = ContentRecord(
            file_id=file.file_id,
            title=file.name,
            content_excerpt=result.text[:500] if result.text else None,
            full_text=result.text,
            extraction_version="1.0",
            extracted_at=datetime.now(),
        )

        # Store in database (this also updates FTS)
        self.db.upsert_content(content)

        # Update file status
        self.db.update_file_status(file.file_id, IndexStatus.EXTRACT_OK)

        return content

    def extract_root(
        self,
        root_id: int,
        progress_callback: Optional[Callable[[ExtractionProgress], None]] = None,
        limit: Optional[int] = None
    ) -> ExtractionStats:
        """
        Extract content from all extractable files in a root.

        Args:
            root_id: The root to process
            progress_callback: Optional callback for progress updates
            limit: Maximum number of files to process (for testing)

        Returns:
            ExtractionStats with counts and timing
        """
        import time
        start_time = time.time()

        # Get the root
        root = self.db.get_root(root_id)
        if not root:
            return ExtractionStats(0, 0, 0, 0, 0.0)

        # Get files that need extraction
        files = self._get_extractable_files(root_id, limit)

        stats = ExtractionStats(
            files_processed=0,
            success_count=0,
            error_count=0,
            skipped_count=0,
            elapsed_seconds=0.0
        )

        for i, file in enumerate(files):
            # Progress callback
            if progress_callback:
                progress_callback(ExtractionProgress(
                    files_processed=i,
                    files_total=len(files),
                    current_file=file.name,
                    success_count=stats.success_count,
                    error_count=stats.error_count,
                    skipped_count=stats.skipped_count,
                ))

            stats.files_processed += 1

            try:
                result = self.extract_file(file, root.root_path)
                if result:
                    stats.success_count += 1
                else:
                    stats.skipped_count += 1
            except Exception as e:
                stats.error_count += 1
                self.db.update_file_status(
                    file.file_id, IndexStatus.ERROR, str(e)
                )

        stats.elapsed_seconds = time.time() - start_time
        return stats

    def _get_extractable_files(
        self,
        root_id: int,
        limit: Optional[int] = None
    ) -> List[FileRecord]:
        """Get files that are eligible for extraction."""
        all_files = self.db.list_files(root_id, limit=limit or 10000)

        extractable = []
        for file in all_files:
            # Skip directories
            if file.is_dir:
                continue

            # Skip already indexed files
            if file.status == IndexStatus.EXTRACT_OK:
                continue

            # Skip files in non-extractable categories
            if file.category not in self.EXTRACTABLE_CATEGORIES:
                continue

            # Check if we have an extractor for this type
            full_path = Path(file.path)
            if not self.registry.can_extract(full_path):
                continue

            extractable.append(file)

        return extractable

    def get_extraction_stats(self, root_id: int) -> dict:
        """Get extraction statistics for a root."""
        files = self.db.list_files(root_id, limit=100000)

        total = len(files)
        indexed = sum(1 for f in files if f.status == IndexStatus.EXTRACT_OK)
        pending = sum(1 for f in files if f.status == IndexStatus.PENDING)
        errors = sum(1 for f in files if f.status == IndexStatus.ERROR)
        skipped = sum(1 for f in files if f.status == IndexStatus.SKIPPED)

        extractable = len(self._get_extractable_files(root_id))

        return {
            'total_files': total,
            'indexed': indexed,
            'pending': pending,
            'errors': errors,
            'skipped': skipped,
            'extractable_remaining': extractable,
        }
