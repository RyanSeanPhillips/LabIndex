"""
Adaptive Linking Service - Orchestrates the intelligent linking pipeline.

This service ties together:
1. LLM exploration to propose linking strategies
2. Context-aware file reading
3. Soft scoring with explainable features
4. Candidate routing (auto-accept, human review, LLM audit)
5. ML model training from accumulated labels
6. Strategy performance tracking

Key Concept: The linking process adapts over time as users provide
feedback and more labels accumulate for ML training.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from .context_reader import ContextReader
from .feature_extractor import FeatureExtractor, FeatureVector
from .linker import LinkerService
from .link_auditor import LinkAuditor
from .ml_trainer import MLTrainer
from .handlers import create_default_registry, HandlerRegistry

from ..domain.models import (
    FileRecord, CandidateEdge, LinkerStrategy, StrategyProposal,
    ScoringResult, Edge
)
from ..domain.enums import FileCategory, EdgeType, CandidateStatus, IndexStatus
from ..ports.db_port import DBPort
from ..ports.llm_port import LLMPort


@dataclass
class RoutingResult:
    """Result of routing candidates to different reviewers."""
    auto_accepted: List[int] = field(default_factory=list)
    needs_human_review: List[int] = field(default_factory=list)
    needs_audit: List[int] = field(default_factory=list)
    auto_rejected: List[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (len(self.auto_accepted) + len(self.needs_human_review) +
                len(self.needs_audit) + len(self.auto_rejected))


@dataclass
class LinkingProgress:
    """Progress of a linking operation."""
    files_processed: int = 0
    references_found: int = 0
    candidates_generated: int = 0
    auto_accepted: int = 0
    needs_review: int = 0
    elapsed_seconds: float = 0.0


class AdaptiveLinkingService:
    """
    Main orchestration service for adaptive linking.

    Workflow:
    1. User describes data organization (or LLM explores)
    2. System proposes linking strategies
    3. User selects/refines strategy
    4. System generates candidates with context
    5. Candidates are routed: auto-accept, human review, or LLM audit
    6. Labels accumulate and ML model is trained
    7. Future linking uses learned model
    """

    # LLM prompt for strategy exploration
    EXPLORATION_PROMPT = """You are analyzing a research data folder to understand how files are organized and should be linked.

## Folder Structure
{folder_structure}

## Sample Files (with content excerpts)
{sample_files}

## User Description (if provided)
{user_description}

## Task
Analyze this data and propose linking strategies. Consider:
1. What types of files are present? (data files, notes, spreadsheets, etc.)
2. How are they organized? (by animal, date, experiment type?)
3. What references might exist between files? (notes mentioning data files, etc.)
4. What metadata can be extracted from paths and content? (animal IDs, dates, etc.)

