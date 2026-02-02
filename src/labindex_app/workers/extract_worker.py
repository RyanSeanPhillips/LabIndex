"""
Extract worker thread.

Runs content extraction in the background without blocking the UI.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from labindex_core.services.extractor import ExtractorService


class ExtractWorker(QThread):
    """
    Background thread for content extraction.

    Signals:
        progress(int, int, str): Emitted during extraction with (processed, total, current_file)
        finished(bool, str): Emitted when extraction completes with (success, message)
    """

    progress = pyqtSignal(int, int, str)  # processed, total, current_file
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, extractor: ExtractorService, root_id: int):
        """
        Initialize the worker.

        Args:
            extractor: The extractor service to use
            root_id: ID of the root to extract content from
        """
        super().__init__()
        self.extractor = extractor
        self.root_id = root_id

    def run(self):
        """Run the extraction operation."""
        try:
            def on_progress(p):
                self.progress.emit(p.files_processed, p.files_total, p.current_file)

            result = self.extractor.extract_root(self.root_id, progress_callback=on_progress)
            self.finished.emit(
                True,
                f"Extraction complete: {result.success_count:,} indexed, "
                f"{result.skipped_count:,} skipped, {result.error_count:,} errors"
            )
        except Exception as e:
            self.finished.emit(False, f"Extraction failed: {e}")
