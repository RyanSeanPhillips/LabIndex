"""
Domain models (DTOs) for LabIndex.

These are pure data classes with no database or filesystem dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from .enums import FileCategory, IndexStatus, EdgeType, JobStatus, CandidateStatus


@dataclass
class IndexRoot:
    """A root folder that has been added for indexing."""
    root_id: int
    root_path: str
    label: str
    scan_config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_scan_at: Optional[datetime] = None

    @property
    def path(self) -> Path:
        return Path(self.root_path)


@dataclass
class FileRecord:
    """A file or directory in the index."""
    file_id: int
    root_id: int
    path: str                    # Full path relative to root
    parent_path: str             # Parent directory path
    name: str                    # Filename with extension
    ext: str                     # Extension (lowercase, no dot)
    is_dir: bool
    size_bytes: int
    mtime: datetime              # Last modified time
    ctime: datetime              # Creation time
    category: FileCategory
    status: IndexStatus = IndexStatus.PENDING
    error_msg: Optional[str] = None
    last_indexed_at: Optional[datetime] = None

    @property
    def full_path(self) -> Path:
        return Path(self.path)

    @property
    def stem(self) -> str:
        """Filename without extension."""
        return Path(self.name).stem


@dataclass
class ContentRecord:
    """Extracted content for a file (Tier 1/2/3)."""
    file_id: int
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)  # {type: [values]}
    content_excerpt: Optional[str] = None  # First N chars/lines
    full_text: Optional[str] = None  # Complete extracted text (for FTS)
    extraction_version: str = "1.0"
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class Edge:
    """A relationship between two files."""
    edge_id: int
    src_file_id: int
    dst_file_id: int
    relation_type: EdgeType
    confidence: float = 1.0      # 0.0 to 1.0
    evidence: Optional[str] = None  # Snippet/reason for the link
    evidence_file_id: Optional[int] = None  # Where evidence was found
    created_by: str = "rule"     # "rule", "llm", "user"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CrawlJob:
    """A job to crawl a directory."""
    job_id: int
    root_id: int
    dir_path: str
    status: JobStatus = JobStatus.PENDING
    priority: int = 0            # Higher = more important
    attempts: int = 0
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_msg: Optional[str] = None


@dataclass
class SearchResult:
    """A search result with ranking info."""
    file_id: int
    file_record: FileRecord
    score: float                 # Relevance score
    match_type: str              # "fts", "filename", "fuzzy", "edge"
    snippet: Optional[str] = None  # Matching text snippet
    highlight_positions: List[tuple] = field(default_factory=list)  # (start, end) pairs

    @property
    def path(self) -> str:
        return self.file_record.path

    @property
    def name(self) -> str:
        return self.file_record.name


@dataclass
class CandidateEdge:
    """A proposed relationship between two files awaiting review."""
    candidate_id: int
    src_file_id: int
    dst_file_id: int
    relation_type: EdgeType
    confidence: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)  # Structured evidence
    features: Dict[str, Any] = field(default_factory=dict)  # ML-ready features
    feature_schema_version: int = 1
    status: CandidateStatus = CandidateStatus.PENDING
    strategy_id: Optional[int] = None  # LinkerStrategy that generated this
    created_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None  # "user", "auditor:model_name"


@dataclass
class Artifact:
    """A sub-document anchor for evidence navigation."""
    artifact_id: int
    file_id: int
    artifact_type: str  # text_span, table_cell, table_row, ppt_slide, ipynb_cell
    locator: Dict[str, Any] = field(default_factory=dict)  # Type-specific location data
    excerpt: Optional[str] = None  # Small text snippet from this location
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Audit:
    """LLM auditor verdict for a candidate edge."""
    audit_id: int
    candidate_id: int
    auditor_model: Optional[str] = None  # e.g., "claude-3-haiku"
    auditor_prompt_version: Optional[str] = None  # For reproducibility
    verdict: str = "needs_more_info"  # accept, reject, needs_more_info
    confidence: Optional[float] = None  # 0.0-1.0
    rationale_excerpt: Optional[str] = None  # Brief explanation
    recommended_next_steps: List[str] = field(default_factory=list)  # Tool suggestions
    audited_at: datetime = field(default_factory=datetime.now)


@dataclass
class LinkerStrategy:
    """A versioned linking strategy configuration."""
    strategy_id: int
    name: str                    # e.g., "Surgery Notes v2"
    version: int = 1
    description: Optional[str] = None
    strategy_config: Dict[str, Any] = field(default_factory=dict)  # Full strategy JSON
    src_folder_pattern: Optional[str] = None  # Source folder glob/regex
    dst_folder_pattern: Optional[str] = None  # Target folder glob/regex
    relation_type: EdgeType = EdgeType.NOTES_FOR
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = False

    @property
    def column_mappings(self) -> Dict[str, str]:
        """Get column header synonyms mapping."""
        return self.strategy_config.get("column_mappings", {})

    @property
    def token_patterns(self) -> Dict[str, str]:
        """Get token extraction patterns (animal_id, date, chamber, etc.)."""
        return self.strategy_config.get("token_patterns", {})

    @property
    def thresholds(self) -> Dict[str, float]:
        """Get score thresholds (promote, candidate, reject)."""
        return self.strategy_config.get("thresholds", {
            "promote": 0.8,
            "candidate": 0.4,
            "reject": 0.2
        })

    @property
    def feature_weights(self) -> Dict[str, float]:
        """Get feature weights for soft scoring."""
        return self.strategy_config.get("feature_weights", {})


@dataclass
class SoftScore:
    """
    Probabilistic score contribution from a single feature.

    Used to build explainable scoring where each feature contributes
    a weighted amount to the final confidence score.
    """
    feature_name: str               # Name of the feature
    raw_value: float                # The measured/extracted value
    normalized_value: float         # Value normalized to 0-1 range
    weight: float                   # Weight applied to this feature
    contribution: float             # weight * normalized_value
    explanation: str                # Human-readable explanation


@dataclass
class ScoringResult:
    """
    Complete scoring result with breakdown.

    Provides full explainability for how a candidate's score was computed.
    """
    total_score: float                          # Final score (0-1)
    score_breakdown: List[SoftScore] = field(default_factory=list)  # Individual contributions
    confidence_level: str = "medium"            # low/medium/high
    flags: List[str] = field(default_factory=list)  # Warnings or issues

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_score": self.total_score,
            "confidence_level": self.confidence_level,
            "flags": self.flags,
            "breakdown": [
                {
                    "feature": s.feature_name,
                    "raw": s.raw_value,
                    "normalized": s.normalized_value,
                    "weight": s.weight,
                    "contribution": s.contribution,
                    "explanation": s.explanation,
                }
                for s in self.score_breakdown
            ],
        }


@dataclass
class StrategyProposal:
    """
    A proposed linking strategy from LLM exploration.

    Generated when the LLM analyzes data patterns and suggests
    how files should be linked.
    """
    name: str
    description: str
    src_folder_pattern: str
    dst_folder_pattern: str
    relation_type: str
    feature_weights: Dict[str, float]
    token_patterns: Dict[str, str]
    confidence: float                   # LLM's confidence in this proposal
    rationale: str                      # Why this strategy was proposed
    example_matches: List[Dict[str, Any]] = field(default_factory=list)  # Sample matches

    def to_strategy(self, strategy_id: int = 0) -> LinkerStrategy:
        """Convert proposal to LinkerStrategy."""
        return LinkerStrategy(
            strategy_id=strategy_id,
            name=self.name,
            description=self.description,
            src_folder_pattern=self.src_folder_pattern,
            dst_folder_pattern=self.dst_folder_pattern,
            relation_type=EdgeType(self.relation_type),
            strategy_config={
                "feature_weights": self.feature_weights,
                "token_patterns": self.token_patterns,
            },
        )
