"""
Main entry point for LabIndex application.

Usage:
    python -m labindex_app
    labindex  (if installed)
"""

import sys
import traceback
from pathlib import Path
from datetime import datetime


def setup_exception_hook():
    """Setup global exception hook to catch Qt exceptions."""
    log_file = Path(__file__).parent.parent.parent.parent / "crash_log.txt"

    def exception_hook(exctype, value, tb):
        # Write to log file
        error_msg = ''.join(traceback.format_exception(exctype, value, tb))
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"UNHANDLED EXCEPTION at {datetime.now()}\n")
            f.write(f"{'='*60}\n")
            f.write(error_msg)
            f.write("\n")

        # Print to console
        print("\n" + "="*60)
        print("UNHANDLED EXCEPTION!")
        print("="*60)
        print(error_msg)
        print(f"\nError log saved to: {log_file}")

        # Call default handler
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = exception_hook


def main():
    """Launch the LabIndex application."""
    # Setup exception hook first
    setup_exception_hook()

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
