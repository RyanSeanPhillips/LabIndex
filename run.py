#!/usr/bin/env python
"""
Convenience script to run LabIndex during development.

Usage:
    python run.py
"""

import sys
import traceback
from pathlib import Path
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Log file for crash reports
log_file = Path(__file__).parent / "crash_log.txt"

def main_with_error_handling():
    try:
        from labindex_app.__main__ import main
        main()
    except Exception as e:
        # Write to log file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH at {datetime.now()}\n")
            f.write(f"{'='*60}\n")
            f.write(traceback.format_exc())
            f.write("\n")

        # Also print to console
        print("\n" + "="*60)
        print("APPLICATION CRASHED!")
        print("="*60)
        traceback.print_exc()
        print(f"\nError log saved to: {log_file}")
        print("\nPress Enter to exit...")
        input()  # Keep console open

if __name__ == "__main__":
    main_with_error_handling()
