"""
Feature Extraction Layer for ML-ready candidate scoring.

Extracts structured features from candidate edges for:
1. Rule-based scoring
2. ML model training and inference
3. Explainable link decisions
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Optional dependency - provides better fuzzy matching
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    # Fallback: simple ratio based on common characters
    class FuzzFallback:
        @staticmethod
        def ratio(s1: str, s2: str) -> float:
            if not s1 or not s2:
                return 0.0
            s1, s2 = s1.lower(), s2.lower()
            common = sum(1 for c in s1 if c in s2)
            return 100.0 * (2.0 * common) / (len(s1) + len(s2))
    fuzz = FuzzFallback()

from ..domain.models import FileRecord, ContentRecord, LinkerStrategy, CandidateEdge
from ..domain.enums import EdgeType
from ..ports.db_port import DBPort


# Current feature schema version
FEATURE_SCHEMA_VERSION = 1


@dataclass
class FeatureVector:
    """Complete feature vector for a candidate edge."""
    # A) Path/name similarity features
    exact_basename_match: int = 0          # 0 or 1
    normalized_basename_match: int = 0     # 0 or 1 (after normalization)
    edit_distance: int = 0                 # Levenshtein distance
    rapidfuzz_ratio: float = 0.0           # 0-100 fuzzy ratio
    numeric_suffix_delta: Optional[int] = None  # Difference in numeric suffixes
    same_folder: int = 0                   # 0 or 1
    parent_folder: int = 0                 # 0 or 1 (share parent)
    sibling_folder: int = 0                # 0 or 1 (share grandparent)
    path_depth_difference: int = 0         # Absolute difference in path depth
    common_ancestor_depth: int = 0         # Depth of deepest common ancestor

    # B) Evidence quality features
    evidence_type: str = "proximity_only"  # explicit_mention|column_cell|inferred_sequence|proximity_only
    evidence_strength: float = 0.0         # 0-1 derived from evidence type
    has_canonical_column_match: int = 0    # 0 or 1
    column_header_similarity: float = 0.0  # Best match to known column headers
    evidence_span_length: int = 0          # Length of evidence text

    # C) Context agreement features
    date_token_agreement: float = 0.0      # 0-1 score
    animal_id_agreement: float = 0.0       # 0-1 score
    chamber_agreement: float = 0.0         # 0-1 score
    video_filename_agreement: float = 0.0  # 0-1 score
    abf_header_signature_match: float = 0.0  # 0-1 score

    # D) Uniqueness/conflict features
    num_candidates_for_src: int = 1        # How many candidates share this source
    num_candidates_for_dst: int = 1        # How many candidates share this destination
    violates_one_to_one: int = 0           # 0 or 1
    dst_already_linked: int = 0            # 0 or 1 (destination has confirmed edge)

    # E) Context-aware features (from context window reading)
    context_mouse_id_match: float = 0.0    # Mouse/animal ID found in context around reference
    context_date_match: float = 0.0        # Date matches in context
    context_channel_agreement: float = 0.0 # Channel descriptions match
    context_explicit_reference: int = 0    # 1 if explicit filename in context
    context_section_type: str = ""         # "recording_log", "setup_notes", etc.
    context_lines_analyzed: int = 0        # How many lines of context were analyzed
    context_confidence: float = 0.0        # Overall confidence from context analysis

    # F) Timestamp proximity features (file creation/modification times)
    time_created_delta_hours: Optional[float] = None   # Hours between creation times
    time_modified_delta_hours: Optional[float] = None  # Hours between modification times
    created_within_1h: int = 0             # 0 or 1: created within 1 hour of each other
    created_within_24h: int = 0            # 0 or 1: created within 24 hours
    created_within_7d: int = 0             # 0 or 1: created within 7 days
    modified_within_1h: int = 0            # 0 or 1: modified within 1 hour
    modified_within_24h: int = 0           # 0 or 1: modified within 24 hours
    src_size_bytes: int = 0                # Source file size (for learning size patterns)
    dst_size_bytes: int = 0                # Destination file size

    # G) Supervision signals (added during labeling)
    user_label: Optional[str] = None       # accepted|rejected|unknown
    auditor_verdict: Optional[str] = None  # accept|reject|needs_more_info
    auditor_confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            # Path/name similarity
            "exact_basename_match": self.exact_basename_match,
            "normalized_basename_match": self.normalized_basename_match,
            "edit_distance": self.edit_distance,
            "rapidfuzz_ratio": self.rapidfuzz_ratio,
            "numeric_suffix_delta": self.numeric_suffix_delta,
            "same_folder": self.same_folder,
            "parent_folder": self.parent_folder,
            "sibling_folder": self.sibling_folder,
            "path_depth_difference": self.path_depth_difference,
            "common_ancestor_depth": self.common_ancestor_depth,
            # Evidence quality
            "evidence_type": self.evidence_type,
            "evidence_strength": self.evidence_strength,
            "has_canonical_column_match": self.has_canonical_column_match,
            "column_header_similarity": self.column_header_similarity,
            "evidence_span_length": self.evidence_span_length,
            # Context agreement
            "date_token_agreement": self.date_token_agreement,
            "animal_id_agreement": self.animal_id_agreement,
            "chamber_agreement": self.chamber_agreement,
            "video_filename_agreement": self.video_filename_agreement,
            "abf_header_signature_match": self.abf_header_signature_match,
            # Uniqueness/conflict
            "num_candidates_for_src": self.num_candidates_for_src,
            "num_candidates_for_dst": self.num_candidates_for_dst,
            "violates_one_to_one": self.violates_one_to_one,
            "dst_already_linked": self.dst_already_linked,
            # Context-aware features
            "context_mouse_id_match": self.context_mouse_id_match,
            "context_date_match": self.context_date_match,
            "context_channel_agreement": self.context_channel_agreement,
            "context_explicit_reference": self.context_explicit_reference,
            "context_section_type": self.context_section_type,
            "context_lines_analyzed": self.context_lines_analyzed,
            "context_confidence": self.context_confidence,
            # Timestamp proximity features
            "time_created_delta_hours": self.time_created_delta_hours,
            "time_modified_delta_hours": self.time_modified_delta_hours,
            "created_within_1h": self.created_within_1h,
            "created_within_24h": self.created_within_24h,
            "created_within_7d": self.created_within_7d,
            "modified_within_1h": self.modified_within_1h,
            "modified_within_24h": self.modified_within_24h,
            "src_size_bytes": self.src_size_bytes,
            "dst_size_bytes": self.dst_size_bytes,
            # Supervision
            "user_label": self.user_label,
            "auditor_verdict": self.auditor_verdict,
            "auditor_confidence": self.auditor_confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureVector":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class FeatureExtractor:
    """
    Extract ML-ready features from candidate edges.

    Features are grouped into categories:
    A) Path/name similarity - Structural relationship between files
    B) Evidence quality - Strength and type of linking evidence
    C) Context agreement - Token matching (dates, IDs, etc.)
    D) Uniqueness/conflict - Relationship to other candidates
    E) Supervision signals - Labels from user/auditor (added later)
    """

    # Token extraction patterns
    DATE_PATTERN = r'(\d{4}[-/]?\d{2}[-/]?\d{2}|\d{8})'
    ANIMAL_ID_PATTERN = r'(?:animal|mouse|rat|id)[_\-\s]*(\d{3,5})|[_\-](\d{3,4})[_\-]'
    CHAMBER_PATTERN = r'(?:chamber|ch)[_\-\s]*([A-D]|\d{1,2})'
    NUMERIC_SUFFIX_PATTERN = r'(\d{3,})(?:\.\w+)?$'

    # Common column header synonyms for surgery notes
    CANONICAL_COLUMNS = {
        "data_file": ["pleth file", "data file", "recording file", "abf file", "file name"],
        "animal_id": ["animal id", "mouse id", "rat id", "subject id", "id", "animal"],
        "date": ["date", "recording date", "surgery date", "experiment date"],
        "chamber": ["chamber", "box", "recording chamber"],
        "strain": ["strain", "genotype", "mouse line"],
    }

    def __init__(self, db: DBPort):
        """Initialize with database access."""
        self.db = db

    def extract(
        self,
        src: FileRecord,
        dst: FileRecord,
        evidence: Dict[str, Any],
        strategy: Optional[LinkerStrategy] = None
    ) -> FeatureVector:
        """
        Extract complete feature vector for a candidate edge.

        Args:
            src: Source file record
            dst: Destination file record
            evidence: Evidence dict from candidate generation
            strategy: Optional linking strategy for additional patterns

        Returns:
            FeatureVector with all extracted features
        """
        features = FeatureVector()

        # A) Path/name similarity
        self._extract_path_features(src, dst, features)

        # B) Evidence quality
        self._extract_evidence_features(evidence, strategy, features)

        # C) Context agreement
        self._extract_context_features(src, dst, strategy, features)

        # D) Timestamp proximity
        self._extract_timestamp_features(src, dst, features)

        return features

    def _extract_path_features(
        self,
        src: FileRecord,
        dst: FileRecord,
        features: FeatureVector
    ) -> None:
        """Extract path and filename similarity features."""
        # Exact basename match
        src_stem = Path(src.name).stem.lower()
        dst_stem = Path(dst.name).stem.lower()
        features.exact_basename_match = 1 if src_stem == dst_stem else 0

        # Normalized basename match (remove common prefixes/suffixes)
        src_norm = self._normalize_filename(src_stem)
        dst_norm = self._normalize_filename(dst_stem)
        features.normalized_basename_match = 1 if src_norm == dst_norm else 0

        # Edit distance
        features.edit_distance = self._levenshtein(src_stem, dst_stem)

        # Fuzzy ratio using rapidfuzz
        features.rapidfuzz_ratio = fuzz.ratio(src_stem, dst_stem)

        # Numeric suffix delta
        src_suffix = self._extract_numeric_suffix(src.name)
        dst_suffix = self._extract_numeric_suffix(dst.name)
        if src_suffix is not None and dst_suffix is not None:
            features.numeric_suffix_delta = abs(src_suffix - dst_suffix)

        # Path relationship
        src_parts = Path(src.path).parts
        dst_parts = Path(dst.path).parts

        # Same folder?
        src_parent = Path(src.path).parent
        dst_parent = Path(dst.path).parent
        features.same_folder = 1 if src_parent == dst_parent else 0

        # Share parent (siblings)?
        if len(src_parts) > 1 and len(dst_parts) > 1:
            if src_parts[:-1] == dst_parts[:-1]:
                features.parent_folder = 1

        # Share grandparent?
        if len(src_parts) > 2 and len(dst_parts) > 2:
            if src_parts[:-2] == dst_parts[:-2]:
                features.sibling_folder = 1

        # Path depth difference
        features.path_depth_difference = abs(len(src_parts) - len(dst_parts))

        # Common ancestor depth
        common = 0
        for sp, dp in zip(src_parts, dst_parts):
            if sp.lower() == dp.lower():
                common += 1
            else:
                break
        features.common_ancestor_depth = common

    def _extract_evidence_features(
        self,
        evidence: Dict[str, Any],
        strategy: Optional[LinkerStrategy],
        features: FeatureVector
    ) -> None:
        """Extract evidence quality features."""
        evidence_type = evidence.get("type", "proximity_only")
        features.evidence_type = evidence_type

        # Evidence strength based on type
        strength_map = {
            "explicit_mention": 1.0,
            "column_cell": 0.85,
            "inferred_sequence": 0.6,
            "proximity_only": 0.3,
        }
        features.evidence_strength = strength_map.get(evidence_type, 0.3)

        # Canonical column match
        if "column_header" in evidence:
            header = evidence["column_header"].lower()
            for canonical, synonyms in self.CANONICAL_COLUMNS.items():
                if any(syn in header for syn in synonyms):
                    features.has_canonical_column_match = 1
                    features.column_header_similarity = 1.0
                    break
            else:
                # Fuzzy match against all known headers
                all_synonyms = [s for syns in self.CANONICAL_COLUMNS.values() for s in syns]
                best_match = max(fuzz.ratio(header, syn) for syn in all_synonyms)
                features.column_header_similarity = best_match / 100.0

        # Evidence span length
        if "excerpt" in evidence:
            features.evidence_span_length = len(evidence["excerpt"])
        elif "evidence_text" in evidence:
            features.evidence_span_length = len(evidence["evidence_text"])

    def _extract_context_features(
        self,
        src: FileRecord,
        dst: FileRecord,
        strategy: Optional[LinkerStrategy],
        features: FeatureVector
    ) -> None:
        """Extract context agreement features (token matching)."""
        # Get content for both files if available
        src_content = self.db.get_content(src.file_id)
        dst_content = self.db.get_content(dst.file_id)

        # Build token sets from paths and content
        src_tokens = self._extract_all_tokens(src.path, src.name, src_content)
        dst_tokens = self._extract_all_tokens(dst.path, dst.name, dst_content)

        # Use strategy patterns if provided, otherwise use defaults
        date_pattern = self.DATE_PATTERN
        animal_pattern = self.ANIMAL_ID_PATTERN
        chamber_pattern = self.CHAMBER_PATTERN

        if strategy:
            date_pattern = strategy.token_patterns.get("date", date_pattern)
            animal_pattern = strategy.token_patterns.get("animal_id", animal_pattern)
            chamber_pattern = strategy.token_patterns.get("chamber", chamber_pattern)

        # Date agreement
        src_dates = set(re.findall(date_pattern, src_tokens))
        dst_dates = set(re.findall(date_pattern, dst_tokens))
        if src_dates and dst_dates:
            overlap = len(src_dates & dst_dates)
            features.date_token_agreement = overlap / max(len(src_dates), len(dst_dates))

        # Animal ID agreement
        src_animals = set()
        dst_animals = set()
        for match in re.finditer(animal_pattern, src_tokens, re.IGNORECASE):
            src_animals.add(match.group(1) or match.group(2))
        for match in re.finditer(animal_pattern, dst_tokens, re.IGNORECASE):
            dst_animals.add(match.group(1) or match.group(2))

        if src_animals and dst_animals:
            overlap = len(src_animals & dst_animals)
            features.animal_id_agreement = overlap / max(len(src_animals), len(dst_animals))

        # Chamber agreement
        src_chambers = set(re.findall(chamber_pattern, src_tokens, re.IGNORECASE))
        dst_chambers = set(re.findall(chamber_pattern, dst_tokens, re.IGNORECASE))
        if src_chambers and dst_chambers:
            overlap = len(src_chambers & dst_chambers)
            features.chamber_agreement = overlap / max(len(src_chambers), len(dst_chambers))

    def _extract_timestamp_features(
        self,
        src: FileRecord,
        dst: FileRecord,
        features: FeatureVector
    ) -> None:
        """
        Extract timestamp proximity features.

        These features capture temporal relationships between files,
        which can indicate they were created as part of the same experiment.
        """
        # Store file sizes (useful for learning size patterns)
        features.src_size_bytes = src.size_bytes
        features.dst_size_bytes = dst.size_bytes

        # Creation time proximity
        if src.ctime and dst.ctime:
            delta = abs((src.ctime - dst.ctime).total_seconds())
            delta_hours = delta / 3600.0
            features.time_created_delta_hours = delta_hours

            # Boolean thresholds
            features.created_within_1h = 1 if delta_hours <= 1.0 else 0
            features.created_within_24h = 1 if delta_hours <= 24.0 else 0
            features.created_within_7d = 1 if delta_hours <= (24.0 * 7) else 0

        # Modification time proximity
        if src.mtime and dst.mtime:
            delta = abs((src.mtime - dst.mtime).total_seconds())
            delta_hours = delta / 3600.0
            features.time_modified_delta_hours = delta_hours

            # Boolean thresholds
            features.modified_within_1h = 1 if delta_hours <= 1.0 else 0
            features.modified_within_24h = 1 if delta_hours <= 24.0 else 0

    def update_conflict_features(
        self,
        candidate: CandidateEdge,
        all_candidates: List[CandidateEdge],
        confirmed_edges: Dict[int, List[int]]  # dst_file_id -> [src_file_ids]
    ) -> FeatureVector:
        """
        Update uniqueness/conflict features based on other candidates.

        Args:
            candidate: The candidate to update
            all_candidates: All candidates in the current batch
            confirmed_edges: Map of dst_file_id to confirmed source file IDs

        Returns:
            Updated feature vector
        """
        features = FeatureVector.from_dict(candidate.features)

        # Count candidates sharing source
        features.num_candidates_for_src = sum(
            1 for c in all_candidates if c.src_file_id == candidate.src_file_id
        )

        # Count candidates sharing destination
        features.num_candidates_for_dst = sum(
            1 for c in all_candidates if c.dst_file_id == candidate.dst_file_id
        )

        # Check one-to-one violation
        if features.num_candidates_for_dst > 1:
            features.violates_one_to_one = 1

        # Check if destination already has confirmed link
        if candidate.dst_file_id in confirmed_edges:
            features.dst_already_linked = 1

        return features

    def compute_score(self, features: FeatureVector, strategy: Optional[LinkerStrategy] = None) -> float:
        """
        Compute confidence score from feature vector.

        Uses weighted rule-based scoring. Can be replaced with ML model later.

        Args:
            features: Extracted feature vector
            strategy: Optional strategy with custom thresholds

        Returns:
            Score between 0.0 and 1.0
        """
        # Base weights for each feature category
        score = 0.0

        # A) Path/name similarity (max 0.3)
        path_score = 0.0
        if features.exact_basename_match:
            path_score += 0.15
        elif features.normalized_basename_match:
            path_score += 0.10
        path_score += (features.rapidfuzz_ratio / 100.0) * 0.10
        if features.same_folder:
            path_score += 0.05
        elif features.parent_folder:
            path_score += 0.03
        score += min(path_score, 0.3)

        # B) Evidence quality (max 0.4)
        evidence_score = features.evidence_strength * 0.3
        if features.has_canonical_column_match:
            evidence_score += 0.10
        score += min(evidence_score, 0.4)

        # C) Context agreement (max 0.25)
        context_score = 0.0
        context_score += features.date_token_agreement * 0.10
        context_score += features.animal_id_agreement * 0.10
        context_score += features.chamber_agreement * 0.05
        score += min(context_score, 0.25)

        # D) Conflict penalties (reduce up to 0.2)
        conflict_penalty = 0.0
        if features.violates_one_to_one:
            conflict_penalty += 0.10
        if features.dst_already_linked:
            conflict_penalty += 0.10
        score -= conflict_penalty

        return max(0.0, min(1.0, score))

    def compute_soft_score(
        self,
        features: FeatureVector,
        strategy: Optional[LinkerStrategy] = None
    ) -> "ScoringResult":
        """
        Compute confidence score with full explainability.

        Uses weighted soft scoring where each feature contributes
        a probabilistic score. Returns detailed breakdown.

        Args:
            features: Extracted feature vector
            strategy: Optional strategy with custom weights

        Returns:
            ScoringResult with total score and breakdown
        """
        from ..domain.models import SoftScore, ScoringResult

        breakdown = []
        flags = []

        # Get weights from strategy or use defaults
        weights = self._get_default_weights()
        if strategy and strategy.feature_weights:
            weights.update(strategy.feature_weights)

        # A) Path/name similarity features
        # Exact basename match
        raw = float(features.exact_basename_match)
        weight = weights.get("exact_basename_match", 0.15)
        breakdown.append(SoftScore(
            feature_name="exact_basename_match",
            raw_value=raw,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation="Exact filename match" if raw else "No exact match"
        ))

        # Rapidfuzz ratio
        raw = features.rapidfuzz_ratio / 100.0
        weight = weights.get("rapidfuzz_ratio", 0.10)
        breakdown.append(SoftScore(
            feature_name="rapidfuzz_ratio",
            raw_value=features.rapidfuzz_ratio,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation=f"Fuzzy name similarity: {features.rapidfuzz_ratio:.0f}%"
        ))

        # Same folder
        raw = float(features.same_folder)
        weight = weights.get("same_folder", 0.05)
        breakdown.append(SoftScore(
            feature_name="same_folder",
            raw_value=raw,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation="Same folder" if raw else "Different folders"
        ))

        # B) Evidence quality features
        # Evidence strength
        raw = features.evidence_strength
        weight = weights.get("evidence_strength", 0.30)
        breakdown.append(SoftScore(
            feature_name="evidence_strength",
            raw_value=raw,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation=f"Evidence type: {features.evidence_type}"
        ))

        # Canonical column match
        raw = float(features.has_canonical_column_match)
        weight = weights.get("has_canonical_column_match", 0.10)
        breakdown.append(SoftScore(
            feature_name="has_canonical_column_match",
            raw_value=raw,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation="Found in standard file column" if raw else "No column match"
        ))

        # C) Context agreement features
        # Date agreement
        raw = features.date_token_agreement
        weight = weights.get("date_token_agreement", 0.10)
        breakdown.append(SoftScore(
            feature_name="date_token_agreement",
            raw_value=raw,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation=f"Date agreement: {raw:.0%}" if raw > 0 else "No date match"
        ))

        # Animal ID agreement
        raw = features.animal_id_agreement
        weight = weights.get("animal_id_agreement", 0.10)
        breakdown.append(SoftScore(
            feature_name="animal_id_agreement",
            raw_value=raw,
            normalized_value=raw,
            weight=weight,
            contribution=raw * weight,
            explanation=f"Animal ID agreement: {raw:.0%}" if raw > 0 else "No animal ID match"
        ))

        # Context-aware features (new)
        if features.context_explicit_reference:
            raw = 1.0
            weight = weights.get("context_explicit_reference", 0.15)
            breakdown.append(SoftScore(
                feature_name="context_explicit_reference",
                raw_value=raw,
                normalized_value=raw,
                weight=weight,
                contribution=raw * weight,
                explanation="Explicit reference in context"
            ))

        if features.context_confidence > 0:
            raw = features.context_confidence
            weight = weights.get("context_confidence", 0.10)
            breakdown.append(SoftScore(
                feature_name="context_confidence",
                raw_value=raw,
                normalized_value=raw,
                weight=weight,
                contribution=raw * weight,
                explanation=f"Context analysis confidence: {raw:.0%}"
            ))

        # D) Timestamp proximity features
        if features.created_within_24h:
            raw = 1.0
            weight = weights.get("created_within_24h", 0.08)
            breakdown.append(SoftScore(
                feature_name="created_within_24h",
                raw_value=raw,
                normalized_value=raw,
                weight=weight,
                contribution=raw * weight,
                explanation="Files created within 24 hours of each other"
            ))
        elif features.created_within_7d:
            raw = 1.0
            weight = weights.get("created_within_7d", 0.04)
            breakdown.append(SoftScore(
                feature_name="created_within_7d",
                raw_value=raw,
                normalized_value=raw,
                weight=weight,
                contribution=raw * weight,
                explanation="Files created within 7 days of each other"
            ))

        if features.modified_within_24h:
            raw = 1.0
            weight = weights.get("modified_within_24h", 0.03)
            breakdown.append(SoftScore(
                feature_name="modified_within_24h",
                raw_value=raw,
                normalized_value=raw,
                weight=weight,
                contribution=raw * weight,
                explanation="Files modified within 24 hours of each other"
            ))

        # E) Conflict penalties (negative contributions)
        if features.violates_one_to_one:
            weight = weights.get("violates_one_to_one", -0.10)
            breakdown.append(SoftScore(
                feature_name="violates_one_to_one",
                raw_value=1.0,
                normalized_value=1.0,
                weight=weight,
                contribution=weight,  # Negative contribution
                explanation="WARNING: Multiple candidates for same target"
            ))
            flags.append("one_to_one_conflict")

        if features.dst_already_linked:
            weight = weights.get("dst_already_linked", -0.10)
            breakdown.append(SoftScore(
                feature_name="dst_already_linked",
                raw_value=1.0,
                normalized_value=1.0,
                weight=weight,
                contribution=weight,  # Negative contribution
                explanation="WARNING: Target already has confirmed link"
            ))
            flags.append("already_linked")

        # Calculate total score
        total = sum(s.contribution for s in breakdown)
        total = max(0.0, min(1.0, total))

        # Determine confidence level
        if total >= 0.8:
            confidence_level = "high"
        elif total >= 0.5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        return ScoringResult(
            total_score=total,
            score_breakdown=breakdown,
            confidence_level=confidence_level,
            flags=flags,
        )

    def _get_default_weights(self) -> Dict[str, float]:
        """Get default feature weights for soft scoring."""
        return {
            # Path/name similarity (total ~0.30)
            "exact_basename_match": 0.15,
            "normalized_basename_match": 0.10,
            "rapidfuzz_ratio": 0.10,
            "same_folder": 0.05,
            "parent_folder": 0.03,
            # Evidence quality (total ~0.40)
            "evidence_strength": 0.30,
            "has_canonical_column_match": 0.10,
            # Context agreement (total ~0.25)
            "date_token_agreement": 0.10,
            "animal_id_agreement": 0.10,
            "chamber_agreement": 0.05,
            # Context-aware features (total ~0.25)
            "context_explicit_reference": 0.15,
            "context_confidence": 0.10,
            "context_mouse_id_match": 0.10,
            "context_date_match": 0.10,
            # Timestamp proximity (total ~0.15)
            "created_within_24h": 0.08,
            "created_within_7d": 0.04,
            "modified_within_24h": 0.03,
            # Conflict penalties (negative)
            "violates_one_to_one": -0.10,
            "dst_already_linked": -0.10,
        }

    def extract_context_features(
        self,
        features: FeatureVector,
        context_data: Dict[str, Any]
    ) -> FeatureVector:
        """
        Enrich feature vector with context-aware features.

        Args:
            features: Base feature vector
            context_data: Context data from ContextReader

        Returns:
            Updated feature vector
        """
        # Update context features from context_data
        if "mouse_id_match" in context_data:
            features.context_mouse_id_match = float(context_data["mouse_id_match"])

        if "date_match" in context_data:
            features.context_date_match = float(context_data["date_match"])

        if "channel_agreement" in context_data:
            features.context_channel_agreement = float(context_data["channel_agreement"])

        if "explicit_reference" in context_data:
            features.context_explicit_reference = 1 if context_data["explicit_reference"] else 0

        if "section_type" in context_data:
            features.context_section_type = str(context_data["section_type"])

        if "lines_analyzed" in context_data:
            features.context_lines_analyzed = int(context_data["lines_analyzed"])

        if "confidence" in context_data:
            features.context_confidence = float(context_data["confidence"])

        return features

    def export_training_set(
        self,
        relation_type: Optional[str] = None,
        min_confidence: float = 0.0,
        include_rejected: bool = True,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Export labeled candidate features for ML training.

        Args:
            relation_type: Filter by relation type (optional)
            min_confidence: Minimum original confidence threshold
            include_rejected: Whether to include rejected candidates
            output_path: Output file path (default: training_set_{timestamp}.csv)

        Returns:
            Path to the exported CSV file
        """
        import csv

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"training_set_{timestamp}.csv")

        # Get labeled candidates
        statuses = ["accepted"]
        if include_rejected:
            statuses.append("rejected")

        candidates = []
        for status in statuses:
            candidates.extend(self.db.list_candidate_edges(status=status, limit=10000))

        if relation_type:
            candidates = [c for c in candidates if c.relation_type.value == relation_type]

        if min_confidence > 0:
            candidates = [c for c in candidates if c.confidence >= min_confidence]

        # Export to CSV
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = None
            for candidate in candidates:
                features = FeatureVector.from_dict(candidate.features)
                # Add supervision label
                features.user_label = candidate.status.value

                row = features.to_dict()
                row["candidate_id"] = candidate.candidate_id
                row["src_file_id"] = candidate.src_file_id
                row["dst_file_id"] = candidate.dst_file_id
                row["relation_type"] = candidate.relation_type.value
                row["original_confidence"] = candidate.confidence

                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=row.keys())
                    writer.writeheader()
                writer.writerow(row)

        return output_path

    # === Helper methods ===

    def _normalize_filename(self, name: str) -> str:
        """Normalize filename for comparison."""
        # Remove common prefixes/suffixes
        name = re.sub(r'^(\d{8}|\d{6})', '', name)  # Date prefixes
        name = re.sub(r'_\d{3}$', '', name)  # Numeric suffixes
        name = re.sub(r'[-_]', '', name)  # Separators
        return name.lower()

    def _extract_numeric_suffix(self, filename: str) -> Optional[int]:
        """Extract numeric suffix from filename."""
        match = re.search(self.NUMERIC_SUFFIX_PATTERN, filename, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _extract_all_tokens(
        self,
        path: str,
        name: str,
        content: Optional[ContentRecord]
    ) -> str:
        """Combine path, name, and content for token extraction."""
        parts = [path, name]
        if content:
            if content.title:
                parts.append(content.title)
            if content.summary:
                parts.append(content.summary)
            if content.content_excerpt:
                parts.append(content.content_excerpt)
        return " ".join(parts)

    def _levenshtein(self, s1: str, s2: str) -> int:
        """Compute Levenshtein edit distance."""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
