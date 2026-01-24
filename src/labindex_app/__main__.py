"""
Main entry point for LabIndex application.

Usage:
    python -m labindex_app
    labindex  (if installed)
"""

import sys
from pathlib import Path


def main():
    """Launch the LabIndex application."""
    # Ensure src is in path for development
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("LabIndex")
    app.setOrganizationName("PhysioMetrics")

    # Import and apply dark theme
    from labindex_app.resources.styles import DARK_STYLESHEET
    app.setStyleSheet(DARK_STYLESHEET)

    # Import and create main window
    from labindex_app.views.main_window import MainWindow

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
