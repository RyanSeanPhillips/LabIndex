"""
CandidateReview ViewModel for the Link Review tab.

Manages:
- Candidate edge filtering and display
- Selection and batch actions
- Evidence preview
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from PyQt6.QtCore import pyqtSignal

from .base import BaseViewModel
from labindex_core.services.linker import LinkerService
from labindex_core.services.crawler import CrawlerService
from labindex_core.ports.db_port import DBPort
from labindex_core.domain.models import LinkerStrategy


@dataclass
class CandidateRow:
    """Pre-formatted candidate row for display."""
    candidate_id: int
    src_file_id: int
    dst_file_id: int
    src_name: str
    src_path: str
    dst_name: str
    dst_path: str
    confidence: float
    status: str
    evidence: Dict[str, Any]
    features: Dict[str, Any]
    strategy_id: Optional[int]
    strategy_name: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CandidateRow":
        """Create from get_candidates_with_files dict."""
        return cls(
            candidate_id=d["candidate_id"],
            src_file_id=d["src_file_id"],
            dst_file_id=d["dst_file_id"],
            src_name=d["src_name"],
            src_path=d["src_path"],
            dst_name=d["dst_name"],
            dst_path=d["dst_path"],
            confidence=d["confidence"],
            status=d["status"],
            evidence=d.get("evidence", {}),
            features=d.get("features", {}),
            strategy_id=d.get("strategy_id"),
            strategy_name=d.get("strategy_name", "Default"),
        )

    def format_evidence_summary(self) -> str:
        """Format evidence for table display."""
        evidence = self.evidence
        text = evidence.get("type", "unknown")
        if "matched_text" in evidence:
            text += f": {evidence['matched_text'][:30]}"
        elif "matched_suffix" in evidence:
            text += f": {evidence['matched_suffix']}"
        return text


@dataclass
class CandidateStats:
    """Statistics about candidates."""
    pending: int = 0
    accepted: int = 0
    rejected: int = 0
    needs_audit: int = 0
    total: int = 0


class CandidateReviewVM(BaseViewModel):
    """
    ViewModel for Link Review tab.

    Uses get_candidates_with_files() to avoid N+1 queries when populating
    the candidates table.

    Signals:
        candidates_changed: Emitted when candidate list changes
        selection_changed: Emitted when selected candidate changes
        stats_changed: Emitted when stats change
        evidence_changed: Emitted when evidence preview changes

    State:
        available_strategies: List of linking strategies
        selected_strategy_id: Currently selected strategy filter
        selected_status: Currently selected status filter
        candidates: List of CandidateRow (pre-joined data)
        selected_candidate: Currently selected candidate
        stats: Current candidate statistics
        evidence_html: HTML content for evidence preview
    """

    # Signals
    candidates_changed = pyqtSignal()
    selection_changed = pyqtSignal()
    stats_changed = pyqtSignal()
    evidence_changed = pyqtSignal()
    strategies_changed = pyqtSignal()

    def __init__(
        self,
        linker: LinkerService,
        crawler: CrawlerService,
        db: DBPort,
    ):
        """
        Initialize the ViewModel.

        Args:
            linker: Service for candidate operations
            crawler: Service for getting roots
            db: Database adapter
        """
        super().__init__()

        self._linker = linker
        self._crawler = crawler
        self._db = db

        # State
        self._strategies: List[LinkerStrategy] = []
        self._selected_strategy_id: Optional[int] = None
        self._selected_status: str = "pending"
        self._candidates: List[CandidateRow] = []
        self._selected_candidate: Optional[CandidateRow] = None
        self._stats = CandidateStats()
        self._evidence_html: str = ""

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def available_strategies(self) -> List[LinkerStrategy]:
        """Get list of available linking strategies."""
        return self._strategies.copy()

    @property
    def selected_strategy_id(self) -> Optional[int]:
        """Get selected strategy ID for filtering (None = all)."""
        return self._selected_strategy_id

    @property
    def selected_status(self) -> str:
        """Get selected status filter."""
        return self._selected_status

    @property
    def candidates(self) -> List[CandidateRow]:
        """Get current candidate list."""
        return self._candidates.copy()

    @property
    def candidate_count(self) -> int:
        """Get number of candidates."""
        return len(self._candidates)

    @property
    def selected_candidate(self) -> Optional[CandidateRow]:
        """Get the selected candidate."""
        return self._selected_candidate

    @property
    def stats(self) -> CandidateStats:
        """Get current statistics."""
        return self._stats

    @property
    def evidence_html(self) -> str:
        """Get HTML for evidence preview."""
        return self._evidence_html

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def refresh_strategies(self) -> None:
        """Refresh the list of available strategies."""
        self._strategies = self._db.list_linker_strategies()
        self.strategies_changed.emit()

    def set_filter(
        self,
        status: Optional[str] = None,
        strategy_id: Optional[int] = None,
    ) -> None:
        """
        Set filters and refresh candidates.

        Args:
            status: Status filter ("pending", "needs_audit", "accepted", "rejected", None=all)
            strategy_id: Strategy filter (None = all)
        """
        if status is not None:
            self._selected_status = status
        self._selected_strategy_id = strategy_id
        self.refresh_candidates()

    def refresh_candidates(self) -> None:
        """Refresh the candidate list using batch query."""
        # Map status filter
        status = self._selected_status
        if status == "all":
            status = None

        # Use batch method to avoid N+1 queries
        rows = self._linker.get_candidates_with_files(
            status=status,
            strategy_id=self._selected_strategy_id,
            limit=200
        )

        self._candidates = [CandidateRow.from_dict(r) for r in rows]

        # Clear selection if no longer valid
        if self._selected_candidate:
            if not any(c.candidate_id == self._selected_candidate.candidate_id
                       for c in self._candidates):
                self._selected_candidate = None
                self._evidence_html = ""
                self.selection_changed.emit()
                self.evidence_changed.emit()

        # Refresh stats
        self._refresh_stats()

        self.candidates_changed.emit()

    def select_candidate(self, candidate_id: int) -> None:
        """
        Select a candidate for preview.

        Args:
            candidate_id: ID of candidate to select
        """
        for c in self._candidates:
            if c.candidate_id == candidate_id:
                self._selected_candidate = c
                self._build_evidence_html(c)
                self.selection_changed.emit()
                self.evidence_changed.emit()
                return

        # Not found - clear selection
        self._selected_candidate = None
        self._evidence_html = ""
        self.selection_changed.emit()
        self.evidence_changed.emit()

    def accept_selected(self) -> bool:
        """
        Accept the selected candidate.

        Returns:
            True if accepted
        """
        if not self._selected_candidate:
            return False

        edge = self._linker.promote_candidate(
            self._selected_candidate.candidate_id, "user"
        )

        if edge:
            self.refresh_candidates()
            return True
        return False

    def reject_selected(self) -> bool:
        """
        Reject the selected candidate.

        Returns:
            True if rejected
        """
        if not self._selected_candidate:
            return False

        result = self._linker.reject_candidate(
            self._selected_candidate.candidate_id, "user"
        )

        if result:
            self.refresh_candidates()
            return True
        return False

    def flag_for_audit(self) -> bool:
        """
        Flag the selected candidate for LLM audit.

        Returns:
            True if flagged
        """
        if not self._selected_candidate:
            return False

        result = self._linker.flag_for_audit(
            self._selected_candidate.candidate_id
        )

        if result:
            self.refresh_candidates()
            return True
        return False

    def accept_batch(self, candidate_ids: List[int]) -> int:
        """
        Accept multiple candidates.

        Args:
            candidate_ids: List of candidate IDs to accept

        Returns:
            Number accepted
        """
        accepted = 0
        for cid in candidate_ids:
            edge = self._linker.promote_candidate(cid, "user")
            if edge:
                accepted += 1

        if accepted > 0:
            self.refresh_candidates()
        return accepted

    def reject_batch(self, candidate_ids: List[int]) -> int:
        """
        Reject multiple candidates.

        Args:
            candidate_ids: List of candidate IDs to reject

        Returns:
            Number rejected
        """
        rejected = 0
        for cid in candidate_ids:
            if self._linker.reject_candidate(cid, "user"):
                rejected += 1

        if rejected > 0:
            self.refresh_candidates()
        return rejected

    def accept_high_confidence(self, min_confidence: float = 0.9) -> int:
        """
        Accept all high-confidence candidates.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            Number promoted
        """
        promoted = self._linker.bulk_promote_high_confidence(
            min_confidence=min_confidence,
            strategy_id=self._selected_strategy_id
        )

        if promoted > 0:
            self.refresh_candidates()
        return promoted

    def clear_rejected(self) -> int:
        """
        Clear all rejected candidates.

        Returns:
            Number cleared
        """
        candidates = self._db.list_candidate_edges(status="rejected", limit=10000)
        cleared = 0

        for c in candidates:
            if self._db.delete_candidate_edge(c.candidate_id):
                cleared += 1

        if cleared > 0:
            self.refresh_candidates()
        return cleared

    def get_full_path(self, path: str) -> Optional[str]:
        """Get full filesystem path for a relative path."""
        roots = self._crawler.get_roots()
        if roots:
            return str(Path(roots[0].root_path) / path)
        return None

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _refresh_stats(self) -> None:
        """Refresh candidate statistics."""
        stats = self._linker.get_candidate_stats()
        self._stats = CandidateStats(
            pending=stats.get("pending", 0),
            accepted=stats.get("accepted", 0),
            rejected=stats.get("rejected", 0),
            needs_audit=stats.get("needs_audit", 0),
            total=stats.get("total", 0),
        )
        self.stats_changed.emit()

    def _build_evidence_html(self, candidate: CandidateRow) -> None:
        """Build HTML for evidence preview."""
        evidence = candidate.evidence
        html = f"<h4>Evidence Type: {evidence.get('type', 'unknown')}</h4>"

        if "matched_text" in evidence:
            html += f"<p><b>Matched:</b> {evidence['matched_text']}</p>"
        if "matched_suffix" in evidence:
            html += f"<p><b>Suffix:</b> {evidence['matched_suffix']} ({evidence.get('mention_count', 0)} mentions)</p>"
        if "shared_animal_id" in evidence:
            html += f"<p><b>Shared Animal ID:</b> {evidence['shared_animal_id']}</p>"
        if "evidence_text" in evidence:
            html += f"<p><b>Excerpt:</b><br><code>{evidence['evidence_text'][:500]}</code></p>"
        if "path_similarity" in evidence:
            html += f"<p><b>Path Similarity:</b> {evidence['path_similarity']:.0%}</p>"

        # Context-aware features (from adaptive linking)
        if "reference" in evidence:
            html += f"<p><b>Reference Found:</b> <code>{evidence['reference']}</code></p>"
        if "reference_type" in evidence:
            html += f"<p><b>Reference Type:</b> {evidence['reference_type']}</p>"
        if "context_excerpt" in evidence:
            html += "<h4>Context Around Reference</h4>"
            html += f"<pre style='background:#f5f5f5;padding:10px;font-size:11px;white-space:pre-wrap;'>{evidence['context_excerpt'][:800]}</pre>"
        if "context_metadata" in evidence:
            meta = evidence["context_metadata"]
            if meta:
                html += "<h4>Extracted from Context</h4><ul>"
                if "animal_ids" in meta and meta["animal_ids"]:
                    html += f"<li><b>Animal IDs:</b> {', '.join(str(x) for x in meta['animal_ids'][:5])}</li>"
                if "dates" in meta and meta["dates"]:
                    html += f"<li><b>Dates:</b> {', '.join(str(x) for x in meta['dates'][:5])}</li>"
                if "row_header" in meta:
                    html += f"<li><b>Column Headers:</b> {meta['row_header'][:100]}</li>"
                html += "</ul>"

        # Feature highlights
        features = candidate.features
        if features:
            html += "<h4>Key Features</h4><ul>"
            if features.get("exact_basename_match"):
                html += "<li>Exact basename match</li>"
            if features.get("rapidfuzz_ratio", 0) > 70:
                html += f"<li>Name similarity: {features['rapidfuzz_ratio']:.0f}%</li>"
            if features.get("animal_id_agreement", 0) > 0:
                html += f"<li>Animal ID agreement: {features['animal_id_agreement']:.0%}</li>"
            if features.get("date_token_agreement", 0) > 0:
                html += f"<li>Date agreement: {features['date_token_agreement']:.0%}</li>"

            # Context-aware features
            if features.get("context_explicit_reference"):
                html += "<li><b>Explicit reference in context</b></li>"
            if features.get("context_confidence", 0) > 0:
                html += f"<li>Context confidence: {features['context_confidence']:.0%}</li>"
            if features.get("context_mouse_id_match", 0) > 0:
                html += f"<li>Context mouse ID match: {features['context_mouse_id_match']:.0%}</li>"
            if features.get("context_date_match", 0) > 0:
                html += f"<li>Context date match: {features['context_date_match']:.0%}</li>"
            html += "</ul>"

        self._evidence_html = html
