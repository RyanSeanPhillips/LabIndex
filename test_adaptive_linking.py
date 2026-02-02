"""
Test script for Adaptive Linking System.

This script is READ-ONLY - it does not modify any files in the target directory.
It uses a persistent SQLite database for indexing (stored in %APPDATA%/LabIndex/).

Tests:
1. Index the examples directory (read-only scan)
2. Find photometry data (FP_data*) files
3. Find related notes using context-aware reading
4. Use Ollama/Gemma to analyze and describe experiments

Usage:
    python test_adaptive_linking.py              # Use persistent database (default)
    python test_adaptive_linking.py --memory     # Use in-memory database (no persistence)
    python test_adaptive_linking.py --fresh      # Delete existing DB and start fresh
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from labindex_core.adapters.sqlite_db import SqliteDB
from labindex_core.adapters.readonly_fs import ReadOnlyFS
from labindex_core.adapters.ollama_llm import OllamaLLM
from labindex_core.services.crawler import CrawlerService
from labindex_core.services.extractor import ExtractorService
from labindex_core.services.context_reader import ContextReader
from labindex_core.services.handlers import create_default_registry
from labindex_core.domain.enums import FileCategory, IndexStatus


def get_db_path() -> Path:
    """Get the persistent database path in %APPDATA%/LabIndex/."""
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        appdata = Path.home() / ".config"

    db_dir = appdata / "LabIndex"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "index.db"


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test Adaptive Linking System")
    parser.add_argument("--memory", action="store_true",
                        help="Use in-memory database (no persistence)")
    parser.add_argument("--fresh", action="store_true",
                        help="Delete existing database and start fresh")
    args = parser.parse_args()

    print("=" * 70)
    print("Adaptive Linking System - READ-ONLY Test")
    print("=" * 70)
    print()

    # Target directory
    target_dir = r"C:\Users\rphil2\Dropbox\python scripts\breath_analysis\pyqt6\examples"

    if not os.path.exists(target_dir):
        print(f"ERROR: Directory not found: {target_dir}")
        return

    print(f"Target directory: {target_dir}")

    # === Initialize database ===
    if args.memory:
        db_path = ":memory:"
        print(f"Database: IN-MEMORY (no persistence)")
    else:
        db_path = get_db_path()
        if args.fresh and db_path.exists():
            print(f"Deleting existing database: {db_path}")
            db_path.unlink()
        print(f"Database: {db_path}")
        if db_path.exists():
            print(f"  (Using existing index - {db_path.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"  (Creating new index)")

    print(f"Filesystem: READ-ONLY (no file modifications)")
    print()

    # === Initialize services ===
    print("=== Initializing Services ===")

    # SQLite database - persistent or in-memory based on args
    db = SqliteDB(str(db_path))

    # Read-only filesystem adapter
    fs = ReadOnlyFS()

    # Initialize Ollama LLM
    llm = OllamaLLM()  # Auto-detects model

    if llm.is_available():
        print(f"  Ollama: Available (model: {llm.get_model_name()})")
    else:
        print("  Ollama: NOT AVAILABLE - LLM features disabled")
        llm = None

    # Services (note: CrawlerService takes (fs, db), ExtractorService takes (fs, db))
    crawler = CrawlerService(fs, db)
    extractor = ExtractorService(fs, db)
    context_reader = ContextReader(db, llm, llm_budget=10)

    print("  Services initialized OK")
    print()

    # === Index the directory (read-only scan) ===
    print("=== Indexing Directory (Read-Only Scan) ===")

    # Check if root already exists (for persistent DB)
    # Normalize paths for comparison
    target_dir_resolved = str(Path(target_dir).resolve())
    existing_roots = db.list_roots()
    root = None
    for r in existing_roots:
        root_path_resolved = str(Path(r.path).resolve())
        if root_path_resolved == target_dir_resolved:
            root = r
            print(f"  Using existing root: {root.label} (ID={root.root_id})")
            break

    if root is None:
        root = crawler.add_root(target_dir, "examples")
        print(f"  Added new root: {root.label} (ID={root.root_id})")

    stats = crawler.crawl_root(root.root_id)
    print(f"  Crawled: {stats.files_found} files, {stats.dirs_scanned} directories")
    print()

    # === Extract content (reads files, no modifications) ===
    print("=== Extracting Content (Read-Only) ===")

    extract_stats = extractor.extract_root(root.root_id)
    print(f"  Extracted: {extract_stats.success_count} files")
    print(f"  Skipped: {extract_stats.skipped_count} files")
    print()

    # === Find photometry data files ===
    print("=== Finding Photometry Data Files (FP_data*) ===")

    all_files = db.list_files(root.root_id, limit=10000)

    # Find FP_data files
    fp_files = [f for f in all_files if "fp_data" in f.name.lower() and not f.is_dir]
    print(f"  Found {len(fp_files)} photometry data files")

    for fp in fp_files[:5]:  # Show first 5
        print(f"    - {fp.path}")

    print()

    # === Find notes files ===
    print("=== Finding Notes Files ===")

    notes_files = [f for f in all_files
                   if f.ext.lower() in ("txt", "md", "docx")
                   and not f.is_dir
                   and f.status == IndexStatus.EXTRACT_OK]

    print(f"  Found {len(notes_files)} notes files with content")

    for nf in notes_files[:5]:
        print(f"    - {nf.path}")

    print()

    # === Use Context Reader to find references ===
    print("=== Context-Aware Reference Detection ===")

    # Find a notes file and analyze its references
    if notes_files:
        # Pick a notes file that might have photometry references
        test_notes = None
        for nf in notes_files:
            ctx = context_reader.get_file_context(nf)
            if ctx.references:
                test_notes = nf
                break

        if test_notes:
            print(f"\n  Analyzing: {test_notes.name}")
            print(f"  Path: {test_notes.path}")

            ctx = context_reader.get_file_context(test_notes, context_lines=15)

            print(f"  Handler: {ctx.handler_name}")
            print(f"  References found: {len(ctx.references)}")

            for ref in ctx.references[:5]:
                print(f"\n  Reference: '{ref.reference}' (type: {ref.reference_type})")
                print(f"    Line: {ref.line_number}")
                print(f"    Confidence: {ref.confidence:.0%}")
                if ref.extracted_metadata:
                    print(f"    Metadata: {ref.extracted_metadata}")
                print(f"    Context preview: {ref.context_summary[:100]}...")

    print()

    # === Try to link FP data to notes ===
    print("=== Finding Linked Experiments ===")

    # Look for notes in same folder as FP data
    experiments_found = []

    for fp in fp_files:
        # Find parent folder
        fp_parent = Path(fp.path).parent

        # Find notes in same or parent folder
        related_notes = [
            nf for nf in notes_files
            if str(fp_parent) in nf.path or str(fp_parent.parent) in nf.path
        ]

        if related_notes:
            # Get content of the notes
            for notes in related_notes[:1]:  # Just first one
                content = db.get_content(notes.file_id)
                if content and content.full_text:
                    experiments_found.append({
                        "fp_file": fp,
                        "notes_file": notes,
                        "notes_content": content.full_text,
                    })

    print(f"  Found {len(experiments_found)} FP files with nearby notes")
    print()

    # === Describe one experiment using LLM ===
    if experiments_found and llm:
        print("=== Experiment Analysis (using Ollama) ===")

        exp = experiments_found[0]
        print(f"\n  FP Data: {exp['fp_file'].name}")
        print(f"  FP Path: {exp['fp_file'].path}")
        print(f"  Notes: {exp['notes_file'].name}")

        # Get notes content (truncate for LLM)
        notes_content = exp['notes_content'][:3000]

        print(f"\n  --- Notes Content (first 500 chars) ---")
        print(f"  {notes_content[:500]}...")
        print()

        # Ask LLM to describe the experiment
        prompt = f"""Based on these research notes, describe this experiment briefly:

