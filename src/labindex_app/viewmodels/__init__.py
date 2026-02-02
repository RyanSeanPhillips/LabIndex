"""
ViewModels for LabIndex app.

MVVM architecture separating business logic from UI:
- ViewModels handle state and business logic
- Views (Qt widgets) handle rendering and user input
- Services handle data access and operations
"""

from .base import BaseViewModel
from .index_status_vm import IndexStatusVM, IndexStats
from .search_vm import SearchVM, SearchResultRow
from .graph_vm import GraphVM, GraphSettings
from .agent_vm import AgentVM, ChatMessage, LLMProvider
from .inspector_vm import InspectorVM, RelatedFile
from .candidate_review_vm import CandidateReviewVM, CandidateRow, CandidateStats
from .strategy_explorer_vm import StrategyExplorerVM, ProposalRow, LinkingProgressRow
from .coordinator import AppCoordinator

__all__ = [
    # Base
    "BaseViewModel",

    # ViewModels
    "IndexStatusVM",
    "SearchVM",
    "GraphVM",
    "AgentVM",
    "InspectorVM",
    "CandidateReviewVM",
    "StrategyExplorerVM",
    "AppCoordinator",

    # Data classes
    "IndexStats",
    "SearchResultRow",
    "GraphSettings",
    "ChatMessage",
    "LLMProvider",
    "RelatedFile",
    "CandidateRow",
    "CandidateStats",
    "ProposalRow",
    "LinkingProgressRow",
]
