"""
Analyze photometry files and their notes relationships.

Goal: For each FP_data file, find the corresponding notes.txt that describes:
- Mouse IDs (R-266018, LR-266019, etc.)
- Channel mappings (ROI, AI channels)
- Experimental conditions (wavelengths, timeline)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from labindex_core.adapters.sqlite_db import SqliteDB
from labindex_core.adapters.readonly_fs import ReadOnlyFS
from labindex_core.services.search import SearchService


def main():
    # Use the test database
    db_path = Path(__file__).parent / "test_labindex.db"
    db = SqliteDB(db_path)
    search = SearchService(db)

    roots = db.list_roots()
    if not roots:
        print("No roots found!")
        return

    all_files = db.list_files(roots[0].root_id, limit=5000)

    # Find FP_data CSV files
    fp_files = [f for f in all_files
                if 'FP_data' in f.name and f.name.endswith('.csv')]

    # Find txt notes files
    txt_files = [f for f in all_files if f.name.endswith('.txt')]

    print(f"Found {len(fp_files)} FP_data CSV files")
    print(f"Found {len(txt_files)} txt files")

    print("\n" + "=" * 70)
    print("PHOTOMETRY DATA FILES AND THEIR NOTES")
    print("=" * 70)

    # Group FP files by their parent folder (session folder)
    sessions = {}
    for fp in fp_files:
        # FP_data files are typically in: session_folder/FP_data_X/FP_data_X.csv
        # The notes are typically at: session_folder/YYMMDD.txt
        session_path = Path(fp.path).parent.parent  # Go up 2 levels
        session_key = str(session_path)
        if session_key not in sessions:
            sessions[session_key] = {"fp_files": [], "notes": []}
        sessions[session_key]["fp_files"].append(fp)

    # Find notes for each session
    for session_path, data in sessions.items():
        # Look for txt files in the session folder or parent
        session_txt = [f for f in txt_files
                       if f.parent_path == session_path or
                          str(Path(f.path).parent) == session_path]
        data["notes"] = session_txt

    # Print analysis
    for session_path, data in sorted(sessions.items()):
        print(f"\n{'=' * 70}")
        print(f"SESSION: {session_path}")
        print(f"  FP Files: {len(data['fp_files'])}")
        for fp in data['fp_files']:
            print(f"    - {fp.name} ({fp.path})")

        if data['notes']:
            print(f"  Notes Files: {len(data['notes'])}")
            for note in data['notes']:
                print(f"    - {note.name}")

                # Get content excerpt
                content = db.get_content(note.file_id)
                if content and content.full_text:
                    lines = content.full_text.split('\n')[:10]
                    for line in lines:
                        if line.strip():
                            print(f"      | {line[:70]}")
        else:
            print(f"  Notes Files: NONE FOUND")
            # Try to find by name pattern
            # Notes often follow pattern: YYMMDD.txt or YYMMDDX.txt
            session_name = Path(session_path).name
            possible = [f for f in txt_files if session_name[:6] in f.name]
            if possible:
                print(f"  Possible matches by date pattern:")
                for p in possible[:3]:
                    print(f"    - {p.name} ({p.path})")

    # Summary of what we can extract
    print("\n" + "=" * 70)
    print("PLAN FOR EXTRACTING EXPERIMENT INFO")
    print("=" * 70)

    print("""
For each photometry data file, we can determine:

1. **Mouse IDs**: Parse notes for patterns like "R-266018" or "LR-266019"
2. **Channel Mapping**:
   - ROI number (0, 1, etc.) - which fiber
   - AI channel number (1, 2, etc.) - which analog input
   - Signal type (GCaMP, GRABNE) - which sensor

3. **Wavelength Settings**:
   - 415nm (isosbestic/control)
   - 470nm (signal)
   - Power levels (microwatts)

4. **Experimental Timeline**:
   - Recording start/end times
   - Condition changes (room air, CO2, O2)
   - Tone/stimulus events

5. **Observations**: Manual annotations about signal quality

LINKING STRATEGY:
- FP_data files should link to notes in same session folder
- Use folder hierarchy: session_folder/FP_data_X/FP_data_X.csv
- Notes are at: session_folder/YYMMDD.txt

The current linker is finding wrong links because it's using:
- Animal ID patterns (matches to unrelated .abf files)
- Content mentions (noise)

RECOMMENDED FIX:
Add a "sibling_folder_notes" rule that:
1. For each FP_data CSV, look for .txt files in parent folder
2. Higher confidence (85%+) for same-folder notes
3. Extract structured metadata from notes content
""")

    db.close()


if __name__ == "__main__":
    main()
