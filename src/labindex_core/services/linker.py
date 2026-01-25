"""
Linker Service - Auto-detect relationships between files.

This service analyzes files and their content to discover relationships:
- Animal ID matching (folder names to surgery notes)
- Filename patterns (related files in same folder)
- Content mentions (text references to other files/animals)
- Date/session matching (files from same recording session)
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

from ..domain.models import FileRecord, ContentRecord, Edge
from ..domain.enums import FileCategory, EdgeType, IndexStatus
from ..ports.db_port import DBPort


@dataclass
class LinkCandidate:
    """A potential relationship between two files."""
    src_file_id: int
    dst_file_id: int
    relation_type: EdgeType
    confidence: float  # 0.0 to 1.0
    evidence: str  # Why we think they're related
    rule_name: str  # Which rule found this


@dataclass
class LinkingStats:
    """Statistics from a linking run."""
    files_analyzed: int
    edges_created: int
    edges_updated: int
    elapsed_seconds: float


class LinkerService:
    """Service for discovering relationships between files."""

    # Common animal ID patterns in folder/file names
    ANIMAL_ID_PATTERNS = [
        r'(?:animal|mouse|rat|subject)[_\-\s]*(\d{3,5})',  # animal_982, mouse-1234
        r'(?:id|ID)[_\-\s]*(\d{3,5})',  # ID_982, id-1234
        r'[_\-](\d{3,5})[_\-]',  # _982_, -1234-
        r'^(\d{3,5})(?:[_\-]|$)',  # 982_something or just 982
    ]

    # Patterns that suggest notes/documentation
    NOTES_PATTERNS = [
        r'(?:surgery|surgical|notes|log|record)',
        r'(?:protocol|procedure|experiment)',
        r'(?:metadata|info|details)',
    ]

    # Patterns for data files
    DATA_EXTENSIONS = {'.abf', '.smrx', '.smr', '.edf', '.mat', '.nwb', '.h5'}

    # Common data file extensions to look for in text
    DATA_FILE_PATTERN = r'\b(\w+\.(?:abf|smrx|smr|edf|mat|nwb|h5|csv|xlsx?))\b'

    # Short reference patterns (e.g., "000", "001", "002" or "000.abf")
    # These are often used in notes to refer to files like "20240115000.abf"
    SHORT_REF_PATTERN = r'\b(\d{3})(?:\.abf)?\b'

    # Pattern to extract the numeric suffix from ABF filenames
    ABF_SUFFIX_PATTERN = r'(\d{3})\.abf$'

    def __init__(self, db: DBPort):
        """Initialize the linker service."""
        self.db = db

    def link_root(self, root_id: int) -> LinkingStats:
        """
        Analyze all files in a root and create relationship edges.

        Args:
            root_id: The root to analyze

        Returns:
            LinkingStats with counts
        """
        import time
        start_time = time.time()

        stats = LinkingStats(
            files_analyzed=0,
            edges_created=0,
            edges_updated=0,
            elapsed_seconds=0.0
        )

        # Get all files
        files = self.db.list_files(root_id, limit=100000)
        stats.files_analyzed = len(files)

        # Build indexes for fast lookup
        files_by_id = {f.file_id: f for f in files}
        files_by_path = {f.path: f for f in files}

        # Extract animal IDs from folder structure
        animal_id_to_files = self._build_animal_id_index(files)

        # Build filename index for explicit reference matching
        files_by_name = {f.name.lower(): f for f in files if not f.is_dir}

        # Build ABF suffix index for short reference matching
        # Maps "000" -> [file1, file2, ...] (files ending in 000.abf)
        abf_by_suffix = self._build_abf_suffix_index(files)

        # Find all candidates
        candidates: List[LinkCandidate] = []

        # Rule 0: NPZ original_file links (HIGHEST VALUE)
        # PhysioMetrics NPZ files contain explicit reference to source data
        candidates.extend(self._find_npz_source_links(files, files_by_name))

        # Rule 1: Explicit file references in content (HIGH VALUE)
        # This finds documents that explicitly mention data file names
        candidates.extend(self._find_explicit_file_references(files, files_by_name))

        # Rule 2: Short file references (e.g., "000", "001" referring to YYYYMMDD000.abf)
        candidates.extend(self._find_short_file_references(files, abf_by_suffix))

        # Rule 3: Animal ID matching between data folders and notes
        candidates.extend(self._find_animal_id_links(files, animal_id_to_files))

        # Rule 4: Sibling files in same folder (only if similar names)
        candidates.extend(self._find_sibling_links(files))

        # Rule 5: Content-based mentions (if content extracted)
        candidates.extend(self._find_content_mentions(root_id, files, animal_id_to_files))

        # Create edges from candidates
        for candidate in candidates:
            edge = Edge(
                edge_id=0,  # Will be set by DB
                src_file_id=candidate.src_file_id,
                dst_file_id=candidate.dst_file_id,
                relation_type=candidate.relation_type,
                confidence=candidate.confidence,
                evidence=candidate.evidence,
                created_by=f"rule:{candidate.rule_name}",
            )
            try:
                self.db.add_edge(edge)
                stats.edges_created += 1
            except Exception:
                # Edge might already exist
                stats.edges_updated += 1

        stats.elapsed_seconds = time.time() - start_time
        return stats

    def _build_animal_id_index(self, files: List[FileRecord]) -> Dict[str, List[FileRecord]]:
        """Build an index mapping animal IDs to files."""
        animal_id_to_files: Dict[str, List[FileRecord]] = {}

        for file in files:
            # Look for animal IDs in the path
            for pattern in self.ANIMAL_ID_PATTERNS:
                matches = re.findall(pattern, file.path, re.IGNORECASE)
                for animal_id in matches:
                    if animal_id not in animal_id_to_files:
                        animal_id_to_files[animal_id] = []
                    animal_id_to_files[animal_id].append(file)

        return animal_id_to_files

    def _build_abf_suffix_index(self, files: List[FileRecord]) -> Dict[str, List[FileRecord]]:
        """
        Build an index mapping 3-digit suffixes to ABF files.

        E.g., "000" -> [file with name "20240115000.abf", ...]
        """
        suffix_to_files: Dict[str, List[FileRecord]] = {}

        for file in files:
            if file.is_dir:
                continue

            # Check if it's an ABF file
            if not file.name.lower().endswith('.abf'):
                continue

            # Extract the 3-digit suffix
            match = re.search(self.ABF_SUFFIX_PATTERN, file.name, re.IGNORECASE)
            if match:
                suffix = match.group(1)
                if suffix not in suffix_to_files:
                    suffix_to_files[suffix] = []
                suffix_to_files[suffix].append(file)

        return suffix_to_files

    def _calculate_path_similarity(self, path1: str, path2: str) -> float:
        """
        Calculate how similar two paths are (0.0 to 1.0).

        - Same folder: 1.0
        - Share parent: 0.8
        - Share grandparent: 0.6
        - Share some ancestor: 0.4
        - No common path: 0.0
        """
        parts1 = Path(path1).parts
        parts2 = Path(path2).parts

        # Find common prefix length
        common = 0
        for p1, p2 in zip(parts1, parts2):
            if p1.lower() == p2.lower():
                common += 1
            else:
                break

        if common == 0:
            return 0.0

        # Calculate similarity based on how much of the path is shared
        max_depth = max(len(parts1), len(parts2))
        if max_depth == 0:
            return 0.0

        # How deep is the common ancestor relative to the deepest file?
        similarity = common / max_depth

        # Boost if they're very close (same parent or grandparent)
        if len(parts1) > 1 and len(parts2) > 1:
            if parts1[:-1] == parts2[:-1]:  # Same parent folder
                return 1.0
            if len(parts1) > 2 and len(parts2) > 2:
                if parts1[:-2] == parts2[:-2]:  # Same grandparent
                    return 0.8

        return min(similarity + 0.2, 0.6)  # Cap at 0.6 for distant relations

    def _find_short_file_references(
        self,
        files: List[FileRecord],
        abf_by_suffix: Dict[str, List[FileRecord]]
    ) -> List[LinkCandidate]:
        """
        Find documents that reference ABF files by short suffix (e.g., "000", "001").

        This handles the common case where notes say "recorded 000, 001, 002"
        referring to files like "20240115000.abf", "20240115001.abf", etc.
        """
        candidates = []

        for file in files:
            # Only check files with extracted content
            if file.status != IndexStatus.EXTRACT_OK:
                continue

            content = self.db.get_content(file.file_id)
            if not content or not content.full_text:
                continue

            text = content.full_text

            # Find all short references (3-digit numbers)
            matches = re.findall(self.SHORT_REF_PATTERN, text)

            # Count occurrences to filter noise (single mentions might be coincidence)
            suffix_counts: Dict[str, int] = {}
            for suffix in matches:
                suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1

            for suffix, count in suffix_counts.items():
                # Skip if this suffix doesn't match any ABF file
                if suffix not in abf_by_suffix:
                    continue

                abf_files = abf_by_suffix[suffix]

                for abf_file in abf_files:
                    # Don't link file to itself
                    if abf_file.file_id == file.file_id:
                        continue

                    # Calculate base confidence
                    # Multiple mentions = higher confidence
                    base_confidence = min(0.5 + (count - 1) * 0.1, 0.7)

                    # Boost confidence based on path similarity
                    path_sim = self._calculate_path_similarity(file.path, abf_file.path)
                    confidence = base_confidence + (path_sim * 0.25)  # Up to +0.25 boost

                    # Cap at 0.9 (not as high as explicit full filename)
                    confidence = min(confidence, 0.9)

                    candidates.append(LinkCandidate(
                        src_file_id=file.file_id,
                        dst_file_id=abf_file.file_id,
                        relation_type=EdgeType.NOTES_FOR,
                        confidence=confidence,
                        evidence=f"Short reference: '{suffix}' ({count}x), path similarity: {path_sim:.0%}",
                        rule_name="short_file_reference"
                    ))

        return candidates

    def _find_npz_source_links(
        self,
        files: List[FileRecord],
        files_by_name: Dict[str, FileRecord]
    ) -> List[LinkCandidate]:
        """
        Find PhysioMetrics NPZ files and link them to their source data files.

        NPZ files store 'original_file_path' which is an explicit reference
        to the source ABF/SMRX file they were generated from.
        """
        candidates = []

        for file in files:
            # Only check NPZ files with extracted content
            if not file.name.lower().endswith('.npz'):
                continue
            if file.status != IndexStatus.EXTRACT_OK:
                continue

            content = self.db.get_content(file.file_id)
            if not content or not content.full_text:
                continue

            text = content.full_text

            # Look for "Original Data File:" or "Original Path:" in extracted content
            # These are added by the NPZ extractor
            original_patterns = [
                r'Original Data File:\s*(\S+)',
                r'Original Path:.*?([^\\/]+\.(?:abf|smrx|smr|edf))',
            ]

            for pattern in original_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    ref_name = match.group(1).lower()

                    if ref_name in files_by_name:
                        source_file = files_by_name[ref_name]

                        # Don't link to self
                        if source_file.file_id == file.file_id:
                            continue

                        # Calculate path similarity for confidence boost
                        path_sim = self._calculate_path_similarity(file.path, source_file.path)
                        confidence = 0.95 + (path_sim * 0.04)  # 95-99%

                        candidates.append(LinkCandidate(
                            src_file_id=file.file_id,
                            dst_file_id=source_file.file_id,
                            relation_type=EdgeType.ANALYSIS_OF,
                            confidence=min(confidence, 0.99),
                            evidence=f"NPZ original_file: '{ref_name}'",
                            rule_name="npz_source_link"
                        ))
                        break  # Only one link per NPZ file

        return candidates

    def _find_explicit_file_references(
        self,
        files: List[FileRecord],
        files_by_name: Dict[str, FileRecord]
    ) -> List[LinkCandidate]:
        """
        Find documents that explicitly reference data file names.

        This is the highest-value linking rule - it finds surgery notes,
        protocol documents, etc. that list specific data files by name.
        """
        candidates = []

        for file in files:
            # Only check files with extracted content
            if file.status != IndexStatus.EXTRACT_OK:
                continue

            content = self.db.get_content(file.file_id)
            if not content or not content.full_text:
                continue

            text = content.full_text

            # Find all data file references in the text
            matches = re.findall(self.DATA_FILE_PATTERN, text, re.IGNORECASE)

            # Count occurrences
            match_counts: Dict[str, int] = {}
            for match in matches:
                match_lower = match.lower()
                match_counts[match_lower] = match_counts.get(match_lower, 0) + 1

            for match_lower, count in match_counts.items():
                # Check if this filename exists in our index
                if match_lower not in files_by_name:
                    continue

                referenced_file = files_by_name[match_lower]

                # Don't link file to itself
                if referenced_file.file_id == file.file_id:
                    continue

                # Base confidence is high for explicit references
                base_confidence = 0.9

                # Boost for path similarity
                path_sim = self._calculate_path_similarity(file.path, referenced_file.path)
                confidence = base_confidence + (path_sim * 0.08)  # Up to +0.08 boost

                # Cap at 0.98
                confidence = min(confidence, 0.98)

                candidates.append(LinkCandidate(
                    src_file_id=file.file_id,
                    dst_file_id=referenced_file.file_id,
                    relation_type=EdgeType.NOTES_FOR,
                    confidence=confidence,
                    evidence=f"Explicit reference: '{match_lower}' ({count}x)",
                    rule_name="explicit_file_reference"
                ))

        return candidates

    def _find_animal_id_links(
        self,
        files: List[FileRecord],
        animal_id_to_files: Dict[str, List[FileRecord]]
    ) -> List[LinkCandidate]:
        """Find links between files that share animal IDs."""
        candidates = []

        for animal_id, related_files in animal_id_to_files.items():
            if len(related_files) < 2:
                continue

            # Separate data files from notes/docs
            data_files = [f for f in related_files if f.category == FileCategory.DATA]
            note_files = [f for f in related_files
                        if f.category in (FileCategory.DOCUMENTS, FileCategory.SPREADSHEETS)]

            # Link notes to data files
            for note in note_files:
                for data in data_files:
                    # Check if note looks like it describes the data
                    is_notes = any(re.search(p, note.name, re.IGNORECASE)
                                  for p in self.NOTES_PATTERNS)

                    if is_notes:
                        candidates.append(LinkCandidate(
                            src_file_id=note.file_id,
                            dst_file_id=data.file_id,
                            relation_type=EdgeType.NOTES_FOR,
                            confidence=0.5,  # Medium - pattern match, not explicit
                            evidence=f"Shared animal ID: {animal_id}",
                            rule_name="animal_id_match"
                        ))
                    else:
                        # Generic same-animal relationship
                        candidates.append(LinkCandidate(
                            src_file_id=note.file_id,
                            dst_file_id=data.file_id,
                            relation_type=EdgeType.SAME_ANIMAL,
                            confidence=0.4,  # Lower - just ID pattern match
                            evidence=f"Shared animal ID: {animal_id}",
                            rule_name="animal_id_match"
                        ))

        return candidates

    def _find_sibling_links(self, files: List[FileRecord]) -> List[LinkCandidate]:
        """Find files in the same folder that are likely related."""
        candidates = []

        # Group files by parent folder
        by_parent: Dict[str, List[FileRecord]] = {}
        for f in files:
            if f.is_dir:
                continue
            if f.parent_path not in by_parent:
                by_parent[f.parent_path] = []
            by_parent[f.parent_path].append(f)

        for parent_path, siblings in by_parent.items():
            if len(siblings) < 2:
                continue

            # Find data files and their potential notes
            data_files = [f for f in siblings
                         if f.ext.lower() in {e.lstrip('.') for e in self.DATA_EXTENSIONS}]
            doc_files = [f for f in siblings
                        if f.category in (FileCategory.DOCUMENTS, FileCategory.SPREADSHEETS)]

            # Link docs to data files in same folder
            for doc in doc_files:
                for data in data_files:
                    # Check for similar names (same stem)
                    doc_stem = Path(doc.name).stem.lower()
                    data_stem = Path(data.name).stem.lower()

                    if doc_stem == data_stem:
                        # Exact stem match - high confidence
                        candidates.append(LinkCandidate(
                            src_file_id=doc.file_id,
                            dst_file_id=data.file_id,
                            relation_type=EdgeType.NOTES_FOR,
                            confidence=0.85,
                            evidence=f"Same folder, matching name: {doc_stem}",
                            rule_name="sibling_name_match"
                        ))
                    elif doc_stem in data_stem or data_stem in doc_stem:
                        # Partial match - medium confidence
                        candidates.append(LinkCandidate(
                            src_file_id=doc.file_id,
                            dst_file_id=data.file_id,
                            relation_type=EdgeType.NOTES_FOR,
                            confidence=0.6,
                            evidence=f"Same folder, similar name",
                            rule_name="sibling_name_match"
                        ))

        return candidates

    def _find_content_mentions(
        self,
        root_id: int,
        files: List[FileRecord],
        animal_id_to_files: Dict[str, List[FileRecord]]
    ) -> List[LinkCandidate]:
        """Find links based on content mentioning animal IDs or file names."""
        candidates = []

        # Get files with extracted content
        for file in files:
            if file.status != IndexStatus.EXTRACT_OK:
                continue

            content = self.db.get_content(file.file_id)
            if not content or not content.full_text:
                continue

            text = content.full_text.lower()

            # Look for animal ID mentions in content
            for animal_id, related_files in animal_id_to_files.items():
                # Check if this animal ID appears in the content
                if animal_id in text or f"animal {animal_id}" in text:
                    # Link to data files for this animal
                    data_files = [f for f in related_files
                                 if f.category == FileCategory.DATA and f.file_id != file.file_id]

                    for data in data_files:
                        candidates.append(LinkCandidate(
                            src_file_id=file.file_id,
                            dst_file_id=data.file_id,
                            relation_type=EdgeType.MENTIONS,
                            confidence=0.35,  # Low - animal ID in text is often noise
                            evidence=f"Content mentions animal ID: {animal_id}",
                            rule_name="content_mention"
                        ))

        return candidates

    def clear_links(self, root_id: int) -> int:
        """
        Clear all auto-generated links for a root.

        Returns the number of links removed.
        """
        files = self.db.list_files(root_id, limit=100000)
        removed = 0

        for file in files:
            edges = self.db.get_edges_from(file.file_id)
            for edge in edges:
                # Only remove rule-generated edges, not user-created ones
                if edge.created_by.startswith("rule:"):
                    try:
                        self.db.delete_edge(edge.edge_id)
                        removed += 1
                    except Exception:
                        pass  # Edge might already be deleted

        return removed

    def get_link_stats(self, root_id: int) -> Dict[str, int]:
        """Get statistics about links for a root."""
        files = self.db.list_files(root_id, limit=100000)

        total_edges = 0
        edges_by_type: Dict[str, int] = {}

        for file in files:
            edges = self.db.get_edges_from(file.file_id)
            edges.extend(self.db.get_edges_to(file.file_id))

            for edge in edges:
                total_edges += 1
                edge_type = edge.relation_type.value
                edges_by_type[edge_type] = edges_by_type.get(edge_type, 0) + 1

        return {
            'total_edges': total_edges // 2,  # Each edge counted twice
            'by_type': edges_by_type,
        }
