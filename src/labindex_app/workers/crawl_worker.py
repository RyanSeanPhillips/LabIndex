"""
Crawl worker thread.

Runs directory scanning in the background without blocking the UI.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from labindex_core.services.crawler import CrawlerService


class CrawlWorker(QThread):
    """
    Background thread for crawling directories.

    Signals:
        progress(int, int, str): Emitted during crawl with (dirs_scanned, files_found, current_path)
        finished(bool, str): Emitted when crawl completes with (success, message)
    """

    progress = pyqtSignal(int, int, str)  # dirs, files, current_path
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, crawler: CrawlerService, root_id: int):
        """
        Initialize the worker.

        Args:
            crawler: The crawler service to use
            root_id: ID of the root to crawl
        """
        super().__init__()
        self.crawler = crawler
        self.root_id = root_id

    def run(self):
        """Run the crawl operation."""
        try:
            def on_progress(p):
                self.progress.emit(p.dirs_scanned, p.files_found, p.current_path)

            result = self.crawler.crawl_root(self.root_id, progress_callback=on_progress)
            self.finished.emit(
                True,
                f"Crawl complete: {result.files_found:,} files in {result.dirs_scanned:,} directories"
            )
        except Exception as e:
            self.finished.emit(False, f"Crawl failed: {e}")
