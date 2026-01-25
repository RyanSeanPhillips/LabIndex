"""
Main Window for LabIndex.

Two-tab layout:
- Tab 1: Index & Build (manage roots, run crawls)
- Tab 2: Search & Explore (search, graph, assistant)
"""

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QSplitter, QStatusBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QProgressBar, QFileDialog, QMessageBox, QPlainTextEdit, QTextEdit,
    QFrame, QListWidget, QListWidgetItem, QAbstractItemView,
    QComboBox, QCheckBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("LabIndex - Read-Only Lab Drive Indexer")
        self.resize(1400, 900)

        # Database path
        self.db_path = self._get_db_path()

        # Initialize services (lazy)
        self._db = None
        self._fs = None
        self._crawler = None
        self._search = None
        self._extractor = None
        self._linker = None

        self._setup_ui()
        self._setup_status_bar()

    def _get_db_path(self) -> Path:
        """Get the database path in AppData."""
        app_data = Path(os.environ.get("APPDATA", ".")) / "LabIndex"
        app_data.mkdir(parents=True, exist_ok=True)
        return app_data / "labindex.db"

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
        layout.addWidget(self.tabs)

        # Tab 1: Index & Build
        self._setup_index_tab()

        # Tab 2: Search & Explore
        self._setup_search_tab()

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

        # Roots list
        self.roots_list = QListWidget()
        self.roots_list.setMaximumHeight(150)
        roots_layout.addWidget(self.roots_list)

        # Root buttons
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

        # Progress bar
        self.crawl_progress = QProgressBar()
        self.crawl_progress.setTextVisible(True)
        self.crawl_progress.setValue(0)
        crawl_layout.addWidget(self.crawl_progress)

        # Status label
        self.crawl_status = QLabel("Ready to scan")
        self.crawl_status.setStyleSheet("color: #888;")
        crawl_layout.addWidget(self.crawl_status)

        # Crawl buttons
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
        self.extract_btn.setToolTip("Extract text from documents for full-text search")
        self.extract_btn.clicked.connect(self._on_start_extraction)
        crawl_buttons.addWidget(self.extract_btn)

        self.link_btn = QPushButton("Find Links")
        self.link_btn.setToolTip("Auto-detect relationships between files (animal IDs, notes, etc.)")
        self.link_btn.clicked.connect(self._on_find_links)
        crawl_buttons.addWidget(self.link_btn)

        self.clear_links_btn = QPushButton("Clear Links")
        self.clear_links_btn.setToolTip("Remove all auto-detected links (allows re-running with fresh rules)")
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

        self.tabs.addTab(tab, "🔧 Index & Build")

        # Load initial data
        self._refresh_roots_list()
        self._refresh_stats()

    def _setup_search_tab(self):
        """Setup the Search & Explore tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search bar at top
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

        # Main content area: splitter with graph/results on left, assistant on right
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Graph + Results (vertical layout)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Graph visualization frame
        graph_frame = QFrame()
        graph_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(4, 4, 4, 4)
        graph_layout.setSpacing(4)

        # Graph control toolbar (row 1)
        graph_toolbar = QHBoxLayout()
        graph_toolbar.setSpacing(6)

        # Layout selector
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Tree", "Radial", "Balloon", "Spring", "Circular"])
        self.layout_combo.setFixedWidth(75)
        self.layout_combo.setToolTip("Graph layout algorithm")
        self.layout_combo.currentTextChanged.connect(self._on_layout_changed)
        graph_toolbar.addWidget(self.layout_combo)

        # Tree direction
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Top-Down", "Left-Right", "Bottom-Up", "Right-Left"])
        self.direction_combo.setFixedWidth(85)
        self.direction_combo.setToolTip("Tree growth direction")
        self.direction_combo.currentTextChanged.connect(self._on_direction_changed)
        graph_toolbar.addWidget(self.direction_combo)

        # Color mode
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Uniform", "Category", "Depth", "Size"])
        self.color_combo.setFixedWidth(75)
        self.color_combo.setToolTip("Node coloring mode")
        self.color_combo.currentTextChanged.connect(self._on_color_mode_changed)
        graph_toolbar.addWidget(self.color_combo)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #444;")
        graph_toolbar.addWidget(sep1)

        # Show options (compact)
        self.show_files_cb = QCheckBox("Files")
        self.show_files_cb.setChecked(True)
        self.show_files_cb.stateChanged.connect(self._on_show_files_changed)
        graph_toolbar.addWidget(self.show_files_cb)

        self.show_labels_cb = QCheckBox("Labels")
        self.show_labels_cb.setChecked(True)
        self.show_labels_cb.stateChanged.connect(self._on_show_labels_changed)
        graph_toolbar.addWidget(self.show_labels_cb)

        self.show_links_cb = QCheckBox("Links")
        self.show_links_cb.setChecked(False)
        self.show_links_cb.setToolTip("Show relationship links (≥ threshold)")
        self.show_links_cb.stateChanged.connect(self._on_show_links_changed)
        graph_toolbar.addWidget(self.show_links_cb)

        # Link confidence threshold
        self.link_threshold_combo = QComboBox()
        self.link_threshold_combo.addItems(["≥50%", "≥70%", "≥85%", "≥95%"])
        self.link_threshold_combo.setCurrentIndex(1)  # Default 70%
        self.link_threshold_combo.setFixedWidth(60)
        self.link_threshold_combo.setToolTip("Minimum link confidence to display")
        self.link_threshold_combo.currentTextChanged.connect(self._on_link_threshold_changed)
        graph_toolbar.addWidget(self.link_threshold_combo)

        graph_toolbar.addStretch()

        # Settings dropdown for layout tuning
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedWidth(28)
        self.settings_btn.setToolTip("Graph layout settings")
        self.settings_btn.clicked.connect(self._show_graph_settings)
        graph_toolbar.addWidget(self.settings_btn)

        # Navigation buttons
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedWidth(28)
        self.back_btn.setToolTip("Go back")
        self.back_btn.clicked.connect(self._on_graph_back)
        self.back_btn.setEnabled(False)
        graph_toolbar.addWidget(self.back_btn)

        self.home_btn = QPushButton("⌂")
        self.home_btn.setFixedWidth(28)
        self.home_btn.setToolTip("Go to root")
        self.home_btn.clicked.connect(self._on_graph_home)
        graph_toolbar.addWidget(self.home_btn)

        self.fit_btn = QPushButton("⊡")
        self.fit_btn.setFixedWidth(28)
        self.fit_btn.setToolTip("Fit to view")
        self.fit_btn.clicked.connect(self._on_graph_fit)
        graph_toolbar.addWidget(self.fit_btn)

        graph_layout.addLayout(graph_toolbar)

        # Import and create GraphCanvas
        from labindex_app.views.graph_canvas import GraphCanvas
        self.graph_canvas = GraphCanvas()
        self.graph_canvas.node_clicked.connect(self._on_graph_node_clicked)
        self.graph_canvas.navigation_changed.connect(self._on_graph_navigation_changed)
        graph_layout.addWidget(self.graph_canvas, 1)  # Stretch factor 1

        # Results table (below graph)
        results_frame = QFrame()
        results_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(4, 4, 4, 4)
        results_layout.setSpacing(2)

        # Results header with count
        results_header_layout = QHBoxLayout()
        results_header = QLabel("Search Results")
        results_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        results_header.setStyleSheet("color: #4fc3f7;")
        results_header_layout.addWidget(results_header)
        self.results_count_label = QLabel("")
        self.results_count_label.setStyleSheet("color: #888;")
        results_header_layout.addWidget(self.results_count_label)
        results_header_layout.addStretch()
        results_layout.addLayout(results_header_layout)

        # Enhanced results table with Content and Links columns
        # All columns are user-resizable (Interactive mode)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["Name", "Type", "Content", "Links", "Path", "Score"])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # All columns resizable
        header.setStretchLastSection(False)
        # Set initial column widths
        self.results_table.setColumnWidth(0, 180)  # Name
        self.results_table.setColumnWidth(1, 80)   # Type
        self.results_table.setColumnWidth(2, 150)  # Content
        self.results_table.setColumnWidth(3, 70)   # Links
        self.results_table.setColumnWidth(4, 200)  # Path
        self.results_table.setColumnWidth(5, 50)   # Score
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.doubleClicked.connect(self._on_result_double_clicked)
        self.results_table.setMouseTracking(True)
        self.results_table.cellEntered.connect(self._on_result_cell_hover)
        results_layout.addWidget(self.results_table)

        # Use a splitter between graph and results for resizable divider
        graph_results_splitter = QSplitter(Qt.Orientation.Vertical)
        graph_results_splitter.addWidget(graph_frame)
        graph_results_splitter.addWidget(results_frame)
        graph_results_splitter.setSizes([400, 200])  # Initial 2:1 ratio
        graph_results_splitter.setHandleWidth(6)  # Visible drag handle
        left_layout.addWidget(graph_results_splitter)

        main_splitter.addWidget(left_widget)

        # Right side: Assistant chat
        assistant_frame = QFrame()
        assistant_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        assistant_frame.setMinimumWidth(300)
        assistant_frame.setMaximumWidth(450)
        assistant_layout = QVBoxLayout(assistant_frame)
        assistant_layout.setContentsMargins(8, 8, 8, 8)

        # Header with LLM provider selector
        header_layout = QHBoxLayout()
        assistant_header = QLabel("🤖 Assistant")
        assistant_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        assistant_header.setStyleSheet("color: #4fc3f7;")
        header_layout.addWidget(assistant_header)
        header_layout.addStretch()

        # LLM provider dropdown
        self.llm_combo = QComboBox()
        self.llm_combo.setFixedWidth(120)
        self.llm_combo.setToolTip("Select LLM provider")
        self._populate_llm_providers()
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        header_layout.addWidget(self.llm_combo)

        assistant_layout.addLayout(header_layout)

        # Status label for LLM
        self.llm_status_label = QLabel("")
        self.llm_status_label.setStyleSheet("color: #888; font-size: 10px;")
        assistant_layout.addWidget(self.llm_status_label)

        # Chat display (QTextEdit for HTML formatting)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Ask me about your lab files...\n\n"
            "Examples:\n"
            "• Find notes for recording_001.abf\n"
            "• What experiments used PenkCre?\n"
            "• Show me conference slides from 2024"
        )
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        assistant_layout.addWidget(self.chat_display, stretch=1)

        # Chat input - multi-line text box above buttons
        self.chat_input = QPlainTextEdit()
        self.chat_input.setPlaceholderText("Type a message... (Ctrl+Enter to send)")
        self.chat_input.setMaximumHeight(80)
        self.chat_input.setMinimumHeight(50)
        # Install event filter for Ctrl+Enter to send
        self.chat_input.installEventFilter(self)
        assistant_layout.addWidget(self.chat_input)

        # Buttons row below input
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

        self.tabs.addTab(tab, "🔍 Search & Explore")

    def _setup_status_bar(self):
        """Setup the status bar with read-only indicator."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Read-only indicator (always visible)
        readonly_label = QLabel(" READ-ONLY ")
        readonly_label.setObjectName("readOnlyIndicator")
        status_bar.addPermanentWidget(readonly_label)

        # Database location
        db_label = QLabel(f"Index: {self.db_path}")
        db_label.setStyleSheet("color: white; padding: 0 12px;")
        status_bar.addWidget(db_label)

    # === Event Handlers ===

    def _on_add_root(self):
        """Add a new root folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Index",
            options=QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            try:
                root = self.crawler.add_root(folder)
                self._refresh_roots_list()
                self._refresh_stats()
                self.statusBar().showMessage(f"Added root: {root.label}", 5000)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to add root: {e}")

    def _on_remove_root(self):
        """Remove the selected root."""
        current = self.roots_list.currentItem()
        if current:
            root_id = current.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(
                self, "Remove Root",
                f"Remove '{current.text()}' from the index?\n\n"
                "This will delete all indexed files for this root.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.crawler.remove_root(root_id)
                self._refresh_roots_list()
                self._refresh_stats()

    def _on_start_crawl(self):
        """Start crawling selected root."""
        current = self.roots_list.currentItem()
        if not current:
            QMessageBox.information(self, "Select Root", "Please select a root folder to crawl.")
            return

        root_id = current.data(Qt.ItemDataRole.UserRole)
        self.start_crawl_btn.setEnabled(False)
        self.stop_crawl_btn.setEnabled(True)
        self.crawl_status.setText("Starting crawl...")

        # Run crawl in background thread
        self._crawl_thread = CrawlThread(self.crawler, root_id)
        self._crawl_thread.progress.connect(self._on_crawl_progress)
        self._crawl_thread.finished.connect(self._on_crawl_finished)
        self._crawl_thread.start()

    def _on_stop_crawl(self):
        """Stop the current crawl."""
        if hasattr(self, "_crawl_thread"):
            self.crawler.cancel()
            self.crawl_status.setText("Stopping...")

    def _on_crawl_progress(self, dirs: int, files: int, current: str):
        """Handle crawl progress update."""
        self.crawl_status.setText(f"Scanning: {current}")
        self.stats_files.setText(f"Files: {files}")

    def _on_crawl_finished(self, success: bool, message: str):
        """Handle crawl completion."""
        self.start_crawl_btn.setEnabled(True)
        self.stop_crawl_btn.setEnabled(False)
        self.crawl_status.setText(message)
        self._refresh_stats()

        # Populate graph with new data
        if success and hasattr(self, 'graph_canvas'):
            self._populate_graph()

    def _on_start_extraction(self):
        """Start content extraction for selected root."""
        roots = self.crawler.get_roots()
        if not roots:
            QMessageBox.warning(self, "No Roots", "Please add and crawl a folder first.")
            return

        # Use first root (TODO: let user select)
        root = roots[0]

        # Create and start extraction thread
        self._extract_thread = ExtractThread(self.extractor, root.root_id)
        self._extract_thread.progress.connect(self._on_extract_progress)
        self._extract_thread.finished.connect(self._on_extract_finished)
        self._extract_thread.start()

        # Update UI
        self.extract_btn.setEnabled(False)
        self.crawl_status.setText("Extracting content...")

    def _on_extract_progress(self, processed: int, total: int, current: str):
        """Handle extraction progress update."""
        self.crawl_status.setText(f"Extracting: {current}")
        if total > 0:
            self.crawl_progress.setValue(int(processed * 100 / total))

    def _on_extract_finished(self, success: bool, message: str):
        """Handle extraction completion."""
        self.extract_btn.setEnabled(True)
        self.crawl_status.setText(message)
        self.crawl_progress.setValue(100 if success else 0)
        self._refresh_stats()

    def _on_find_links(self):
        """Start auto-linking for selected root."""
        roots = self.crawler.get_roots()
        if not roots:
            QMessageBox.warning(self, "No Roots", "Please add and crawl a folder first.")
            return

        # Use first root (TODO: let user select)
        root = roots[0]

        # Create and start link thread
        self._link_thread = LinkThread(self.linker, root.root_id)
        self._link_thread.progress.connect(self._on_link_progress)
        self._link_thread.finished.connect(self._on_link_finished)
        self._link_thread.start()

        # Update UI
        self.link_btn.setEnabled(False)
        self.crawl_status.setText("Finding relationships...")

    def _on_link_progress(self, message: str):
        """Handle linking progress update."""
        self.crawl_status.setText(message)

    def _on_link_finished(self, success: bool, message: str):
        """Handle linking completion."""
        self.link_btn.setEnabled(True)
        self.crawl_status.setText(message)
        self._refresh_stats()

    def _on_clear_links(self):
        """Clear all auto-generated links."""
        roots = self.crawler.get_roots()
        if not roots:
            QMessageBox.warning(self, "No Roots", "No roots to clear links from.")
            return

        reply = QMessageBox.question(
            self, "Clear Links",
            "This will remove all auto-detected links.\n"
            "You can re-run 'Find Links' afterward.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear links for all roots
        total_removed = 0
        for root in roots:
            removed = self.linker.clear_links(root.root_id)
            total_removed += removed

        self.crawl_status.setText(f"Cleared {total_removed:,} links")
        self._refresh_stats()

    def _on_search(self):
        """Perform search."""
        query = self.search_input.text().strip()
        if not query:
            return

        results = self.search.search(query, limit=100)
        self._populate_results(results)

        # Highlight results in graph
        if hasattr(self, 'graph_canvas'):
            self._highlight_search_results(results)

    def _populate_results(self, results):
        """Populate results table with all 6 columns."""
        self._current_results = results  # Store for selection handling
        self.results_table.setRowCount(len(results))
        self.results_count_label.setText(f"({len(results)} results)")

        for row, result in enumerate(results):
            # Column 0: Name (with file_id stored)
            name_item = QTableWidgetItem(result.name)
            name_item.setData(Qt.ItemDataRole.UserRole, result.file_id)
            self.results_table.setItem(row, 0, name_item)

            # Column 1: Type (category)
            self.results_table.setItem(row, 1, QTableWidgetItem(result.file_record.category.value))

            # Column 2: Content (excerpt preview)
            content = self.db.get_content(result.file_id)
            content_preview = ""
            if content and content.content_excerpt:
                # First 60 chars of excerpt
                content_preview = content.content_excerpt[:60].replace('\n', ' ')
                if len(content.content_excerpt) > 60:
                    content_preview += "..."
            content_item = QTableWidgetItem(content_preview)
            content_item.setToolTip(content.content_excerpt if content and content.content_excerpt else "No content extracted")
            self.results_table.setItem(row, 2, content_item)

            # Column 3: Links (count of related files)
            edges_from = self.db.get_edges_from(result.file_id)
            edges_to = self.db.get_edges_to(result.file_id)
            link_count = len(edges_from) + len(edges_to)
            link_text = f"{link_count} links" if link_count > 0 else ""

            # Build tooltip with link details
            if link_count > 0:
                link_details = []
                for edge in edges_from[:3]:  # Show first 3
                    other = self.db.get_file(edge.dst_file_id)
                    if other:
                        link_details.append(f"→ {other.name} ({edge.relation_type.value}, {edge.confidence:.0%})")
                for edge in edges_to[:3]:
                    other = self.db.get_file(edge.src_file_id)
                    if other:
                        link_details.append(f"← {other.name} ({edge.relation_type.value}, {edge.confidence:.0%})")
                if link_count > 6:
                    link_details.append(f"... and {link_count - 6} more")
                tooltip = "\n".join(link_details)
            else:
                tooltip = "No links"

            links_item = QTableWidgetItem(link_text)
            links_item.setToolTip(tooltip)
            self.results_table.setItem(row, 3, links_item)

            # Column 4: Path
            self.results_table.setItem(row, 4, QTableWidgetItem(result.path))

            # Column 5: Score
            self.results_table.setItem(row, 5, QTableWidgetItem(f"{result.score:.2f}"))

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.1f} MB"
        else:
            return f"{size_bytes / 1024 / 1024 / 1024:.1f} GB"

    def eventFilter(self, obj, event):
        """Handle Ctrl+Enter to send chat message."""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if obj == self.chat_input and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if (key_event.key() == Qt.Key.Key_Return and
                key_event.modifiers() == Qt.KeyboardModifier.ControlModifier):
                self._on_chat_send()
                return True
        return super().eventFilter(obj, event)

    def _on_chat_send(self):
        """Send chat message to assistant."""
        message = self.chat_input.toPlainText().strip()
        if not message:
            return

        self.chat_input.clear()
        self._append_chat("You", message, "#4fc3f7")

        # Check if we have an LLM configured
        if not hasattr(self, '_agent') or self._agent is None:
            self._init_agent()

        if self._agent is None:
            self._append_chat(
                "Assistant",
                "No LLM available. Please select a provider or start Ollama.",
                "#ff6b6b"
            )
            return

        # Disable input while processing
        self.chat_input.setEnabled(False)
        self.chat_send_btn.setEnabled(False)
        self.llm_status_label.setText("Thinking...")
        self.statusBar().showMessage("Assistant is thinking...")
        QApplication.processEvents()

        # Run agent query in background thread
        self._chat_thread = AgentThread(self._agent, message)
        self._chat_thread.status_update.connect(self._on_agent_status)
        self._chat_thread.finished.connect(self._on_agent_response)
        self._chat_thread.start()

    def _on_agent_status(self, status: str):
        """Handle agent status updates."""
        # Show with emoji based on status type
        if "tool" in status.lower() or "search" in status.lower():
            display = f"🔧 {status}"
        else:
            display = f"🤔 {status}"
        self.llm_status_label.setText(display)
        self.statusBar().showMessage(display)
        QApplication.processEvents()

    def _on_agent_response(self, response_content: str, tool_calls: list, error: str):
        """Handle agent response."""
        self.chat_input.setEnabled(True)
        self.chat_send_btn.setEnabled(True)
        self.llm_status_label.setText("")
        self.statusBar().showMessage("Ready")

        if error:
            self._append_chat("Error", error, "#ff6b6b")
        else:
            # Show tool calls if any
            if tool_calls:
                tools_str = ", ".join(tool_calls)
                self._append_chat("Tools", f"🔧 Used: {tools_str}", "#888888")

            self._append_chat("Assistant", response_content, "#90ff90")

    def _append_chat(self, sender: str, message: str, color: str):
        """Append a styled message to the chat display."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M")

        # Escape HTML in message but preserve newlines
        import html
        escaped = html.escape(message).replace('\n', '<br>')

        html_msg = f'''
        <div style="margin: 8px 0;">
            <span style="color: {color}; font-weight: bold;">{sender}</span>
            <span style="color: #666; font-size: 10px;"> {timestamp}</span>
            <br>
            <span style="color: #d4d4d4;">{escaped}</span>
        </div>
        '''
        self.chat_display.append(html_msg)
        # Scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_chat_clear(self):
        """Clear chat history."""
        self.chat_display.clear()
        if hasattr(self, '_agent') and self._agent:
            self._agent.clear_history()

    def _populate_llm_providers(self):
        """Populate the LLM provider dropdown."""
        try:
            from labindex_core.adapters.llm_factory import get_available_providers
            providers = get_available_providers()

            self.llm_combo.clear()
            self._llm_providers = providers

            for p in providers:
                status = "✓" if p["available"] else "✗"
                self.llm_combo.addItem(f"{status} {p['name']}")

            # Select first available
            for i, p in enumerate(providers):
                if p["available"]:
                    self.llm_combo.setCurrentIndex(i)
                    break
        except Exception as e:
            self.llm_combo.addItem("No providers")
            self._llm_providers = []

    def _on_llm_changed(self, index: int):
        """Handle LLM provider change."""
        if not hasattr(self, '_llm_providers') or index < 0:
            return

        if index >= len(self._llm_providers):
            return

        provider_info = self._llm_providers[index]
        if provider_info["available"]:
            self.llm_status_label.setText(f"Using {provider_info['name']}")
            self._agent = None  # Reset agent to use new provider
            self._init_agent()
        else:
            reason = provider_info.get("reason", "Not available")
            self.llm_status_label.setText(f"Not available: {reason}")
            self._agent = None

    def _init_agent(self):
        """Initialize the agent with the selected LLM provider."""
        if not hasattr(self, '_llm_providers') or not self._llm_providers:
            self._agent = None
            return

        index = self.llm_combo.currentIndex()
        if index < 0 or index >= len(self._llm_providers):
            self._agent = None
            return

        provider_info = self._llm_providers[index]
        if not provider_info["available"]:
            self._agent = None
            return

        try:
            from labindex_core.adapters.llm_factory import create_llm
            from labindex_core.services.agent_service import AgentService

            llm = create_llm(provider_info["provider"])
            if llm:
                self._agent = AgentService(llm, self.db, self.fs)
                self.llm_status_label.setText(f"Ready: {llm.get_model_name()}")
            else:
                self._agent = None
                self.llm_status_label.setText("Failed to create LLM")
        except Exception as e:
            self._agent = None
            self.llm_status_label.setText(f"Error: {str(e)[:30]}")

    def _refresh_roots_list(self):
        """Refresh the roots list."""
        self.roots_list.clear()
        for root in self.crawler.get_roots():
            item = QListWidgetItem(f"{root.label} ({root.root_path})")
            item.setData(Qt.ItemDataRole.UserRole, root.root_id)
            self.roots_list.addItem(item)

    def _refresh_stats(self):
        """Refresh statistics."""
        stats = self.search.get_stats()
        self.stats_files.setText(f"Files: {stats['file_count']:,}")
        self.stats_roots.setText(f"Roots: {stats['roots']}")
        self.stats_indexed.setText(f"Indexed: {stats['indexed_count']:,}")
        self.stats_links.setText(f"Links: {stats['edge_count']:,}")

    # === Graph Methods ===

    def _on_graph_node_clicked(self, path: str):
        """Handle click on a graph node."""
        self.statusBar().showMessage(f"Selected: {path}", 3000)
        # TODO: Show details panel for the clicked node

    def _on_graph_navigation_changed(self, breadcrumb: list):
        """Handle graph navigation changes."""
        # Enable/disable back button based on navigation history
        has_history = len(breadcrumb) > 1
        self.back_btn.setEnabled(has_history)

    def _on_layout_changed(self, layout: str):
        """Handle layout combo change."""
        self.graph_canvas.set_layout(layout)
        # Show/hide direction combo based on layout (only relevant for tree layouts)
        is_tree = layout == "Tree"
        self.direction_combo.setVisible(is_tree)

    def _on_direction_changed(self, direction: str):
        """Handle tree direction change."""
        self.graph_canvas.set_tree_direction(direction)

    def _on_color_mode_changed(self, mode: str):
        """Handle color mode change."""
        self.graph_canvas.set_color_mode(mode)

    def _on_show_files_changed(self, state: int):
        """Handle show files checkbox."""
        self.graph_canvas.set_show_files(state == Qt.CheckState.Checked.value)

    def _on_show_labels_changed(self, state: int):
        """Handle show labels checkbox."""
        self.graph_canvas.set_show_labels(state == Qt.CheckState.Checked.value)

    def _on_show_links_changed(self, state: int):
        """Handle show links checkbox."""
        show = state == Qt.CheckState.Checked.value
        if show:
            # Load relationship edges into graph
            self._load_graph_links()
        else:
            self.graph_canvas.clear_relationship_edges()
        self.graph_canvas.show_relationship_edges = show
        self.graph_canvas.update()

    def _on_link_threshold_changed(self, threshold_text: str):
        """Handle link confidence threshold change."""
        # Parse threshold from text like "≥70%"
        threshold_map = {"≥50%": 0.50, "≥70%": 0.70, "≥85%": 0.85, "≥95%": 0.95}
        threshold = threshold_map.get(threshold_text, 0.70)
        self.graph_canvas.set_link_threshold(threshold)
        # Reload links if currently showing
        if self.show_links_cb.isChecked():
            self._load_graph_links()

    def _show_graph_settings(self):
        """Show graph layout settings dialog."""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Graph Layout Settings")
        dialog.setMinimumWidth(300)

        form = QFormLayout(dialog)

        # Node spacing
        node_spacing = QSpinBox()
        node_spacing.setRange(10, 200)
        node_spacing.setValue(self.graph_canvas.node_spacing)
        form.addRow("Node Spacing:", node_spacing)

        # Layer spacing (for tree layout)
        layer_spacing = QSpinBox()
        layer_spacing.setRange(20, 300)
        layer_spacing.setValue(self.graph_canvas.layer_spacing)
        form.addRow("Layer Spacing:", layer_spacing)

        # Node size
        node_size = QSpinBox()
        node_size.setRange(4, 40)
        node_size.setValue(self.graph_canvas.node_size)
        form.addRow("Node Size:", node_size)

        # Font size
        font_size = QSpinBox()
        font_size.setRange(6, 18)
        font_size.setValue(self.graph_canvas.font_size)
        form.addRow("Label Font Size:", font_size)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply settings
            self.graph_canvas.node_spacing = node_spacing.value()
            self.graph_canvas.layer_spacing = layer_spacing.value()
            self.graph_canvas.node_size = node_size.value()
            self.graph_canvas.font_size = font_size.value()
            self.graph_canvas.recalculate_layout()
            self.graph_canvas.update()

    def _on_result_double_clicked(self, index):
        """Handle double-click on a result row - show full details."""
        row = index.row()
        name_item = self.results_table.item(row, 0)
        if not name_item:
            return

        file_id = name_item.data(Qt.ItemDataRole.UserRole)
        if file_id is None:
            return

        self._show_file_details_dialog(file_id)

    def _show_file_details_dialog(self, file_id: int):
        """Show a dialog with full file details."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox

        file = self.db.get_file(file_id)
        if not file:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"File Details: {file.name}")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)

        # Build HTML content
        html = f"""
        <h2>{file.name}</h2>
        <p><b>Path:</b> {file.path}</p>
        <p><b>Category:</b> {file.category.value}</p>
        <p><b>Size:</b> {self._format_size(file.size_bytes)}</p>
        <p><b>Status:</b> {file.status.value}</p>
        """

        # Extracted content
        content = self.db.get_content(file_id)
        if content and content.full_text:
            preview = content.full_text[:2000]
            if len(content.full_text) > 2000:
                preview += f"\n\n... ({len(content.full_text):,} chars total)"
            html += f"""
            <h3>Extracted Content</h3>
            <pre style="background: #2d2d30; padding: 8px; white-space: pre-wrap;">{preview}</pre>
            """

        # Links
        edges_from = self.db.get_edges_from(file_id)
        edges_to = self.db.get_edges_to(file_id)

        if edges_from or edges_to:
            html += "<h3>Related Files</h3><ul>"
            for edge in sorted(edges_from, key=lambda e: e.confidence, reverse=True):
                other = self.db.get_file(edge.dst_file_id)
                if other:
                    html += f"<li>→ <b>{other.name}</b> ({edge.relation_type.value}, {edge.confidence:.0%})"
                    if edge.evidence:
                        html += f" - {edge.evidence}"
                    html += "</li>"
            for edge in sorted(edges_to, key=lambda e: e.confidence, reverse=True):
                other = self.db.get_file(edge.src_file_id)
                if other:
                    html += f"<li>← <b>{other.name}</b> ({edge.relation_type.value}, {edge.confidence:.0%})"
                    if edge.evidence:
                        html += f" - {edge.evidence}"
                    html += "</li>"
            html += "</ul>"

        browser.setHtml(html)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _on_result_cell_hover(self, row: int, col: int):
        """Handle cell hover - update tooltip dynamically if needed."""
        # Tooltips are already set in _populate_results, but this could be used
        # for lazy loading of tooltip content for large result sets
        pass

    def _on_graph_back(self):
        """Navigate back in graph."""
        self.graph_canvas.navigate_back()

    def _on_graph_home(self):
        """Navigate to graph root."""
        self.graph_canvas.navigate_to_root()

    def _on_graph_fit(self):
        """Fit graph to view."""
        self.graph_canvas.fit_to_view()

    def _load_graph_links(self):
        """Load relationship edges from database into graph."""
        roots = self.crawler.get_roots()
        if not roots:
            return

        root_id = roots[0].root_id
        files = self.db.list_files(root_id, limit=10000)

        # Build file path to ID mapping
        path_to_id = {f.path: f.file_id for f in files}

        # Collect relationship edges
        relationship_edges = []
        for f in files:
            edges = self.db.get_edges_from(f.file_id)
            for edge in edges:
                # Find the destination file
                dst_file = self.db.get_file(edge.dst_file_id)
                if dst_file:
                    relationship_edges.append({
                        'src_path': f.path,
                        'dst_path': dst_file.path,
                        'relation_type': edge.relation_type.value,
                        'confidence': edge.confidence,
                        'evidence': edge.evidence
                    })

        self.graph_canvas.set_relationship_edges(relationship_edges)

    def _populate_graph(self, root_id: Optional[int] = None):
        """Populate the graph with file index data."""
        try:
            # Get all files for the root
            roots = self.crawler.get_roots()
            if not roots:
                return

            # Use first root if none specified
            if root_id is None:
                root_id = roots[0].root_id

            root = self.db.get_root(root_id)
            if not root:
                return

            # Get files and convert to the format GraphCanvas expects
            files = self.search.list_files(root_id, limit=5000)

            # Build file index dict for GraphCanvas
            file_index = {
                'root': root.root_path,
                'total_files': len(files),
                'files': []
            }

            for f in files:
                file_info = {
                    'name': f.name,
                    'path': f.path,
                    'full_path': str(Path(root.root_path) / f.path),
                    'parent': f.parent_path,
                    'is_dir': f.is_dir,
                    'category': f.category.value,
                    'size_kb': f.size_bytes // 1024,  # GraphCanvas expects size_kb
                }
                file_index['files'].append(file_info)

            # Update the graph canvas
            self.graph_canvas.build_graph(file_index, preserve_full_index=False)
            self.graph_canvas.update()

        except Exception as e:
            print(f"[ERROR] Failed to populate graph: {e}")
            import traceback
            traceback.print_exc()

    def _highlight_search_results(self, results):
        """Highlight search results in the graph."""
        paths = {r.path for r in results}
        self.graph_canvas.set_highlighted_paths(paths)
        self.graph_canvas.update()

    def closeEvent(self, event):
        """Handle window close."""
        if self._db:
            self._db.close()
        event.accept()


class CrawlThread(QThread):
    """Background thread for crawling."""

    progress = pyqtSignal(int, int, str)  # dirs, files, current_path
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, crawler, root_id: int):
        super().__init__()
        self.crawler = crawler
        self.root_id = root_id

    def run(self):
        try:
            def on_progress(p):
                self.progress.emit(p.dirs_scanned, p.files_found, p.current_path)

            result = self.crawler.crawl_root(self.root_id, progress_callback=on_progress)
            self.finished.emit(
                True,
                f"Crawl complete: {result.files_found:,} files in {result.dirs_scanned:,} directories"
            )
        except Exception as e:
            self.finished.emit(False, f"Crawl failed: {e}")


class ExtractThread(QThread):
    """Background thread for content extraction."""

    progress = pyqtSignal(int, int, str)  # processed, total, current_file
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, extractor, root_id: int):
        super().__init__()
        self.extractor = extractor
        self.root_id = root_id

    def run(self):
        try:
            def on_progress(p):
                self.progress.emit(p.files_processed, p.files_total, p.current_file)

            result = self.extractor.extract_root(self.root_id, progress_callback=on_progress)
            self.finished.emit(
                True,
                f"Extraction complete: {result.success_count:,} indexed, "
                f"{result.skipped_count:,} skipped, {result.error_count:,} errors"
            )
        except Exception as e:
            self.finished.emit(False, f"Extraction failed: {e}")


class LinkThread(QThread):
    """Background thread for auto-linking files."""

    progress = pyqtSignal(str)  # status message
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, linker, root_id: int):
        super().__init__()
        self.linker = linker
        self.root_id = root_id

    def run(self):
        try:
            self.progress.emit("Analyzing files for relationships...")
            result = self.linker.link_root(self.root_id)
            self.finished.emit(
                True,
                f"Linking complete: {result.edges_created:,} relationships found "
                f"in {result.elapsed_seconds:.1f}s"
            )
        except Exception as e:
            self.finished.emit(False, f"Linking failed: {e}")


class AgentThread(QThread):
    """Background thread for agent queries."""

    status_update = pyqtSignal(str)  # status message
    finished = pyqtSignal(str, list, str)  # response, tool_calls, error

    def __init__(self, agent, message: str):
        super().__init__()
        self.agent = agent
        self.message = message

    def run(self):
        try:
            # Use the streaming query to get status updates
            response = None
            for update in self.agent.query_stream(self.message):
                if isinstance(update, str):
                    self.status_update.emit(update)
                else:
                    response = update

            if response:
                self.finished.emit(
                    response.content,
                    response.tool_calls_made,
                    response.error or ""
                )
            else:
                # Fallback to non-streaming
                response = self.agent.query(self.message)
                self.finished.emit(
                    response.content,
                    response.tool_calls_made,
                    response.error or ""
                )
        except Exception as e:
            self.finished.emit("", [], str(e))
