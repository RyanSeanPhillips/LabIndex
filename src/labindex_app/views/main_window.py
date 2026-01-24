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
    QProgressBar, QFileDialog, QMessageBox, QPlainTextEdit,
    QFrame, QListWidget, QListWidgetItem, QAbstractItemView
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

        # Left side: Graph + Results
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Vertical splitter for graph and results
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # Graph visualization
        graph_frame = QFrame()
        graph_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        graph_frame.setMinimumHeight(300)
        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(0, 0, 0, 0)

        # Import and create GraphCanvas
        from labindex_app.views.graph_canvas import GraphCanvas
        self.graph_canvas = GraphCanvas()
        self.graph_canvas.node_clicked.connect(self._on_graph_node_clicked)
        graph_layout.addWidget(self.graph_canvas)

        left_splitter.addWidget(graph_frame)

        # Results table
        results_frame = QFrame()
        results_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(8, 8, 8, 8)

        results_header = QLabel("Search Results")
        results_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        results_header.setStyleSheet("color: #4fc3f7;")
        results_layout.addWidget(results_header)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Name", "Type", "Path", "Score"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        results_layout.addWidget(self.results_table)

        left_splitter.addWidget(results_frame)
        left_splitter.setSizes([400, 300])

        left_layout.addWidget(left_splitter)
        main_splitter.addWidget(left_widget)

        # Right side: Assistant chat
        assistant_frame = QFrame()
        assistant_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        assistant_frame.setMinimumWidth(300)
        assistant_frame.setMaximumWidth(450)
        assistant_layout = QVBoxLayout(assistant_frame)
        assistant_layout.setContentsMargins(8, 8, 8, 8)

        assistant_header = QLabel("🤖 Assistant")
        assistant_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        assistant_header.setStyleSheet("color: #4fc3f7;")
        assistant_layout.addWidget(assistant_header)

        self.chat_display = QPlainTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Ask me about your lab files...\n\n"
            "Examples:\n"
            "• Find notes for recording_001.abf\n"
            "• What experiments used PenkCre?\n"
            "• Show me conference slides from 2024"
        )
        assistant_layout.addWidget(self.chat_display, stretch=1)

        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask a question...")
        self.chat_input.returnPressed.connect(self._on_chat_send)
        chat_input_layout.addWidget(self.chat_input)

        self.chat_send_btn = QPushButton("Send")
        self.chat_send_btn.clicked.connect(self._on_chat_send)
        chat_input_layout.addWidget(self.chat_send_btn)

        assistant_layout.addLayout(chat_input_layout)

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
        """Populate results table."""
        self.results_table.setRowCount(len(results))

        for row, result in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(result.name))
            self.results_table.setItem(row, 1, QTableWidgetItem(result.file_record.category.value))
            self.results_table.setItem(row, 2, QTableWidgetItem(result.path))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{result.score:.2f}"))

    def _on_chat_send(self):
        """Send chat message to assistant."""
        message = self.chat_input.text().strip()
        if not message:
            return

        self.chat_input.clear()
        self.chat_display.appendPlainText(f"You: {message}\n")

        # TODO: Integrate with LLM agent
        self.chat_display.appendPlainText(
            "Assistant: I'm not connected to an LLM yet. "
            "This will be implemented in a future phase.\n"
        )

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

    # === Graph Methods ===

    def _on_graph_node_clicked(self, path: str):
        """Handle click on a graph node."""
        self.statusBar().showMessage(f"Selected: {path}", 3000)
        # TODO: Show details panel for the clicked node

    def _populate_graph(self, root_id: Optional[int] = None):
        """Populate the graph with file index data."""
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
                'size': f.size_bytes,
            }
            file_index['files'].append(file_info)

        # Update the graph canvas
        self.graph_canvas.build_graph(file_index, preserve_full_index=True)
        self.graph_canvas.update()

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