Notes file: {exp['notes_file'].name}
Related data file: {exp['fp_file'].name}

Notes content:
{notes_content}

Please provide:
1. What type of experiment was this?
2. What was being measured/recorded?
3. What animal/subject was used (if mentioned)?
4. Any key observations or conditions noted?

Keep your response concise (3-5 sentences)."""

        print("  Asking Ollama to analyze the experiment...")
        print()

        response = llm.simple_chat(prompt)

        print("  --- LLM Analysis ---")
        print(f"  {response}")
        print()

    elif experiments_found and not llm:
        print("=== Experiment Found (LLM not available for analysis) ===")
        exp = experiments_found[0]
        print(f"\n  FP Data: {exp['fp_file'].name}")
        print(f"  Notes: {exp['notes_file'].name}")
        print(f"\n  Notes Preview:")
        print(f"  {exp['notes_content'][:800]}...")

    else:
        print("  No linked experiments found with notes content.")

    print()
    print("=" * 70)
    print("Test complete. No files were modified.")
    if not args.memory:
        db_path = get_db_path()
        if db_path.exists():
            print(f"Database saved: {db_path} ({db_path.stat().st_size / 1024:.1f} KB)")
            print("Run again to use cached index, or use --fresh to rebuild.")
    print("=" * 70)


if __name__ == "__main__":
    main()