Return ONLY a valid JSON array of strategy proposals:
[
    {{
        "name": "Strategy Name",
        "description": "What this strategy links",
        "src_folder_pattern": "pattern for source files (glob)",
        "dst_folder_pattern": "pattern for destination files (glob)",
        "relation_type": "notes_for|analysis_of|same_session|etc",
        "feature_weights": {{
            "feature_name": weight_0_to_1
        }},
        "token_patterns": {{
            "animal_id": "regex pattern",
            "date": "regex pattern"
        }},
        "confidence": 0.0_to_1.0,
        "rationale": "Why this strategy makes sense"
    }}
]
"""

    def __init__(
        self,
        db: DBPort,
        llm: Optional[LLMPort] = None,
        llm_budget: int = 50,
        model_dir: Optional[Path] = None,
    ):
        """
        Initialize the adaptive linking service.

        Args:
            db: Database port
            llm: Optional LLM port for exploration and auditing
            llm_budget: Maximum LLM calls per session
            model_dir: Directory for ML models
        """
        self.db = db
        self.llm = llm
        self.llm_budget = llm_budget
        self._llm_calls_made = 0

        # Initialize sub-services
        self.registry = create_default_registry()
        self.context_reader = ContextReader(db, llm, self.registry, llm_budget)
        self.feature_extractor = FeatureExtractor(db)
        self.linker = LinkerService(db)
        self.auditor = LinkAuditor(db, llm)
        self.trainer = MLTrainer(db, model_dir)

    @property
    def llm_calls_remaining(self) -> int:
        """Get remaining LLM call budget."""
        return max(0, self.llm_budget - self._llm_calls_made)

    def reset_llm_budget(self, new_budget: Optional[int] = None) -> None:
        """Reset LLM call counters across all services."""
        self._llm_calls_made = 0
        if new_budget is not None:
            self.llm_budget = new_budget
        self.context_reader.reset_llm_budget(new_budget)

    # =========================================================================
    # Strategy Exploration
    # =========================================================================

    def explore_data_patterns(
        self,
        root_id: int,
        user_description: str = "",
        sample_limit: int = 20,
    ) -> List[StrategyProposal]:
        """
        Use LLM to explore data and propose linking strategies.

        Args:
            root_id: Root ID to explore
            user_description: Optional user description of data organization
            sample_limit: Maximum files to sample

        Returns:
            List of StrategyProposal objects
        """
        if not self.llm:
            # Fall back to rule-based exploration
            return self._rule_based_exploration(root_id)

        # Build folder structure summary
        folder_structure = self._build_folder_structure(root_id)

        # Sample files with content
        sample_files = self._sample_files_with_content(root_id, sample_limit)

        # Build prompt
        prompt = self.EXPLORATION_PROMPT.format(
            folder_structure=folder_structure,
            sample_files=sample_files,
            user_description=user_description or "Not provided",
        )

        # Query LLM
        self._llm_calls_made += 1
        try:
            response = self.llm.simple_chat(prompt)
            proposals = self._parse_exploration_response(response)
            return proposals
        except Exception as e:
            print(f"[AdaptiveLinking] LLM exploration error: {e}")
            return self._rule_based_exploration(root_id)

    def _rule_based_exploration(self, root_id: int) -> List[StrategyProposal]:
        """Fallback rule-based exploration when LLM is unavailable."""
        proposals = []

        # Get file statistics
        files = self.db.list_files(root_id, limit=10000)

        # Count file types
        data_files = [f for f in files if f.category == FileCategory.DATA]
        doc_files = [f for f in files if f.category == FileCategory.DOCUMENTS]
        spreadsheet_files = [f for f in files if f.category == FileCategory.SPREADSHEETS]

        # Propose notes-to-data linking if both exist
        if doc_files and data_files:
            proposals.append(StrategyProposal(
                name="Notes to Data",
                description="Link documentation files to their associated data files",
                src_folder_pattern="**/*",
                dst_folder_pattern="**/*",
                relation_type="notes_for",
                feature_weights={
                    "evidence_strength": 0.35,
                    "same_folder": 0.10,
                    "animal_id_agreement": 0.15,
                    "date_token_agreement": 0.15,
                },
                token_patterns={
                    "animal_id": r"(?:animal|mouse|rat)[_\-\s]*(\d{3,5})",
                    "date": r"(\d{8}|\d{4}[-/]\d{2}[-/]\d{2})",
                },
                confidence=0.6,
                rationale="Found both document and data files in the index",
            ))

        # Propose spreadsheet-to-data linking
        if spreadsheet_files and data_files:
            proposals.append(StrategyProposal(
                name="Spreadsheet Logs to Data",
                description="Link spreadsheet logs/metadata to data files",
                src_folder_pattern="**/*.xlsx",
                dst_folder_pattern="**/*.abf",
                relation_type="notes_for",
                feature_weights={
                    "evidence_strength": 0.40,
                    "has_canonical_column_match": 0.20,
                    "date_token_agreement": 0.15,
                },
                token_patterns={
                    "animal_id": r"(?:animal|mouse|rat)[_\-\s]*(\d{3,5})",
                    "date": r"(\d{8})",
                },
                confidence=0.7,
                rationale="Found spreadsheets that may contain file references",
            ))

        return proposals

    def _build_folder_structure(self, root_id: int, max_depth: int = 4) -> str:
        """Build a summary of the folder structure."""
        files = self.db.list_files(root_id, limit=5000)

        # Build folder tree
        folders = set()
        for f in files:
            if f.is_dir:
                folders.add(f.path)
            else:
                folders.add(f.parent_path)

        # Limit depth
        trimmed = set()
        for folder in folders:
            parts = Path(folder).parts[:max_depth]
            trimmed.add("/".join(parts))

        # Format as tree
        sorted_folders = sorted(trimmed)
        return "\n".join(f"  {f}/" for f in sorted_folders[:50])

    def _sample_files_with_content(self, root_id: int, limit: int) -> str:
        """Sample files with content excerpts."""
        files = self.db.list_files(root_id, limit=1000)

        # Prioritize files with extracted content
        files_with_content = [
            f for f in files
            if not f.is_dir and f.status == IndexStatus.EXTRACT_OK
        ]

        # Sample diverse file types
        samples = []
        by_category: Dict[FileCategory, List[FileRecord]] = {}
        for f in files_with_content:
            if f.category not in by_category:
                by_category[f.category] = []
            by_category[f.category].append(f)

        # Take samples from each category
        per_category = max(2, limit // len(by_category)) if by_category else 0
        for category, category_files in by_category.items():
            samples.extend(category_files[:per_category])

        # Format samples
        result = []
        for f in samples[:limit]:
            content = self.db.get_content(f.file_id)
            excerpt = ""
            if content:
                if content.full_text:
                    excerpt = content.full_text[:500]
                elif content.content_excerpt:
                    excerpt = content.content_excerpt

            result.append(f"""
