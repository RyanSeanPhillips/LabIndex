"""
Strategy Explorer ViewModel.

Manages the UI state for:
1. LLM-assisted strategy exploration
2. Strategy proposal management (select, apply, refine)
3. Linking pipeline execution
4. Training progress and model management
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot

from .base import BaseViewModel
from labindex_core.services.adaptive_linking import AdaptiveLinkingService
from labindex_core.services.crawler import CrawlerService
from labindex_core.domain.models import LinkerStrategy, StrategyProposal


@dataclass
class ProposalRow:
    """UI-ready proposal row."""
    index: int
    name: str
    description: str
    src_pattern: str
    dst_pattern: str
    relation_type: str
    confidence: float
    rationale: str
    is_selected: bool = False

    @classmethod
    def from_proposal(cls, index: int, proposal: StrategyProposal, selected: bool = False) -> "ProposalRow":
        return cls(
            index=index,
            name=proposal.name,
            description=proposal.description,
            src_pattern=proposal.src_folder_pattern,
            dst_pattern=proposal.dst_folder_pattern,
            relation_type=proposal.relation_type,
            confidence=proposal.confidence,
            rationale=proposal.rationale,
            is_selected=selected,
        )


@dataclass
class LinkingProgressRow:
    """Progress data for UI display."""
    files_processed: int = 0
    references_found: int = 0
    candidates_generated: int = 0
    auto_accepted: int = 0
    needs_review: int = 0
    elapsed_seconds: float = 0.0


class ExplorationWorker(QThread):
    """Worker thread for LLM exploration."""
    finished = pyqtSignal(list)  # List[StrategyProposal]
    error = pyqtSignal(str)

    def __init__(
        self,
        service: AdaptiveLinkingService,
        root_id: int,
        user_description: str,
    ):
        super().__init__()
        self.service = service
        self.root_id = root_id
        self.user_description = user_description

    def run(self):
        try:
            proposals = self.service.explore_data_patterns(
                self.root_id,
                self.user_description,
            )
            self.finished.emit(proposals)
        except Exception as e:
            self.error.emit(str(e))


class LinkingWorker(QThread):
    """Worker thread for linking pipeline."""
    progress = pyqtSignal(dict)  # Progress updates
    finished = pyqtSignal(dict)  # Final results
    error = pyqtSignal(str)

    def __init__(
        self,
        service: AdaptiveLinkingService,
        root_id: int,
        strategy: LinkerStrategy,
        auto_accept_threshold: float,
        audit_threshold: float,
    ):
        super().__init__()
        self.service = service
        self.root_id = root_id
        self.strategy = strategy
        self.auto_accept_threshold = auto_accept_threshold
        self.audit_threshold = audit_threshold

    def run(self):
        try:
            results = self.service.run_full_linking_pipeline(
                self.root_id,
                self.strategy,
                self.auto_accept_threshold,
                self.audit_threshold,
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class StrategyExplorerVM(BaseViewModel):
    """
    ViewModel for Strategy Explorer UI.

    Manages:
    - User description input
    - LLM exploration
    - Proposal list display
    - Strategy selection and application
    - Linking pipeline execution
    - ML training

    Signals:
        proposals_changed: Emitted when proposal list changes
        selection_changed: Emitted when selected proposal changes
        exploration_started: Emitted when LLM exploration starts
        exploration_finished: Emitted with (success, message)
        linking_started: Emitted when linking pipeline starts
        linking_progress: Emitted with progress updates
        linking_finished: Emitted with (success, results)
        training_finished: Emitted with (success, metrics)

    State:
        user_description: User's description of data organization
        proposals: List of ProposalRow
        selected_index: Index of selected proposal
        is_exploring: Whether exploration is in progress
        is_linking: Whether linking is in progress
        linking_progress: Current linking progress
        llm_calls_remaining: Remaining LLM budget
    """

    # Signals
    proposals_changed = pyqtSignal()
    selection_changed = pyqtSignal()
    exploration_started = pyqtSignal()
    exploration_finished = pyqtSignal(bool, str)
    linking_started = pyqtSignal()
    linking_progress = pyqtSignal(dict)
    linking_finished = pyqtSignal(bool, dict)
    training_finished = pyqtSignal(bool, dict)

    def __init__(
        self,
        adaptive_service: AdaptiveLinkingService,
        crawler: CrawlerService,
    ):
        """
        Initialize the ViewModel.

        Args:
            adaptive_service: The adaptive linking service
            crawler: Crawler service for getting roots
        """
        super().__init__()

        self._service = adaptive_service
        self._crawler = crawler

        # State
        self._user_description: str = ""
        self._proposals: List[StrategyProposal] = []
        self._proposal_rows: List[ProposalRow] = []
        self._selected_index: int = -1
        self._is_exploring: bool = False
        self._is_linking: bool = False
        self._progress = LinkingProgressRow()
        self._last_results: Dict[str, Any] = {}

        # Workers
        self._exploration_worker: Optional[ExplorationWorker] = None
        self._linking_worker: Optional[LinkingWorker] = None

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def user_description(self) -> str:
        """Get user description."""
        return self._user_description

    @property
    def proposals(self) -> List[ProposalRow]:
        """Get proposal rows for display."""
        return self._proposal_rows.copy()

    @property
    def proposal_count(self) -> int:
        """Get number of proposals."""
        return len(self._proposals)

    @property
    def selected_index(self) -> int:
        """Get selected proposal index (-1 if none)."""
        return self._selected_index

    @property
    def selected_proposal(self) -> Optional[StrategyProposal]:
        """Get selected proposal or None."""
        if 0 <= self._selected_index < len(self._proposals):
            return self._proposals[self._selected_index]
        return None

    @property
    def is_exploring(self) -> bool:
        """Whether LLM exploration is in progress."""
        return self._is_exploring

    @property
    def is_linking(self) -> bool:
        """Whether linking pipeline is running."""
        return self._is_linking

    @property
    def progress(self) -> LinkingProgressRow:
        """Get current linking progress."""
        return self._progress

    @property
    def last_results(self) -> Dict[str, Any]:
        """Get results from last linking run."""
        return self._last_results.copy()

    @property
    def llm_calls_remaining(self) -> int:
        """Get remaining LLM call budget."""
        return self._service.llm_calls_remaining

    @property
    def has_ml_model(self) -> bool:
        """Check if ML model is loaded."""
        return self._service.trainer.is_trained

    @property
    def training_stats(self) -> Dict[str, Any]:
        """Get training data statistics."""
        return self._service.trainer.get_training_stats()

    # =========================================================================
    # Commands
    # =========================================================================

    def set_user_description(self, description: str) -> None:
        """Set user description."""
        self._user_description = description

    def explore(self) -> None:
        """
        Start LLM exploration to discover strategies.

        Emits exploration_started, then exploration_finished when done.
        """
        if self._is_exploring:
            return

        roots = self._crawler.get_roots()
        if not roots:
            self.exploration_finished.emit(False, "No root indexed")
            return

        root_id = roots[0].root_id

        self._is_exploring = True
        self._proposals = []
        self._proposal_rows = []
        self._selected_index = -1

        self.exploration_started.emit()
        self.proposals_changed.emit()

        # Start worker thread
        self._exploration_worker = ExplorationWorker(
            self._service,
            root_id,
            self._user_description,
        )
        self._exploration_worker.finished.connect(self._on_exploration_finished)
        self._exploration_worker.error.connect(self._on_exploration_error)
        self._exploration_worker.start()

    def select_proposal(self, index: int) -> None:
        """
        Select a proposal by index.

        Args:
            index: Proposal index to select
        """
        if 0 <= index < len(self._proposals):
            self._selected_index = index
            self._update_proposal_rows()
            self.selection_changed.emit()

    def apply_proposal(self) -> Optional[LinkerStrategy]:
        """
        Apply the selected proposal as a LinkerStrategy.

        Returns:
            LinkerStrategy or None if no proposal selected
        """
        proposal = self.selected_proposal
        if not proposal:
            return None

        # Convert to strategy and save to database
        strategy = proposal.to_strategy()
        # Note: DB would assign strategy_id
        return strategy

    def refine_proposal(self, feedback: str) -> None:
        """
        Refine the selected proposal with user feedback.

        This would re-run exploration with additional context.

        Args:
            feedback: User feedback/refinement
        """
        if not self.selected_proposal:
            return

        # Append feedback to description
        refined_description = self._user_description
        if refined_description:
            refined_description += f"\n\nRefinement: {feedback}"
        else:
            refined_description = feedback

        self._user_description = refined_description
        self.explore()

    def run_linking(
        self,
        auto_accept_threshold: float = 0.9,
        audit_threshold: float = 0.5,
    ) -> None:
        """
        Run the linking pipeline with the selected strategy.

        Args:
            auto_accept_threshold: Auto-accept confidence threshold
            audit_threshold: LLM audit threshold
        """
        if self._is_linking:
            return

        proposal = self.selected_proposal
        if not proposal:
            self.linking_finished.emit(False, {"error": "No proposal selected"})
            return

        roots = self._crawler.get_roots()
        if not roots:
            self.linking_finished.emit(False, {"error": "No root indexed"})
            return

        root_id = roots[0].root_id
        strategy = proposal.to_strategy()

        self._is_linking = True
        self._progress = LinkingProgressRow()

        self.linking_started.emit()

        # Start worker
        self._linking_worker = LinkingWorker(
            self._service,
            root_id,
            strategy,
            auto_accept_threshold,
            audit_threshold,
        )
        self._linking_worker.progress.connect(self._on_linking_progress)
        self._linking_worker.finished.connect(self._on_linking_finished)
        self._linking_worker.error.connect(self._on_linking_error)
        self._linking_worker.start()

    def train_model(self, model_type: str = "random_forest") -> None:
        """
        Train ML model from accumulated labels.

        Args:
            model_type: "random_forest" or "xgboost"
        """
        try:
            metrics = self._service.train_from_labels(model_type=model_type)
            self.training_finished.emit(True, metrics)
        except Exception as e:
            self.training_finished.emit(False, {"error": str(e)})

    def load_ml_model(self) -> bool:
        """Load previously trained ML model."""
        return self._service.use_ml_scoring()

    def reset_llm_budget(self, budget: int = 50) -> None:
        """Reset LLM call budget."""
        self._service.reset_llm_budget(budget)

    # =========================================================================
    # Slots (connected to worker signals)
    # =========================================================================

    @pyqtSlot(list)
    def _on_exploration_finished(self, proposals: List[StrategyProposal]) -> None:
        """Handle exploration completion."""
        self._is_exploring = False
        self._proposals = proposals
        self._update_proposal_rows()

        if proposals:
            self._selected_index = 0
            self._update_proposal_rows()

        self.proposals_changed.emit()
        self.selection_changed.emit()
        self.exploration_finished.emit(
            len(proposals) > 0,
            f"Found {len(proposals)} potential strategies"
        )

    @pyqtSlot(str)
    def _on_exploration_error(self, error: str) -> None:
        """Handle exploration error."""
        self._is_exploring = False
        self.exploration_finished.emit(False, f"Error: {error}")

    @pyqtSlot(dict)
    def _on_linking_progress(self, data: Dict[str, Any]) -> None:
        """Handle linking progress update."""
        self._progress = LinkingProgressRow(
            files_processed=data.get("files_processed", 0),
            references_found=data.get("references_found", 0),
            candidates_generated=data.get("candidates_generated", 0),
        )
        self.linking_progress.emit(data)

    @pyqtSlot(dict)
    def _on_linking_finished(self, results: Dict[str, Any]) -> None:
        """Handle linking completion."""
        self._is_linking = False
        self._last_results = results

        # Update progress from final results
        if "progress" in results:
            p = results["progress"]
            self._progress = LinkingProgressRow(
                files_processed=p.get("files_processed", 0),
                references_found=p.get("references_found", 0),
                candidates_generated=p.get("candidates_generated", 0),
                elapsed_seconds=p.get("elapsed_seconds", 0),
            )

        if "routing" in results:
            r = results["routing"]
            self._progress.auto_accepted = r.get("auto_accepted", 0)
            self._progress.needs_review = r.get("needs_human_review", 0)

        self.linking_finished.emit(True, results)

    @pyqtSlot(str)
    def _on_linking_error(self, error: str) -> None:
        """Handle linking error."""
        self._is_linking = False
        self.linking_finished.emit(False, {"error": error})

    # =========================================================================
    # Internal
    # =========================================================================

    def _update_proposal_rows(self) -> None:
        """Update proposal rows for display."""
        self._proposal_rows = [
            ProposalRow.from_proposal(i, p, i == self._selected_index)
            for i, p in enumerate(self._proposals)
        ]
