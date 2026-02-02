"""
Linker Trainer Service - LLM-assisted linking strategy builder.

Helps users create custom linking strategies by:
1. Analyzing folder structure and file patterns
2. Proposing column mappings and token patterns via LLM
3. Testing strategies on sample files
4. Storing versioned strategies for reproducibility
"""

import re
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import Counter

from ..domain.models import FileRecord, ContentRecord, LinkerStrategy
from ..domain.enums import FileCategory, EdgeType
from ..ports.db_port import DBPort
from ..ports.llm_port import LLMPort


@dataclass
class FolderAnalysis:
    """Analysis results for a folder subtree."""
    folder_path: str
    file_count: int = 0
    dir_count: int = 0
    file_extensions: Dict[str, int] = field(default_factory=dict)
    categories: Dict[str, int] = field(default_factory=dict)
    filename_patterns: List[str] = field(default_factory=list)
    sample_filenames: List[str] = field(default_factory=list)
    detected_tokens: Dict[str, List[str]] = field(default_factory=dict)
    column_headers: List[str] = field(default_factory=list)  # From spreadsheets

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM prompt."""
        return {
            "folder_path": self.folder_path,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "extensions": self.file_extensions,
            "categories": self.categories,
            "filename_patterns": self.filename_patterns,
            "sample_filenames": self.sample_filenames[:20],
            "detected_tokens": {k: v[:10] for k, v in self.detected_tokens.items()},
            "column_headers": self.column_headers[:20],
        }


@dataclass
class StrategyEvaluation:
    """Results from evaluating a strategy on test files."""
    strategy_name: str
    strategy_version: int
    files_tested: int
    candidates_generated: int
    high_confidence_count: int  # Above promote threshold
    medium_confidence_count: int  # Between candidate and promote
    low_confidence_count: int  # Below candidate threshold
    sample_matches: List[Dict[str, Any]] = field(default_factory=list)
    potential_issues: List[str] = field(default_factory=list)


class LinkerTrainer:
    """
    LLM-assisted linking strategy builder.

    Workflow:
    1. User selects source and destination folders
    2. analyze_branch() samples files and summarizes conventions
    3. propose_strategy() uses LLM to generate JSON strategy
    4. evaluate_strategy() tests on sample files
    5. User reviews samples and activates strategy
    """

    # Token patterns for automatic detection
    DETECTION_PATTERNS = {
        "date": [
            r'(\d{4}[-/]\d{2}[-/]\d{2})',  # 2024-01-15
            r'(\d{8})',                     # 20240115
            r'(\d{2}[-/]\d{2}[-/]\d{4})',  # 01-15-2024
        ],
        "animal_id": [
            r'(?:animal|mouse|rat|subject)[_\-\s]*(\d{3,5})',
            r'(?:id|ID)[_\-\s]*(\d{3,5})',
            r'[_\-](\d{3,4})[_\-]',
        ],
        "chamber": [
            r'(?:chamber|ch|box)[_\-\s]*([A-D])',
            r'(?:chamber|ch|box)[_\-\s]*(\d{1,2})',
        ],
        "sequence": [
            r'(\d{3})\.abf$',  # ABF file numbering
            r'[_\-](\d{3,4})$',  # Generic sequence
        ],
    }

    # LLM prompt template for strategy proposal
    STRATEGY_PROMPT = """You are helping a researcher create a linking strategy to connect data files with their associated notes/metadata.

## Source Folder Analysis
{src_analysis}

## Destination Folder Analysis
{dst_analysis}

## Task
Create a JSON linking strategy that will help match files from the source folder to files in the destination folder.

The strategy should include:
1. **column_mappings**: Map column headers in spreadsheets to canonical field names (data_file, animal_id, date, chamber, strain)
2. **token_patterns**: Regex patterns for extracting key tokens (dates, animal IDs, chambers, etc.)
3. **thresholds**: Score thresholds for promoting candidates to links
4. **folder_rules**: Patterns describing typical source/destination folder organization

Based on the file patterns and column headers detected, propose a strategy.

