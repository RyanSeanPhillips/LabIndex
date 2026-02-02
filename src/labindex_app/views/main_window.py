"""
Main Window for LabIndex.

Thin view layer using MVVM pattern:
- ViewModels hold state and business logic
- This view handles UI layout and binding
"""

import os
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QSplitter, QStatusBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QProgressBar, QFileDialog, QMessageBox, QPlainTextEdit, QTextEdit,
    QFrame, QListWidget, QListWidgetItem, QAbstractItemView,
    QComboBox, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..viewmodels import (
    IndexStatusVM, SearchVM, GraphVM, AgentVM,
    InspectorVM, CandidateReviewVM, AppCoordinator,
)


class MainWindow(QMainWindow):
    """Main application window using MVVM pattern."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("LabIndex - Read-Only Lab Drive Indexer")
        self.resize(1400, 900)

        # Database path
        self.db_path = self._get_db_path()

        # Initialize adapters (lazy)
        self._db = None
        self._fs = None

        # Initialize services (lazy)
        self._crawler = None
        self._search = None
        self._extractor = None
        self._linker = None

        # Initialize ViewModels (after services)
        self._init_viewmodels()

        # Setup UI
        self._setup_ui()
        self._setup_status_bar()

        # Bind ViewModels to UI
        self._bind_viewmodels()

        # Initial data load
        self._coordinator.refresh_all()

    def _get_db_path(self) -> Path:
        """Get the database path in AppData."""
        app_data = Path(os.environ.get("APPDATA", ".")) / "LabIndex"
        app_data.mkdir(parents=True, exist_ok=True)
        return app_data / "labindex.db"

    # -------------------------------------------------------------------------
    # Lazy Service Properties
    # -------------------------------------------------------------------------

    @property
    def db(self):
        """Lazy load database."""
        if self._db is None:
            from labindex_core.adapters.sqlite_db import SqliteDB
            self._db = SqliteDB(self.db_path)
        return self._db

    @property
    def fs(self):
        """Lazy load filesystem."""
        if self._fs is None:
            from labindex_core.adapters.readonly_fs import ReadOnlyFS
            self._fs = ReadOnlyFS()
        return self._fs

    @property
    def crawler(self):
        """Lazy load crawler service."""
        if self._crawler is None:
            from labindex_core.services.crawler import CrawlerService
            self._crawler = CrawlerService(self.fs, self.db)
        return self._crawler

    @property
    def search(self):
        """Lazy load search service."""
        if self._search is None:
            from labindex_core.services.search import SearchService
            self._search = SearchService(self.db)
        return self._search

    @property
    def extractor(self):
        """Lazy load extractor service."""
        if self._extractor is None:
            from labindex_core.services.extractor import ExtractorService
            self._extractor = ExtractorService(self.fs, self.db)
        return self._extractor

    @property
    def linker(self):
        """Lazy load linker service."""
        if self._linker is None:
            from labindex_core.services.linker import LinkerService
            self._linker = LinkerService(self.db)
        return self._linker

    # -------------------------------------------------------------------------
    # ViewModel Initialization
    # -------------------------------------------------------------------------

    def _init_viewmodels(self):
        """Initialize all ViewModels."""
        # Create ViewModels
        self._index_vm = IndexStatusVM(
            self.crawler, self.extractor, self.linker, self.search
        )
        self._search_vm = SearchVM(self.search)
        self._graph_vm = GraphVM(self.crawler, self.search, self.db)
        self._agent_vm = AgentVM(self.db, self.fs)
        self._inspector_vm = InspectorVM(self.db)
        self._review_vm = CandidateReviewVM(self.linker, self.crawler, self.db)

        # Create coordinator for cross-VM wiring
        self._coordinator = AppCoordinator(
            self._index_vm,
            self._search_vm,
            self._graph_vm,
            self._agent_vm,
            self._inspector_vm,
            self._review_vm,
        )

    def _bind_viewmodels(self):
        """Bind ViewModel signals to UI updates."""
        # Index tab bindings
        self._index_vm.roots_changed.connect(self._update_roots_list)
        self._index_vm.stats_changed.connect(self._update_stats)
        self._index_vm.progress_changed.connect(self._update_progress)
        self._index_vm.operation_started.connect(self._on_operation_started)
        self._index_vm.operation_finished.connect(self._on_operation_finished)

        # Search tab bindings
        self._search_vm.results_changed.connect(self._update_results_table)
        self._search_vm.search_started.connect(lambda: self.statusBar().showMessage("Searching..."))
        self._search_vm.search_finished.connect(lambda: self.statusBar().showMessage("Ready"))

        # Graph bindings
        self._graph_vm.navigation_changed.connect(self._update_graph_navigation)

        # Agent bindings
        self._agent_vm.message_added.connect(self._on_chat_message)
        self._agent_vm.thinking_changed.connect(self._on_agent_thinking)
        self._agent_vm.status_changed.connect(self._on_agent_status)

        # Review tab bindings
        self._review_vm.candidates_changed.connect(self._update_candidates_table)
        self._review_vm.stats_changed.connect(self._update_review_stats)
        self._review_vm.evidence_changed.connect(self._update_evidence_preview)

        # Coordinator bindings
        self._coordinator.status_message.connect(self._show_status)

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        """Setup the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        # Tab 1: Chat (primary interface)
        self._setup_chat_tab()

        # Tab 2: Index & Build
        self._setup_index_tab()

        # Tab 3: Search & Explore
        self._setup_search_tab()

        # Tab 4: Link Review
        self._setup_review_tab()

    def _setup_chat_tab(self):
        """Setup the Chat tab (primary interface)."""
        from .chat_tab import ChatTab

        self.chat_tab = ChatTab(
            agent_vm=self._agent_vm,
            index_vm=self._index_vm,
        )

        # Connect signals
        self.chat_tab.folder_index_requested.connect(self._on_chat_folder_requested)

        self.tabs.addTab(self.chat_tab, "Chat")

    def _on_chat_folder_requested(self, folder_path: str):
        """Handle folder index request from chat."""
        try:
            root = self._index_vm.add_root(folder_path)
            self._index_vm.start_crawl()
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 5000)

    def _setup_index_tab(self):
        """Setup the Index & Build tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Index & Build")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #4fc3f7;")
        layout.addWidget(header)

        # Roots section
        roots_group = QGroupBox("Indexed Roots")
        roots_layout = QVBoxLayout(roots_group)

        self.roots_list = QListWidget()
        self.roots_list.setMaximumHeight(150)
        self.roots_list.currentItemChanged.connect(self._on_root_selected)
        roots_layout.addWidget(self.roots_list)

        root_buttons = QHBoxLayout()
        self.add_root_btn = QPushButton("Add Root Folder...")
        self.add_root_btn.setObjectName("primaryButton")
        self.add_root_btn.clicked.connect(self._on_add_root)
        root_buttons.addWidget(self.add_root_btn)

        self.remove_root_btn = QPushButton("Remove Selected")
        self.remove_root_btn.clicked.connect(self._on_remove_root)
        root_buttons.addWidget(self.remove_root_btn)
        root_buttons.addStretch()
        roots_layout.addLayout(root_buttons)
        layout.addWidget(roots_group)

        # Crawl section
        crawl_group = QGroupBox("Crawl Status")
        crawl_layout = QVBoxLayout(crawl_group)

        self.crawl_progress = QProgressBar()
        self.crawl_progress.setTextVisible(True)
        self.crawl_progress.setValue(0)
        crawl_layout.addWidget(self.crawl_progress)

        self.crawl_status = QLabel("Ready to scan")
        self.crawl_status.setStyleSheet("color: #888;")
        crawl_layout.addWidget(self.crawl_status)

        crawl_buttons = QHBoxLayout()
        self.start_crawl_btn = QPushButton("Start Crawl")
        self.start_crawl_btn.setObjectName("successButton")
        self.start_crawl_btn.clicked.connect(self._on_start_crawl)
        crawl_buttons.addWidget(self.start_crawl_btn)

        self.stop_crawl_btn = QPushButton("Stop")
        self.stop_crawl_btn.setEnabled(False)
        self.stop_crawl_btn.clicked.connect(self._on_stop_crawl)
        crawl_buttons.addWidget(self.stop_crawl_btn)

        self.extract_btn = QPushButton("Extract Content")
        self.extract_btn.clicked.connect(self._on_start_extraction)
        crawl_buttons.addWidget(self.extract_btn)

        self.link_btn = QPushButton("Find Links")
        self.link_btn.clicked.connect(self._on_find_links)
        crawl_buttons.addWidget(self.link_btn)

        self.clear_links_btn = QPushButton("Clear Links")
        self.clear_links_btn.clicked.connect(self._on_clear_links)
        crawl_buttons.addWidget(self.clear_links_btn)

        crawl_buttons.addStretch()
        crawl_layout.addLayout(crawl_buttons)
        layout.addWidget(crawl_group)

        # Stats section
        stats_group = QGroupBox("Index Statistics")
        stats_layout = QHBoxLayout(stats_group)

        self.stats_files = QLabel("Files: 0")
        self.stats_files.setFont(QFont("Segoe UI", 12))
        stats_layout.addWidget(self.stats_files)

        self.stats_roots = QLabel("Roots: 0")
        self.stats_roots.setFont(QFont("Segoe UI", 12))
        stats_layout.addWidget(self.stats_roots)

        self.stats_indexed = QLabel("Indexed: 0")
        self.stats_indexed.setFont(QFont("Segoe UI", 12))
        self.stats_indexed.setStyleSheet("color: #4fc3f7;")
        stats_layout.addWidget(self.stats_indexed)

        self.stats_links = QLabel("Links: 0")
        self.stats_links.setFont(QFont("Segoe UI", 12))
        self.stats_links.setStyleSheet("color: #81c784;")
        stats_layout.addWidget(self.stats_links)
        stats_layout.addStretch()
        layout.addWidget(stats_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Index & Build")

    def _setup_search_tab(self):
        """Setup the Search & Explore tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search bar
        search_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBox")
        self.search_input.setPlaceholderText("Search files by name or content...")
        self.search_input.returnPressed.connect(self._on_search)
        search_bar.addWidget(self.search_input, stretch=1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self._on_search)
        search_bar.addWidget(self.search_btn)
        layout.addLayout(search_bar)

        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Graph + Results
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Graph frame with controls
        graph_frame = QFrame()
        graph_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(4, 4, 4, 4)

        # Modern graph canvas (QGraphicsView-based with floating nav buttons)
        # All controls accessible via right-click context menu
        from .graph import ModernGraphCanvas
        self.modern_graph_canvas = ModernGraphCanvas()
        self.modern_graph_canvas.node_clicked.connect(self._on_graph_node_clicked)
        self.modern_graph_canvas.node_double_clicked.connect(self._on_modern_graph_drill_down)
        self.modern_graph_canvas.navigation_changed.connect(self._on_modern_graph_navigation)

        graph_layout.addWidget(self.modern_graph_canvas, 1)

        # Results table
        results_frame = QFrame()
        results_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(4, 4, 4, 4)

        results_header_layout = QHBoxLayout()
        results_header = QLabel("Search Results")
        results_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        results_header_layout.addWidget(results_header)
        self.results_count_label = QLabel("")
        results_header_layout.addWidget(self.results_count_label)
        results_header_layout.addStretch()
        results_layout.addLayout(results_header_layout)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["Name", "Type", "Content", "Links", "Path", "Score"])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results_table.setColumnWidth(0, 180)
        self.results_table.setColumnWidth(1, 80)
        self.results_table.setColumnWidth(2, 150)
        self.results_table.setColumnWidth(3, 70)
        self.results_table.setColumnWidth(4, 200)
        self.results_table.setColumnWidth(5, 50)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.doubleClicked.connect(self._on_result_double_clicked)
        results_layout.addWidget(self.results_table)

        # Vertical splitter for graph/results
        graph_results_splitter = QSplitter(Qt.Orientation.Vertical)
        graph_results_splitter.addWidget(graph_frame)
        graph_results_splitter.addWidget(results_frame)
        graph_results_splitter.setSizes([400, 200])
        left_layout.addWidget(graph_results_splitter)

        main_splitter.addWidget(left_widget)

        # Right: Assistant
        assistant_frame = QFrame()
        assistant_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        assistant_frame.setMinimumWidth(300)
        assistant_frame.setMaximumWidth(450)
        assistant_layout = QVBoxLayout(assistant_frame)
        assistant_layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        assistant_header = QLabel("Assistant")
        assistant_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header_layout.addWidget(assistant_header)
        header_layout.addStretch()

        self.llm_combo = QComboBox()
        self.llm_combo.setFixedWidth(120)
        self._populate_llm_providers()
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        header_layout.addWidget(self.llm_combo)
        assistant_layout.addLayout(header_layout)

        self.llm_status_label = QLabel("")
        self.llm_status_label.setStyleSheet("color: #888; font-size: 10px;")
        assistant_layout.addWidget(self.llm_status_label)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Ask me about your lab files...")
        assistant_layout.addWidget(self.chat_display, stretch=1)

        self.chat_input = QPlainTextEdit()
        self.chat_input.setPlaceholderText("Type a message... (Ctrl+Enter to send)")
        self.chat_input.setMaximumHeight(80)
        self.chat_input.installEventFilter(self)
        assistant_layout.addWidget(self.chat_input)

        buttons_layout = QHBoxLayout()
        self.chat_send_btn = QPushButton("Send")
        self.chat_send_btn.setObjectName("primaryButton")
        self.chat_send_btn.clicked.connect(self._on_chat_send)
        buttons_layout.addWidget(self.chat_send_btn)
        buttons_layout.addStretch()
        self.chat_clear_btn = QPushButton("Clear")
        self.chat_clear_btn.clicked.connect(self._on_chat_clear)
        buttons_layout.addWidget(self.chat_clear_btn)
        assistant_layout.addLayout(buttons_layout)

        main_splitter.addWidget(assistant_frame)
        main_splitter.setSizes([900, 350])
        layout.addWidget(main_splitter)

        self.tabs.addTab(tab, "Search & Explore")

    def _setup_review_tab(self):
        """Setup the Link Review tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with filters
        header_layout = QHBoxLayout()
        header = QLabel("Link Review")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(header)
        header_layout.addStretch()

        strategy_label = QLabel("Strategy:")
        header_layout.addWidget(strategy_label)
        self.review_strategy_combo = QComboBox()
        self.review_strategy_combo.setMinimumWidth(150)
        self.review_strategy_combo.addItem("All Strategies", None)
        self.review_strategy_combo.currentIndexChanged.connect(self._on_review_filter_changed)
        header_layout.addWidget(self.review_strategy_combo)

        status_label = QLabel("Status:")
        header_layout.addWidget(status_label)
        self.review_status_combo = QComboBox()
        self.review_status_combo.addItems(["Pending", "Needs Audit", "Accepted", "Rejected", "All"])
        self.review_status_combo.currentIndexChanged.connect(self._on_review_filter_changed)
        header_layout.addWidget(self.review_status_combo)

        self.review_refresh_btn = QPushButton("Refresh")
        self.review_refresh_btn.clicked.connect(lambda: self._review_vm.refresh_candidates())
        header_layout.addWidget(self.review_refresh_btn)
        layout.addLayout(header_layout)

        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Candidates table
        table_frame = QFrame()
        table_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        table_layout = QVBoxLayout(table_frame)

        stats_layout = QHBoxLayout()
        self.review_stats_label = QLabel("No candidates")
        stats_layout.addWidget(self.review_stats_label)
        stats_layout.addStretch()
        table_layout.addLayout(stats_layout)

        self.candidates_table = QTableWidget()
        self.candidates_table.setColumnCount(6)
        self.candidates_table.setHorizontalHeaderLabels([
            "Source File", "Target File", "Confidence", "Evidence", "Status", "Strategy"
        ])
        header = self.candidates_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.candidates_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidates_table.itemSelectionChanged.connect(self._on_candidate_selected)
        table_layout.addWidget(self.candidates_table)

        main_splitter.addWidget(table_frame)

        # Evidence preview
        evidence_frame = QFrame()
        evidence_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        evidence_layout = QVBoxLayout(evidence_frame)

        evidence_header = QLabel("Evidence Preview")
        evidence_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        evidence_layout.addWidget(evidence_header)

        self.evidence_text = QTextEdit()
        self.evidence_text.setReadOnly(True)
        self.evidence_text.setMaximumHeight(150)
        evidence_layout.addWidget(self.evidence_text)

        main_splitter.addWidget(evidence_frame)
        main_splitter.setSizes([400, 150])
        layout.addWidget(main_splitter)

        # Action buttons
        action_layout = QHBoxLayout()
        self.accept_selected_btn = QPushButton("Accept Selected")
        self.accept_selected_btn.setObjectName("successButton")
        self.accept_selected_btn.clicked.connect(self._on_accept_selected)
        action_layout.addWidget(self.accept_selected_btn)

        self.reject_selected_btn = QPushButton("Reject Selected")
        self.reject_selected_btn.clicked.connect(self._on_reject_selected)
        action_layout.addWidget(self.reject_selected_btn)

        self.audit_selected_btn = QPushButton("Request Audit")
        self.audit_selected_btn.clicked.connect(self._on_audit_selected)
        action_layout.addWidget(self.audit_selected_btn)

        action_layout.addStretch()

        self.accept_high_conf_btn = QPushButton("Accept All High Confidence")
        self.accept_high_conf_btn.clicked.connect(self._on_accept_high_confidence)
        action_layout.addWidget(self.accept_high_conf_btn)

        layout.addLayout(action_layout)
        self.tabs.addTab(tab, "Link Review")

    def _setup_status_bar(self):
        """Setup the status bar."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        readonly_label = QLabel(" READ-ONLY ")
        readonly_label.setObjectName("readOnlyIndicator")
        status_bar.addPermanentWidget(readonly_label)

        db_label = QLabel(f"Index: {self.db_path}")
        db_label.setStyleSheet("color: white; padding: 0 12px;")
        status_bar.addWidget(db_label)

    # -------------------------------------------------------------------------
    # UI Update Methods (bound to ViewModel signals)
    # -------------------------------------------------------------------------

    def _update_roots_list(self):
        """Update roots list from ViewModel."""
        self.roots_list.clear()
        for root in self._index_vm.roots:
            item = QListWidgetItem(f"{root.label} ({root.root_path})")
            item.setData(Qt.ItemDataRole.UserRole, root.root_id)
            self.roots_list.addItem(item)

    def _update_stats(self):
        """Update stats display from ViewModel."""
        stats = self._index_vm.stats
        self.stats_files.setText(f"Files: {stats.file_count:,}")
        self.stats_roots.setText(f"Roots: {stats.roots_count}")
        self.stats_indexed.setText(f"Indexed: {stats.indexed_count:,}")
        self.stats_links.setText(f"Links: {stats.links_count:,}")

    def _update_progress(self, percent: int, message: str):
        """Update progress display."""
        self.crawl_progress.setValue(percent)
        self.crawl_status.setText(message)

    def _on_operation_started(self, operation_type: str):
        """Handle operation start."""
        self.start_crawl_btn.setEnabled(False)
        self.stop_crawl_btn.setEnabled(operation_type == "crawl")
        self.extract_btn.setEnabled(False)
        self.link_btn.setEnabled(False)

    def _on_operation_finished(self, success: bool, message: str):
        """Handle operation completion."""
        self.start_crawl_btn.setEnabled(True)
        self.stop_crawl_btn.setEnabled(False)
        self.extract_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.statusBar().showMessage(message, 5000)

        # Refresh graph
        if success and self._index_vm.roots:
            self._update_graph()

    def _update_results_table(self):
        """Update results table from ViewModel."""
        results = self._search_vm.results
        self.results_table.setRowCount(len(results))
        self.results_count_label.setText(f"({len(results)} results)")

        for row, result in enumerate(results):
            # Name
            name_item = QTableWidgetItem(result.name)
            name_item.setData(Qt.ItemDataRole.UserRole, result.file_id)
            self.results_table.setItem(row, 0, name_item)

            # Type
            self.results_table.setItem(row, 1, QTableWidgetItem(result.category))

            # Content
            content_item = QTableWidgetItem(result.content_excerpt)
            content_item.setToolTip(result.full_excerpt or "No content extracted")
            self.results_table.setItem(row, 2, content_item)

            # Links
            link_text = f"{result.link_count} links" if result.link_count > 0 else ""
            links_item = QTableWidgetItem(link_text)
            links_item.setToolTip(result.format_links_tooltip())
            self.results_table.setItem(row, 3, links_item)

            # Path
            self.results_table.setItem(row, 4, QTableWidgetItem(result.path))

            # Score
            self.results_table.setItem(row, 5, QTableWidgetItem(f"{result.score:.2f}"))

    def _update_graph_navigation(self):
        """Update graph navigation state (handled by canvas floating buttons)."""
        # Navigation buttons are now integrated into the modern_graph_canvas
        pass

    def _update_candidates_table(self):
        """Update candidates table from ViewModel."""
        candidates = self._review_vm.candidates
        self.candidates_table.setRowCount(len(candidates))

        for row, c in enumerate(candidates):
            # Source
            src_item = QTableWidgetItem(c.src_name)
            src_item.setData(Qt.ItemDataRole.UserRole, c.candidate_id)
            self.candidates_table.setItem(row, 0, src_item)

            # Target
            self.candidates_table.setItem(row, 1, QTableWidgetItem(c.dst_name))

            # Confidence
            conf_item = QTableWidgetItem(f"{c.confidence:.0%}")
            if c.confidence >= 0.9:
                conf_item.setBackground(Qt.GlobalColor.darkGreen)
            elif c.confidence >= 0.7:
                conf_item.setBackground(Qt.GlobalColor.darkYellow)
            else:
                conf_item.setBackground(Qt.GlobalColor.darkRed)
            self.candidates_table.setItem(row, 2, conf_item)

            # Evidence
            self.candidates_table.setItem(row, 3, QTableWidgetItem(c.format_evidence_summary()))

            # Status
            self.candidates_table.setItem(row, 4, QTableWidgetItem(c.status))

            # Strategy
            self.candidates_table.setItem(row, 5, QTableWidgetItem(c.strategy_name))

    def _update_review_stats(self):
        """Update review stats label."""
        stats = self._review_vm.stats
        self.review_stats_label.setText(
            f"Pending: {stats.pending} | Accepted: {stats.accepted} | "
            f"Rejected: {stats.rejected} | Needs Audit: {stats.needs_audit}"
        )

    def _update_evidence_preview(self):
        """Update evidence preview."""
        self.evidence_text.setHtml(self._review_vm.evidence_html)

    def _show_status(self, message: str, timeout: int):
        """Show status bar message."""
        self.statusBar().showMessage(message, timeout)

    def _update_graph(self):
        """Update graph with current data."""
        roots = self._index_vm.roots
        if roots:
            self._graph_vm.load_root(roots[0].root_id)
            file_index = self._graph_vm.file_index
            if file_index:
                self.modern_graph_canvas.build_graph(file_index)

    # -------------------------------------------------------------------------
    # Event Handlers (forward to ViewModels)
    # -------------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        self._coordinator.on_tab_changed(index)

    def _on_root_selected(self, current, previous):
        """Handle root selection."""
        if current:
            root_id = current.data(Qt.ItemDataRole.UserRole)
            self._index_vm.select_root(root_id)

    def _on_add_root(self):
        """Handle add root button."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Index",
            options=QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            try:
                root = self._index_vm.add_root(folder)
                self.statusBar().showMessage(f"Added root: {root.label}", 5000)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to add root: {e}")

    def _on_remove_root(self):
        """Handle remove root button."""
        current = self.roots_list.currentItem()
        if current:
            root_id = current.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(
                self, "Remove Root",
                f"Remove '{current.text()}' from the index?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._index_vm.remove_root(root_id)

    def _on_start_crawl(self):
        """Handle start crawl button."""
        if not self._index_vm.start_crawl():
            QMessageBox.information(self, "Select Root", "Please select a root folder to crawl.")

    def _on_stop_crawl(self):
        """Handle stop crawl button."""
        self._index_vm.stop_crawl()

    def _on_start_extraction(self):
        """Handle extract button."""
        if not self._index_vm.start_extraction():
            QMessageBox.warning(self, "No Roots", "Please add and crawl a folder first.")

    def _on_find_links(self):
        """Handle find links button."""
        if not self._index_vm.start_linking():
            QMessageBox.warning(self, "No Roots", "Please add and crawl a folder first.")

    def _on_clear_links(self):
        """Handle clear links button."""
        reply = QMessageBox.question(
            self, "Clear Links",
            "This will remove all auto-detected links. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            removed = self._index_vm.clear_links()
            self.statusBar().showMessage(f"Cleared {removed:,} links", 5000)

    def _on_search(self):
        """Handle search."""
        query = self.search_input.text().strip()
        if query:
            self._search_vm.search(query)

    def _on_result_double_clicked(self, index):
        """Handle result double-click."""
        row = index.row()
        name_item = self.results_table.item(row, 0)
        if name_item:
            file_id = name_item.data(Qt.ItemDataRole.UserRole)
            self._coordinator.load_file_in_inspector(file_id)
            # Show details dialog
            self._show_file_details_dialog(file_id)

    def _show_file_details_dialog(self, file_id: int):
        """Show file details dialog."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox

        roots = self._index_vm.roots
        root_path = roots[0].root_path if roots else None
        self._inspector_vm.load_file(file_id, root_path)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"File Details: {self._inspector_vm.file.name if self._inspector_vm.file else ''}")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(self._inspector_vm.build_details_html())
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    # Graph handlers
    def _on_graph_node_clicked(self, path: str):
        """Handle node selection in graph."""
        self.statusBar().showMessage(f"Selected: {path}", 3000)

    def _on_modern_graph_drill_down(self, path: str):
        """Handle drill-down in modern graph."""
        self._graph_vm.drill_down(path)

    def _on_modern_graph_navigation(self, breadcrumb: list):
        """Handle navigation change in modern graph."""
        # Navigation state is handled by canvas floating buttons
        pass

    # Chat handlers
    def _populate_llm_providers(self):
        """Populate LLM provider dropdown."""
        self.llm_combo.clear()
        for p in self._agent_vm.available_providers:
            status = "+" if p.available else "x"
            self.llm_combo.addItem(f"{status} {p.name}")

    def _on_llm_changed(self, index: int):
        self._agent_vm.select_provider(index)
        self.llm_status_label.setText(self._agent_vm.provider_status)

    def _on_chat_send(self):
        message = self.chat_input.toPlainText().strip()
        if message:
            self.chat_input.clear()
            self._agent_vm.send_message(message)

    def _on_chat_clear(self):
        self.chat_display.clear()
        self._agent_vm.clear_history()

    def _on_chat_message(self, msg):
        """Handle new chat message."""
        import html
        escaped = html.escape(msg.content).replace('\n', '<br>')
        html_msg = f'''
        <div style="margin: 8px 0;">
            <span style="color: {msg.color}; font-weight: bold;">{msg.sender}</span>
            <span style="color: #666; font-size: 10px;"> {msg.timestamp}</span>
            <br><span style="color: #d4d4d4;">{escaped}</span>
        </div>
        '''
        self.chat_display.append(html_msg)
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_agent_thinking(self, thinking: bool):
        self.chat_input.setEnabled(not thinking)
        self.chat_send_btn.setEnabled(not thinking)

    def _on_agent_status(self, status: str):
        self.llm_status_label.setText(status)
        if status:
            self.statusBar().showMessage(status)

    # Review tab handlers
    def _on_review_filter_changed(self):
        status_text = self.review_status_combo.currentText().lower()
        status = None if status_text == "all" else status_text.replace(" ", "_")
        strategy_id = self.review_strategy_combo.currentData()
        self._review_vm.set_filter(status=status, strategy_id=strategy_id)

    def _on_candidate_selected(self):
        selected = self.candidates_table.selectedItems()
        if selected:
            row = selected[0].row()
            src_item = self.candidates_table.item(row, 0)
            if src_item:
                candidate_id = src_item.data(Qt.ItemDataRole.UserRole)
                self._review_vm.select_candidate(candidate_id)

    def _on_accept_selected(self):
        if self._review_vm.accept_selected():
            self.statusBar().showMessage("Candidate accepted", 3000)
            self._index_vm.refresh()

    def _on_reject_selected(self):
        if self._review_vm.reject_selected():
            self.statusBar().showMessage("Candidate rejected", 3000)

    def _on_audit_selected(self):
        if self._review_vm.flag_for_audit():
            self.statusBar().showMessage("Candidate flagged for audit", 3000)

    def _on_accept_high_confidence(self):
        reply = QMessageBox.question(
            self, "Accept High Confidence",
            "Accept all pending candidates with confidence >= 90%?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self._review_vm.accept_high_confidence()
            self.statusBar().showMessage(f"Accepted {count} candidates", 5000)
            self._index_vm.refresh()

    def eventFilter(self, obj, event):
        """Handle Ctrl+Enter to send chat."""
        from PyQt6.QtCore import QEvent
        if obj == self.chat_input and event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_Return and
                event.modifiers() == Qt.KeyboardModifier.ControlModifier):
                self._on_chat_send()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """Handle window close."""
        if self._db:
            self._db.close()
        event.accept()
