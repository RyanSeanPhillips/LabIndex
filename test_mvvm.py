"""
Test script for LabIndex MVVM implementation.

Tests:
1. ViewModels can be imported
2. Indexing the examples folder works
3. Extraction works
4. Linking works
5. Search with N+1 fix works
6. Can find photometry files and their notes
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all ViewModels can be imported."""
    print("\n=== Testing Imports ===")

    try:
        from labindex_app.viewmodels import (
            BaseViewModel,
            IndexStatusVM,
            SearchVM,
            GraphVM,
            AgentVM,
            InspectorVM,
            CandidateReviewVM,
            AppCoordinator,
        )
        print("  ViewModels imported OK")
    except Exception as e:
        print(f"  ERROR importing ViewModels: {e}")
        return False

    try:
        from labindex_app.workers import (
            CrawlWorker,
            ExtractWorker,
            LinkWorker,
            AgentWorker,
        )
        print("  Workers imported OK")
    except Exception as e:
        print(f"  ERROR importing Workers: {e}")
        return False

    return True


def test_services():
    """Test that services can be created."""
    print("\n=== Testing Services ===")

    from labindex_core.adapters.sqlite_db import SqliteDB
    from labindex_core.adapters.readonly_fs import ReadOnlyFS
    from labindex_core.services.crawler import CrawlerService
    from labindex_core.services.search import SearchService
    from labindex_core.services.extractor import ExtractorService
    from labindex_core.services.linker import LinkerService

    # Use test database
    test_db_path = Path(__file__).parent / "test_labindex.db"
    if test_db_path.exists():
        test_db_path.unlink()

    db = SqliteDB(test_db_path)
    fs = ReadOnlyFS()

    crawler = CrawlerService(fs, db)
    search = SearchService(db)
    extractor = ExtractorService(fs, db)
    linker = LinkerService(db)

    print("  Services created OK")
    return db, fs, crawler, search, extractor, linker


def test_indexing(crawler, search, extractor, linker, examples_path):
    """Test crawling and extraction."""
    print("\n=== Testing Indexing ===")

    # Add root
    root = crawler.add_root(examples_path)
    print(f"  Added root: {root.label} (ID={root.root_id})")

    # Crawl
    print("  Crawling...")
    progress = crawler.crawl_root(root.root_id)
    print(f"  Crawl complete: {progress.files_found:,} files, {progress.dirs_scanned:,} dirs")

    # Check stats
    stats = search.get_stats()
    print(f"  Files indexed: {stats['file_count']:,}")

    return root


def test_extraction(extractor, root_id):
    """Test content extraction."""
    print("\n=== Testing Extraction ===")

    print("  Extracting content...")
    result = extractor.extract_root(root_id)
    print(f"  Extraction complete: {result.success_count:,} indexed, "
          f"{result.skipped_count:,} skipped, {result.error_count:,} errors")

    return result


def test_linking(linker, root_id):
    """Test link detection."""
    print("\n=== Testing Linking ===")

    print("  Finding links...")
    result = linker.link_root(root_id)
    print(f"  Linking complete: {result.edges_created:,} links in {result.elapsed_seconds:.1f}s")

    return result


def test_search(search):
    """Test search with N+1 fix."""
    print("\n=== Testing Search ===")

    # Test batch search method
    print("  Testing search_with_metadata (N+1 fix)...")
    results = search.search_with_metadata("FP_data", limit=20)
    print(f"  Found {len(results)} results for 'FP_data'")

    for r in results[:5]:
        links = f" ({r['link_count']} links)" if r['link_count'] > 0 else ""
        print(f"    - {r['name']}: {r['category']}{links}")

    # Search for notes files
    print("\n  Searching for notes files...")
    notes_results = search.search_with_metadata(".txt", limit=20)
    txt_files = [r for r in notes_results if r['name'].endswith('.txt')]
    print(f"  Found {len(txt_files)} txt files")

    for r in txt_files[:5]:
        excerpt = r['content_excerpt'][:50] if r['content_excerpt'] else "No content"
        print(f"    - {r['name']}: {excerpt}...")

    return results


def test_find_photometry_links(db, search):
    """Find photometry files and their linked notes."""
    print("\n=== Finding Photometry-Notes Links ===")

    # Get all files to find FP_data files
    from labindex_core.domain.enums import FileCategory

    roots = db.list_roots()
    if not roots:
        print("  No roots found")
        return

    # Find FP_data CSVs
    all_files = db.list_files(roots[0].root_id, limit=5000)
    fp_data_files = [f for f in all_files if 'FP_data' in f.name and f.name.endswith('.csv')]

    print(f"  Found {len(fp_data_files)} FP_data CSV files")

    # For each FP_data file, look for related notes
    for fp_file in fp_data_files[:5]:
        print(f"\n  FP File: {fp_file.path}")

        # Get edges
        edges_to = db.get_edges_to(fp_file.file_id)
        edges_from = db.get_edges_from(fp_file.file_id)

        if edges_to or edges_from:
            print(f"    Links found:")
            for edge in edges_to:
                src = db.get_file(edge.src_file_id)
                if src:
                    print(f"      <- {src.name} ({edge.relation_type.value}, {edge.confidence:.0%})")
            for edge in edges_from:
                dst = db.get_file(edge.dst_file_id)
                if dst:
                    print(f"      -> {dst.name} ({edge.relation_type.value}, {edge.confidence:.0%})")
        else:
            # Try to find notes by proximity (same parent folder)
            parent = fp_file.parent_path
            sibling_txt = [f for f in all_files
                           if f.parent_path == parent and f.name.endswith('.txt')]
            if sibling_txt:
                print(f"    No links, but sibling txt files: {[f.name for f in sibling_txt]}")
            else:
                # Check grandparent
                gp_path = str(Path(parent).parent) if parent else ""
                gp_txt = [f for f in all_files
                          if f.parent_path == gp_path and f.name.endswith('.txt')]
                if gp_txt:
                    print(f"    No links, but txt files in parent folder: {[f.name for f in gp_txt]}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("LabIndex MVVM Test Suite")
    print("=" * 60)

    # Path to examples
    examples_path = r"C:\Users\rphil2\Dropbox\python scripts\breath_analysis\pyqt6\examples"

    if not Path(examples_path).exists():
        print(f"ERROR: Examples path not found: {examples_path}")
        return

    # Test 1: Imports
    if not test_imports():
        print("\nImport tests failed!")
        return

    # Test 2: Services
    db, fs, crawler, search, extractor, linker = test_services()

    # Test 3: Indexing
    root = test_indexing(crawler, search, extractor, linker, examples_path)

    # Test 4: Extraction
    test_extraction(extractor, root.root_id)

    # Test 5: Linking
    test_linking(linker, root.root_id)

    # Test 6: Search
    test_search(search)

    # Test 7: Find FP-Notes links
    test_find_photometry_links(db, search)

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

    # Cleanup
    db.close()


if __name__ == "__main__":
    main()