Return ONLY a valid JSON object with this structure:
{{
    "name": "descriptive strategy name",
    "description": "brief description of what this strategy links",
    "relation_type": "notes_for",
    "column_mappings": {{
        "column_header_pattern": "canonical_field"
    }},
    "token_patterns": {{
        "animal_id": "regex_pattern",
        "date": "regex_pattern",
        "chamber": "regex_pattern"
    }},
    "thresholds": {{
        "promote": 0.8,
        "candidate": 0.4,
        "reject": 0.2
    }},
    "folder_rules": {{
        "src_pattern": "description of source folder structure",
        "dst_pattern": "description of destination folder structure"
    }}
}}
"""

    def __init__(self, db: DBPort, llm: Optional[LLMPort] = None):
        """
        Initialize the linker trainer.

        Args:
            db: Database port for file access
            llm: Optional LLM port for strategy proposals
        """
        self.db = db
        self.llm = llm

    def analyze_branch(
        self,
        root_id: int,
        folder_path: str,
        sample_size: int = 50
    ) -> FolderAnalysis:
        """
        Analyze a folder subtree to understand its conventions.

        Args:
            root_id: Root ID containing the folder
            folder_path: Path to the folder (relative to root)
            sample_size: Maximum files to sample for patterns

        Returns:
            FolderAnalysis with detected patterns
        """
        analysis = FolderAnalysis(folder_path=folder_path)

        # Get all files under this path
        all_files = self.db.list_files(root_id, limit=10000)
        files = [f for f in all_files if f.path.startswith(folder_path)]

        # Basic counts
        analysis.file_count = sum(1 for f in files if not f.is_dir)
        analysis.dir_count = sum(1 for f in files if f.is_dir)

        # Extension distribution
        ext_counts: Counter = Counter()
        for f in files:
            if not f.is_dir:
                ext_counts[f.ext.lower()] += 1
        analysis.file_extensions = dict(ext_counts.most_common(10))

        # Category distribution
        cat_counts: Counter = Counter()
        for f in files:
            if not f.is_dir:
                cat_counts[f.category.value] += 1
        analysis.categories = dict(cat_counts)

        # Sample filenames
        file_only = [f for f in files if not f.is_dir]
        sample = file_only[:sample_size]
        analysis.sample_filenames = [f.name for f in sample]

        # Detect filename patterns
        analysis.filename_patterns = self._detect_filename_patterns(sample)

        # Extract tokens from paths and filenames
        combined_text = " ".join(f.path + " " + f.name for f in sample)
        analysis.detected_tokens = self._extract_tokens(combined_text)

        # Extract column headers from spreadsheets
        analysis.column_headers = self._extract_column_headers(sample)

        return analysis

    def propose_strategy(
        self,
        src_analysis: FolderAnalysis,
        dst_analysis: FolderAnalysis,
        relation_type: EdgeType = EdgeType.NOTES_FOR
    ) -> Optional[LinkerStrategy]:
        """
        Use LLM to propose a linking strategy based on folder analysis.

        Args:
            src_analysis: Analysis of source folder
            dst_analysis: Analysis of destination folder
            relation_type: Type of relationship to create

        Returns:
            Proposed LinkerStrategy or None if LLM unavailable
        """
        if self.llm is None:
            return self._propose_rule_based_strategy(src_analysis, dst_analysis, relation_type)

        # Build prompt
        prompt = self.STRATEGY_PROMPT.format(
            src_analysis=json.dumps(src_analysis.to_dict(), indent=2),
            dst_analysis=json.dumps(dst_analysis.to_dict(), indent=2),
        )

        try:
            response = self.llm.query(prompt)
            strategy_json = self._parse_json_response(response)

            if strategy_json:
                return LinkerStrategy(
                    strategy_id=0,  # Will be set by DB
                    name=strategy_json.get("name", "Untitled Strategy"),
                    version=1,
                    description=strategy_json.get("description"),
                    strategy_config=strategy_json,
                    src_folder_pattern=src_analysis.folder_path,
                    dst_folder_pattern=dst_analysis.folder_path,
                    relation_type=EdgeType(strategy_json.get("relation_type", "notes_for")),
                    is_active=False,
                )
        except Exception as e:
            print(f"[LinkerTrainer] LLM error: {e}")

        # Fallback to rule-based
        return self._propose_rule_based_strategy(src_analysis, dst_analysis, relation_type)

    def evaluate_strategy(
        self,
        strategy: LinkerStrategy,
        root_id: int,
        test_file_count: int = 20
    ) -> StrategyEvaluation:
        """
        Test a strategy on sample files and report results.

        Args:
            strategy: Strategy to evaluate
            root_id: Root ID containing files
            test_file_count: Number of files to test

        Returns:
            StrategyEvaluation with results
        """
        evaluation = StrategyEvaluation(
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            files_tested=0,
            candidates_generated=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
        )

        # Get files from source and destination folders
        all_files = self.db.list_files(root_id, limit=10000)

        src_files = [f for f in all_files
                     if f.path.startswith(strategy.src_folder_pattern or "")
                     and not f.is_dir][:test_file_count]

        dst_files = [f for f in all_files
                     if f.path.startswith(strategy.dst_folder_pattern or "")
                     and not f.is_dir]

        evaluation.files_tested = len(src_files)
        thresholds = strategy.thresholds

        # Import feature extractor for scoring
        from .feature_extractor import FeatureExtractor
        feature_extractor = FeatureExtractor(self.db)

        # Test each source file
        for src in src_files:
            # Extract tokens from source
            src_tokens = self._extract_tokens(src.path + " " + src.name)

            for dst in dst_files:
                # Quick match check
                dst_tokens = self._extract_tokens(dst.path + " " + dst.name)

                # Check for any token overlap
                if not self._has_token_overlap(src_tokens, dst_tokens):
                    continue

                # Build evidence
                evidence = self._build_evidence(src, dst, src_tokens, dst_tokens)

                # Extract features and score
                features = feature_extractor.extract(src, dst, evidence, strategy)
                score = feature_extractor.compute_score(features, strategy)

                evaluation.candidates_generated += 1

                if score >= thresholds.get("promote", 0.8):
                    evaluation.high_confidence_count += 1
                elif score >= thresholds.get("candidate", 0.4):
                    evaluation.medium_confidence_count += 1
                else:
                    evaluation.low_confidence_count += 1

                # Store sample matches
                if len(evaluation.sample_matches) < 10:
                    evaluation.sample_matches.append({
                        "src": src.name,
                        "dst": dst.name,
                        "score": score,
                        "evidence": evidence,
                    })

        # Detect potential issues
        if evaluation.candidates_generated == 0:
            evaluation.potential_issues.append(
                "No candidates generated. Token patterns may not match file conventions."
            )
        elif evaluation.high_confidence_count == 0:
            evaluation.potential_issues.append(
                "No high-confidence matches. Consider lowering thresholds or adjusting patterns."
            )

        ratio = evaluation.candidates_generated / max(1, evaluation.files_tested)
        if ratio > 10:
            evaluation.potential_issues.append(
                f"High candidate ratio ({ratio:.1f}). Patterns may be too permissive."
            )

        return evaluation

    def save_strategy(self, strategy: LinkerStrategy, activate: bool = False) -> LinkerStrategy:
        """
        Save a strategy to the database.

        Args:
            strategy: Strategy to save
            activate: Whether to activate this strategy

        Returns:
            Saved strategy with ID
        """
        strategy.is_active = activate
        return self.db.add_linker_strategy(strategy)

    # === Helper methods ===

    def _detect_filename_patterns(self, files: List[FileRecord]) -> List[str]:
        """Detect common filename patterns from samples."""
        patterns = []

        # Check for date prefixes
        date_prefix_count = sum(
            1 for f in files if re.match(r'^\d{8}', f.name)
        )
        if date_prefix_count > len(files) * 0.5:
            patterns.append("YYYYMMDD prefix")

        # Check for numeric suffixes (e.g., 000.abf)
        suffix_count = sum(
            1 for f in files if re.search(r'\d{3}\.\w+$', f.name)
        )
        if suffix_count > len(files) * 0.3:
            patterns.append("3-digit sequence suffix")

        # Check for animal ID patterns
        animal_count = sum(
            1 for f in files if re.search(r'(?:animal|mouse|id)[_\-]\d+', f.name, re.I)
        )
        if animal_count > len(files) * 0.2:
            patterns.append("animal/mouse ID in name")

        # Check for chamber patterns
        chamber_count = sum(
            1 for f in files if re.search(r'(?:ch|chamber)[_\-]?[A-D]', f.name, re.I)
        )
        if chamber_count > len(files) * 0.2:
            patterns.append("chamber designation (A-D)")

        return patterns

    def _extract_tokens(self, text: str) -> Dict[str, List[str]]:
        """Extract tokens using detection patterns."""
        tokens: Dict[str, Set[str]] = {k: set() for k in self.DETECTION_PATTERNS}

        for token_type, patterns in self.DETECTION_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = next((m for m in match if m), None)
                    if match:
                        tokens[token_type].add(match)

        return {k: list(v) for k, v in tokens.items()}

    def _extract_column_headers(self, files: List[FileRecord]) -> List[str]:
        """Extract column headers from spreadsheet files."""
        headers = []

        for f in files:
            if f.category == FileCategory.SPREADSHEETS:
                content = self.db.get_content(f.file_id)
                if content and content.entities:
                    # Look for column headers in entities
                    if "columns" in content.entities:
                        headers.extend(content.entities["columns"])

        return list(set(headers))

    def _has_token_overlap(
        self,
        src_tokens: Dict[str, List[str]],
        dst_tokens: Dict[str, List[str]]
    ) -> bool:
        """Check if two token sets have any overlap."""
        for token_type in src_tokens:
            src_set = set(src_tokens.get(token_type, []))
            dst_set = set(dst_tokens.get(token_type, []))
            if src_set & dst_set:
                return True
        return False

    def _build_evidence(
        self,
        src: FileRecord,
        dst: FileRecord,
        src_tokens: Dict[str, List[str]],
        dst_tokens: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Build evidence dict for a candidate match."""
        evidence = {
            "type": "proximity_only",
            "matching_tokens": {},
        }

        for token_type in src_tokens:
            src_set = set(src_tokens.get(token_type, []))
            dst_set = set(dst_tokens.get(token_type, []))
            overlap = src_set & dst_set
            if overlap:
                evidence["matching_tokens"][token_type] = list(overlap)
                evidence["type"] = "inferred_sequence"

        return evidence

    def _propose_rule_based_strategy(
        self,
        src_analysis: FolderAnalysis,
        dst_analysis: FolderAnalysis,
        relation_type: EdgeType
    ) -> LinkerStrategy:
        """Create a rule-based strategy without LLM assistance."""
        # Build column mappings from detected headers
        column_mappings = {}
        canonical_map = {
            "pleth": "data_file",
            "file": "data_file",
            "recording": "data_file",
            "animal": "animal_id",
            "mouse": "animal_id",
            "id": "animal_id",
            "date": "date",
            "chamber": "chamber",
            "strain": "strain",
        }

        for header in dst_analysis.column_headers:
            header_lower = header.lower()
            for key, canonical in canonical_map.items():
                if key in header_lower:
                    column_mappings[header.lower()] = canonical
                    break

        # Build token patterns from detected tokens
        token_patterns = {}
        if src_analysis.detected_tokens.get("date"):
            token_patterns["date"] = r'(\d{8}|\d{4}[-/]\d{2}[-/]\d{2})'
        if src_analysis.detected_tokens.get("animal_id"):
            token_patterns["animal_id"] = r'(?:animal|mouse|id)[_\-]?(\d{3,5})|[_\-](\d{3,4})[_\-]'
        if src_analysis.detected_tokens.get("chamber"):
            token_patterns["chamber"] = r'(?:ch|chamber)[_\-]?([A-D]|\d{1,2})'

        strategy_config = {
            "column_mappings": column_mappings,
            "token_patterns": token_patterns,
            "thresholds": {
                "promote": 0.8,
                "candidate": 0.4,
                "reject": 0.2,
            },
            "folder_rules": {
                "src_pattern": src_analysis.folder_path,
                "dst_pattern": dst_analysis.folder_path,
            },
        }

        return LinkerStrategy(
            strategy_id=0,
            name=f"Auto: {Path(src_analysis.folder_path).name} → {Path(dst_analysis.folder_path).name}",
            version=1,
            description="Automatically generated strategy based on folder analysis",
            strategy_config=strategy_config,
            src_folder_pattern=src_analysis.folder_path,
            dst_folder_pattern=dst_analysis.folder_path,
            relation_type=relation_type,
            is_active=False,
        )

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            response = json_match.group(1)

        # Try to parse as JSON
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Try to find JSON object
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        return None
