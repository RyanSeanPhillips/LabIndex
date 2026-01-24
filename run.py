#!/usr/bin/env python
"""
Convenience script to run LabIndex during development.

Usage:
    python run.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Run the app
from labindex_app.__main__ import main
main()