### {f.name}
- Path: {f.path}
- Type: {f.category.value}
- Content excerpt:
```
{excerpt}
```
""")

        return "\n".join(result)

    def _parse_exploration_response(self, response: str) -> List[StrategyProposal]:
        """Parse LLM response into strategy proposals."""
        # Try to find JSON array
        json_match = re.search(r'\[[\s\S]*\]', response)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
            proposals = []
            for item in data:
                proposals.append(StrategyProposal(
                    name=item.get("name", "Unnamed Strategy"),
                    description=item.get("description", ""),
                    src_folder_pattern=item.get("src_folder_pattern", "**/*"),
                    dst_folder_pattern=item.get("dst_folder_pattern", "**/*"),
                    relation_type=item.get("relation_type", "notes_for"),
                    feature_weights=item.get("feature_weights", {}),
                    token_patterns=item.get("token_patterns", {}),
                    confidence=float(item.get("confidence", 0.5)),
                    rationale=item.get("rationale", ""),
                ))
            return proposals
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[AdaptiveLinking] Failed to parse response: {e}")
            return []

    # =========================================================================
    # Candidate Generation with Context
    # =========================================================================

    def generate_candidates_with_context(
        self,
        root_id: int,
        strategy: LinkerStrategy,
        context_lines: int = 20,
    ) -> Tuple[List[CandidateEdge], LinkingProgress]:
        """
        Generate candidates using context-aware reading.

        Args:
            root_id: Root ID to process
            strategy: Linking strategy to use
            context_lines: Lines of context around references

        Returns:
            Tuple of (candidates, progress)
        """
        import time
        start_time = time.time()

        progress = LinkingProgress()

        # Get files matching strategy patterns
        all_files = self.db.list_files(root_id, limit=100000)

        src_files = self._filter_by_pattern(all_files, strategy.src_folder_pattern)
        dst_files = self._filter_by_pattern(all_files, strategy.dst_folder_pattern)

        # Build indexes
        files_by_id = {f.file_id: f for f in all_files}
        files_by_name = {f.name.lower(): f for f in all_files if not f.is_dir}

        candidates = []

        # Process each source file
        for src_file in src_files:
            if src_file.is_dir:
                continue

            progress.files_processed += 1

            # Get context for this file
            file_ctx = self.context_reader.get_file_context(src_file, context_lines)
            progress.references_found += len(file_ctx.references)

            # Match references to destination files
            matches = self.context_reader.match_references_to_files(
                file_ctx.references,
                dst_files
            )

            for ref, dst_file, ref_confidence in matches:
                # Extract features
                evidence = {
                    "type": "context_reference",
                    "reference": ref.reference,
                    "reference_type": ref.reference_type,
                    "context_excerpt": ref.context_summary,
                    "context_metadata": ref.extracted_metadata,
                }

                features = self.feature_extractor.extract(
                    src_file, dst_file, evidence, strategy
                )

                # Enrich with context features
                context_data = {
                    "explicit_reference": ref.reference_type in ("filename", "cell_filename"),
                    "confidence": ref.confidence,
                    "lines_analyzed": len(ref.before_lines) + len(ref.after_lines),
                }
                if "animal_ids" in ref.extracted_metadata:
                    context_data["mouse_id_match"] = 1.0
                if "dates" in ref.extracted_metadata:
                    context_data["date_match"] = 1.0

                features = self.feature_extractor.extract_context_features(
                    features, context_data
                )

                # Compute score
                score_result = self.feature_extractor.compute_soft_score(features, strategy)
                confidence = score_result.total_score

                # Create candidate
                candidate = CandidateEdge(
                    candidate_id=0,
                    src_file_id=src_file.file_id,
                    dst_file_id=dst_file.file_id,
                    relation_type=strategy.relation_type,
                    confidence=confidence,
                    evidence=evidence,
                    features=features.to_dict(),
                    strategy_id=strategy.strategy_id if strategy.strategy_id else None,
                )

                # Store in database
                self.db.add_candidate_edge(candidate)
                candidates.append(candidate)
                progress.candidates_generated += 1

        progress.elapsed_seconds = time.time() - start_time
        return candidates, progress

    def _filter_by_pattern(
        self,
        files: List[FileRecord],
        pattern: str
    ) -> List[FileRecord]:
        """Filter files by glob pattern."""
        from fnmatch import fnmatch

        if not pattern or pattern == "**/*":
            return files

        return [f for f in files if fnmatch(f.path.lower(), pattern.lower())]

    # =========================================================================
    # Candidate Routing
    # =========================================================================

    def auto_review_candidates(
        self,
        candidates: List[CandidateEdge],
        auto_accept_threshold: float = 0.9,
        audit_threshold: float = 0.5,
        auto_reject_threshold: float = 0.2,
    ) -> RoutingResult:
        """
        Route candidates to appropriate reviewers.

        Args:
            candidates: Candidates to route
            auto_accept_threshold: Score above this auto-accepts
            audit_threshold: Score between this and accept triggers LLM audit
            auto_reject_threshold: Score below this auto-rejects

        Returns:
            RoutingResult with candidate IDs in each category
        """
        result = RoutingResult()

        for candidate in candidates:
            score = candidate.confidence

            if score >= auto_accept_threshold:
                # Auto-accept high confidence
                edge = self.linker.promote_candidate(
                    candidate.candidate_id, "auto:high_confidence"
                )
                if edge:
                    result.auto_accepted.append(candidate.candidate_id)

            elif score >= audit_threshold:
                # Medium confidence - either audit or human review
                should_audit, reason = self.auditor.should_audit(candidate)
                if should_audit and self.llm and self._llm_calls_made < self.llm_budget:
                    self.linker.flag_for_audit(candidate.candidate_id)
                    result.needs_audit.append(candidate.candidate_id)
                else:
                    result.needs_human_review.append(candidate.candidate_id)

            elif score >= auto_reject_threshold:
                # Low confidence - needs human review
                result.needs_human_review.append(candidate.candidate_id)

            else:
                # Very low confidence - auto-reject
                self.linker.reject_candidate(
                    candidate.candidate_id, "auto:low_confidence"
                )
                result.auto_rejected.append(candidate.candidate_id)

        return result

    def run_batch_audit(self, max_audits: int = 10) -> Dict[int, Any]:
        """
        Run LLM audit on flagged candidates.

        Args:
            max_audits: Maximum number of audits to run

        Returns:
            Dict mapping candidate_id to audit result
        """
        if not self.llm:
            return {}

        candidates = self.linker.get_candidates_for_review(
            status="needs_audit", limit=max_audits
        )

        return self.auditor.audit_batch(candidates, max_audits)

    # =========================================================================
    # ML Training Integration
    # =========================================================================

    def train_from_labels(
        self,
        model_type: str = "random_forest",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Train ML model from accumulated labels.

        Args:
            model_type: "random_forest" or "xgboost"
            **kwargs: Additional model parameters

        Returns:
            Training metrics
        """
        metrics = self.trainer.train(model_type=model_type, **kwargs)
        self.trainer.save_model()
        return metrics.to_dict()

    def use_ml_scoring(self) -> bool:
        """
        Load trained model and use it for future scoring.

        Returns:
            True if model was loaded successfully
        """
        try:
            self.trainer.load_model()
            return True
        except FileNotFoundError:
            return False

    def score_with_ml(self, candidate: CandidateEdge) -> ScoringResult:
        """
        Score a candidate using the ML model.

        Args:
            candidate: Candidate to score

        Returns:
            ScoringResult from ML model
        """
        if not self.trainer.is_trained:
            # Fall back to rule-based
            features = FeatureVector.from_dict(candidate.features)
            return self.feature_extractor.compute_soft_score(features)

        return self.trainer.score_with_model(candidate)

    # =========================================================================
    # Strategy Performance Tracking
    # =========================================================================

    def get_strategy_performance(self, strategy_id: int) -> Dict[str, Any]:
        """
        Get performance metrics for a strategy.

        Args:
            strategy_id: Strategy to evaluate

        Returns:
            Performance metrics dict
        """
        # Get all candidates from this strategy
        candidates = self.db.list_candidate_edges(
            strategy_id=strategy_id, limit=10000
        )

        total = len(candidates)
        accepted = sum(1 for c in candidates if c.status == CandidateStatus.ACCEPTED)
        rejected = sum(1 for c in candidates if c.status == CandidateStatus.REJECTED)
        pending = sum(1 for c in candidates if c.status == CandidateStatus.PENDING)

        # Calculate precision (of those reviewed, what % were accepted)
        reviewed = accepted + rejected
        precision = accepted / reviewed if reviewed > 0 else 0.0

        # Average confidence of accepted vs rejected
        avg_conf_accepted = 0.0
        avg_conf_rejected = 0.0
        if accepted > 0:
            avg_conf_accepted = sum(
                c.confidence for c in candidates if c.status == CandidateStatus.ACCEPTED
            ) / accepted
        if rejected > 0:
            avg_conf_rejected = sum(
                c.confidence for c in candidates if c.status == CandidateStatus.REJECTED
            ) / rejected

        return {
            "strategy_id": strategy_id,
            "total_candidates": total,
            "accepted": accepted,
            "rejected": rejected,
            "pending": pending,
            "precision": precision,
            "avg_confidence_accepted": avg_conf_accepted,
            "avg_confidence_rejected": avg_conf_rejected,
        }

    # =========================================================================
    # High-Level Workflows
    # =========================================================================

    def run_full_linking_pipeline(
        self,
        root_id: int,
        strategy: LinkerStrategy,
        auto_accept_threshold: float = 0.9,
        audit_threshold: float = 0.5,
        context_lines: int = 20,
    ) -> Dict[str, Any]:
        """
        Run the complete linking pipeline.

        1. Generate candidates with context
        2. Route candidates (auto-accept, audit, human review)
        3. Run LLM audits if available
        4. Return summary

        Args:
            root_id: Root to process
            strategy: Linking strategy
            auto_accept_threshold: Auto-accept threshold
            audit_threshold: LLM audit threshold
            context_lines: Context window size

        Returns:
            Pipeline summary dict
        """
        # Generate candidates
        candidates, progress = self.generate_candidates_with_context(
            root_id, strategy, context_lines
        )

        # Route candidates
        routing = self.auto_review_candidates(
            candidates, auto_accept_threshold, audit_threshold
        )

        # Run audits
        audit_results = {}
        if routing.needs_audit and self.llm:
            audit_results = self.run_batch_audit(len(routing.needs_audit))

        return {
            "progress": {
                "files_processed": progress.files_processed,
                "references_found": progress.references_found,
                "candidates_generated": progress.candidates_generated,
                "elapsed_seconds": progress.elapsed_seconds,
            },
            "routing": {
                "auto_accepted": len(routing.auto_accepted),
                "needs_human_review": len(routing.needs_human_review),
                "needs_audit": len(routing.needs_audit),
                "auto_rejected": len(routing.auto_rejected),
            },
            "audits_completed": len(audit_results),
            "llm_calls_used": self._llm_calls_made,
            "llm_calls_remaining": self.llm_calls_remaining,
        }
