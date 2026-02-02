"""
Link worker thread.

Runs auto-linking in the background without blocking the UI.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from labindex_core.services.linker import LinkerService


class LinkWorker(QThread):
    """
    Background thread for auto-linking files.

    Signals:
        progress(str): Emitted during linking with status message
        finished(bool, str): Emitted when linking completes with (success, message)
    """

    progress = pyqtSignal(str)  # status message
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, linker: LinkerService, root_id: int):
        """
        Initialize the worker.

        Args:
            linker: The linker service to use
            root_id: ID of the root to find links in
        """
        super().__init__()
        self.linker = linker
        self.root_id = root_id

    def run(self):
        """Run the linking operation."""
        try:
            self.progress.emit("Analyzing files for relationships...")
            result = self.linker.link_root(self.root_id)
            self.finished.emit(
                True,
                f"Linking complete: {result.edges_created:,} relationships found "
                f"in {result.elapsed_seconds:.1f}s"
            )
        except Exception as e:
            self.finished.emit(False, f"Linking failed: {e}")
