"""
Strategy Builder Dialog - LLM-assisted linking strategy creation.

Guides users through:
1. Selecting source and destination folders
2. Analyzing folder conventions
3. Generating strategy with LLM assistance
4. Testing and saving the strategy
"""

import json
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox,
    QGroupBox, QProgressBar, QDialogButtonBox, QMessageBox,
    QFileDialog, QSplitter, QFrame, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from labindex_core.domain.enums import EdgeType
from labindex_core.ports.db_port import DBPort


class AnalyzeThread(QThread):
    """Background thread for folder analysis."""
    finished = pyqtSignal(object, object)  # src_analysis, dst_analysis
    error = pyqtSignal(str)

    def __init__(self, trainer, root_id: int, src_folder: str, dst_folder: str):
        super().__init__()
        self.trainer = trainer
        self.root_id = root_id
        self.src_folder = src_folder
        self.dst_folder = dst_folder

    def run(self):
        try:
            src_analysis = self.trainer.analyze_branch(
                self.root_id, self.src_folder, sample_size=50
            )
            dst_analysis = self.trainer.analyze_branch(
                self.root_id, self.dst_folder, sample_size=50
            )
            self.finished.emit(src_analysis, dst_analysis)
        except Exception as e:
            self.error.emit(str(e))


class StrategyBuilderDialog(QDialog):
    """Dialog for building linking strategies with LLM assistance."""

    def __init__(self, db: DBPort, parent=None):
        super().__init__(parent)
        self.db = db
        self._trainer = None
        self._src_analysis = None
        self._dst_analysis = None
        self._proposed_strategy = None

        self.setWindowTitle("Build Linking Strategy")
        self.setMinimumSize(700, 600)

        self._setup_ui()

    @property
    def trainer(self):
        """Lazy load trainer service."""
        if self._trainer is None:
            from labindex_core.services.linker_trainer import LinkerTrainer
            self._trainer = LinkerTrainer(self.db)
        return self._trainer

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("Build Linking Strategy")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4fc3f7;")
        layout.addWidget(title)

        # Step 1: Folder Selection
        folder_group = QGroupBox("Step 1: Select Folders")
        folder_layout = QFormLayout(folder_group)

        # Root selector
        self.root_combo = QComboBox()
        self._populate_roots()
        folder_layout.addRow("Root:", self.root_combo)

        # Source folder
        src_layout = QHBoxLayout()
        self.src_input = QLineEdit()
        self.src_input.setPlaceholderText("Path to data files (e.g., data/recordings)")
        src_layout.addWidget(self.src_input)
        self.src_browse_btn = QPushButton("Browse...")
        self.src_browse_btn.clicked.connect(self._browse_src)
        src_layout.addWidget(self.src_browse_btn)
        folder_layout.addRow("Source Folder:", src_layout)

        # Destination folder
        dst_layout = QHBoxLayout()
        self.dst_input = QLineEdit()
        self.dst_input.setPlaceholderText("Path to notes/metadata (e.g., notes/surgery)")
        dst_layout.addWidget(self.dst_input)
        self.dst_browse_btn = QPushButton("Browse...")
        self.dst_browse_btn.clicked.connect(self._browse_dst)
        dst_layout.addWidget(self.dst_browse_btn)
        folder_layout.addRow("Target Folder:", dst_layout)

        # Relationship type
        self.relation_combo = QComboBox()
        for edge_type in EdgeType:
            self.relation_combo.addItem(edge_type.value, edge_type)
        folder_layout.addRow("Relationship:", self.relation_combo)

        # Analyze button
        self.analyze_btn = QPushButton("Analyze Folders")
        self.analyze_btn.setObjectName("primaryButton")
        self.analyze_btn.clicked.connect(self._on_analyze)
        folder_layout.addRow("", self.analyze_btn)

        layout.addWidget(folder_group)

        # Step 2: Analysis Results
        analysis_group = QGroupBox("Step 2: Analysis Results")
        analysis_layout = QVBoxLayout(analysis_group)

        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setMaximumHeight(150)
        self.analysis_text.setPlaceholderText("Analysis results will appear here...")
        analysis_layout.addWidget(self.analysis_text)

        # Generate strategy button
        gen_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Strategy with LLM")
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self._on_generate_strategy)
        gen_layout.addWidget(self.generate_btn)

        self.generate_rule_btn = QPushButton("Generate Rule-Based")
        self.generate_rule_btn.setEnabled(False)
        self.generate_rule_btn.setToolTip("Create strategy without LLM")
        self.generate_rule_btn.clicked.connect(self._on_generate_rule_based)
        gen_layout.addWidget(self.generate_rule_btn)

        gen_layout.addStretch()
        analysis_layout.addLayout(gen_layout)

        layout.addWidget(analysis_group)

        # Step 3: Strategy Editor
        strategy_group = QGroupBox("Step 3: Review & Edit Strategy")
        strategy_layout = QFormLayout(strategy_group)

        # Strategy name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Surgery Notes v1")
        strategy_layout.addRow("Strategy Name:", self.name_input)

        # Description
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Brief description of what this strategy links")
        strategy_layout.addRow("Description:", self.description_input)

        # JSON editor
        json_label = QLabel("Strategy JSON (editable):")
        strategy_layout.addRow(json_label)

        self.json_editor = QTextEdit()
        self.json_editor.setFont(QFont("Consolas", 10))
        self.json_editor.setMinimumHeight(150)
        self.json_editor.setPlaceholderText('{"column_mappings": {}, "token_patterns": {}, "thresholds": {}}')
        strategy_layout.addRow(self.json_editor)

        # Test button
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test on Sample (20 files)")
        self.test_btn.setEnabled(False)
        self.test_btn.clicked.connect(self._on_test_strategy)
        test_layout.addWidget(self.test_btn)

        self.test_count_spin = QSpinBox()
        self.test_count_spin.setRange(5, 100)
        self.test_count_spin.setValue(20)
        self.test_count_spin.setPrefix("Test ")
        self.test_count_spin.setSuffix(" files")
        test_layout.addWidget(self.test_count_spin)

        test_layout.addStretch()
        strategy_layout.addRow(test_layout)

        # Test results
        self.test_results = QTextEdit()
        self.test_results.setReadOnly(True)
        self.test_results.setMaximumHeight(100)
        self.test_results.setPlaceholderText("Test results will appear here...")
        strategy_layout.addRow("Test Results:", self.test_results)

        layout.addWidget(strategy_group)

        # Dialog buttons
        self.button_box = QDialogButtonBox()
        self.save_btn = QPushButton("Save Strategy")
        self.save_btn.setObjectName("successButton")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        self.button_box.addButton(self.save_btn, QDialogButtonBox.ButtonRole.AcceptRole)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.button_box.addButton(self.cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(self.button_box)

    def _populate_roots(self):
        """Populate roots dropdown."""
        self.root_combo.clear()
        roots = self.db.list_roots()
        for root in roots:
            self.root_combo.addItem(f"{root.label} ({root.root_path})", root.root_id)

    def _browse_src(self):
        """Browse for source folder."""
        if self.root_combo.currentIndex() < 0:
            return

        root_id = self.root_combo.currentData()
        root = self.db.get_root(root_id)
        if not root:
            return

        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder",
            root.root_path,
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            # Make relative to root
            try:
                rel_path = Path(folder).relative_to(root.root_path)
                self.src_input.setText(str(rel_path))
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Folder",
                    "Selected folder must be inside the root folder."
                )

    def _browse_dst(self):
        """Browse for destination folder."""
        if self.root_combo.currentIndex() < 0:
            return

        root_id = self.root_combo.currentData()
        root = self.db.get_root(root_id)
        if not root:
            return

        folder = QFileDialog.getExistingDirectory(
            self, "Select Target Folder",
            root.root_path,
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            try:
                rel_path = Path(folder).relative_to(root.root_path)
                self.dst_input.setText(str(rel_path))
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Folder",
                    "Selected folder must be inside the root folder."
                )

    def _on_analyze(self):
        """Analyze selected folders."""
        if self.root_combo.currentIndex() < 0:
            QMessageBox.warning(self, "No Root", "Please select a root folder.")
            return

        src_folder = self.src_input.text().strip()
        dst_folder = self.dst_input.text().strip()

        if not src_folder or not dst_folder:
            QMessageBox.warning(self, "Missing Folders", "Please specify both source and target folders.")
            return

        root_id = self.root_combo.currentData()

        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")

        # Run analysis in background
        self._analyze_thread = AnalyzeThread(
            self.trainer, root_id, src_folder, dst_folder
        )
        self._analyze_thread.finished.connect(self._on_analysis_complete)
        self._analyze_thread.error.connect(self._on_analysis_error)
        self._analyze_thread.start()

    def _on_analysis_complete(self, src_analysis, dst_analysis):
        """Handle analysis completion."""
        self._src_analysis = src_analysis
        self._dst_analysis = dst_analysis

        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Folders")
        self.generate_btn.setEnabled(True)
        self.generate_rule_btn.setEnabled(True)

        # Display results
        html = "<h4>Source Folder Analysis</h4>"
        html += f"<p><b>Files:</b> {src_analysis.file_count} | <b>Directories:</b> {src_analysis.dir_count}</p>"
        html += f"<p><b>Extensions:</b> {', '.join(f'{k}: {v}' for k, v in list(src_analysis.file_extensions.items())[:5])}</p>"
        if src_analysis.filename_patterns:
            html += f"<p><b>Patterns:</b> {', '.join(src_analysis.filename_patterns)}</p>"

        html += "<h4>Target Folder Analysis</h4>"
        html += f"<p><b>Files:</b> {dst_analysis.file_count} | <b>Directories:</b> {dst_analysis.dir_count}</p>"
        html += f"<p><b>Extensions:</b> {', '.join(f'{k}: {v}' for k, v in list(dst_analysis.file_extensions.items())[:5])}</p>"
        if dst_analysis.column_headers:
            html += f"<p><b>Column Headers:</b> {', '.join(dst_analysis.column_headers[:10])}</p>"

        self.analysis_text.setHtml(html)

    def _on_analysis_error(self, error: str):
        """Handle analysis error."""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Folders")
        QMessageBox.warning(self, "Analysis Error", f"Failed to analyze folders:\n{error}")

    def _on_generate_strategy(self):
        """Generate strategy with LLM."""
        if not self._src_analysis or not self._dst_analysis:
            QMessageBox.warning(self, "No Analysis", "Please analyze folders first.")
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")

        try:
            # Get LLM from factory
            from labindex_core.adapters.llm_factory import create_llm, get_available_providers

            providers = get_available_providers()
            available = [p for p in providers if p["available"]]

            if not available:
                QMessageBox.warning(
                    self, "No LLM Available",
                    "No LLM provider is available. Using rule-based generation instead."
                )
                self._on_generate_rule_based()
                return

            llm = create_llm(available[0]["provider"])
            self.trainer._llm = llm

            relation_type = self.relation_combo.currentData()
            strategy = self.trainer.propose_strategy(
                self._src_analysis, self._dst_analysis, relation_type
            )

            self._proposed_strategy = strategy
            self._populate_strategy_fields(strategy)

        except Exception as e:
            QMessageBox.warning(self, "Generation Error", f"Failed to generate strategy:\n{e}")

        finally:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate Strategy with LLM")

    def _on_generate_rule_based(self):
        """Generate strategy without LLM."""
        if not self._src_analysis or not self._dst_analysis:
            QMessageBox.warning(self, "No Analysis", "Please analyze folders first.")
            return

        relation_type = self.relation_combo.currentData()
        strategy = self.trainer._propose_rule_based_strategy(
            self._src_analysis, self._dst_analysis, relation_type
        )

        self._proposed_strategy = strategy
        self._populate_strategy_fields(strategy)

    def _populate_strategy_fields(self, strategy):
        """Populate form fields from strategy."""
        self.name_input.setText(strategy.name)
        self.description_input.setText(strategy.description or "")

        # Format JSON nicely
        config_json = json.dumps(strategy.strategy_config, indent=2)
        self.json_editor.setPlainText(config_json)

        self.test_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def _on_test_strategy(self):
        """Test the strategy on sample files."""
        if not self._proposed_strategy:
            return

        # Update strategy from form
        self._update_strategy_from_form()

        root_id = self.root_combo.currentData()
        test_count = self.test_count_spin.value()

        try:
            evaluation = self.trainer.evaluate_strategy(
                self._proposed_strategy, root_id, test_count
            )

            # Display results
            html = f"<h4>Test Results</h4>"
            html += f"<p><b>Files tested:</b> {evaluation.files_tested}</p>"
            html += f"<p><b>Candidates generated:</b> {evaluation.candidates_generated}</p>"
            html += f"<p><b>High confidence (≥{self._proposed_strategy.thresholds.get('promote', 0.8):.0%}):</b> {evaluation.high_confidence_count}</p>"
            html += f"<p><b>Medium confidence:</b> {evaluation.medium_confidence_count}</p>"
            html += f"<p><b>Low confidence:</b> {evaluation.low_confidence_count}</p>"

            if evaluation.potential_issues:
                html += "<h4>Potential Issues</h4><ul>"
                for issue in evaluation.potential_issues:
                    html += f"<li style='color: #ff6b6b;'>{issue}</li>"
                html += "</ul>"

            if evaluation.sample_matches:
                html += "<h4>Sample Matches</h4><ul>"
                for match in evaluation.sample_matches[:5]:
                    html += f"<li>{match['src']} → {match['dst']}: {match['score']:.0%}</li>"
                html += "</ul>"

            self.test_results.setHtml(html)

        except Exception as e:
            self.test_results.setPlainText(f"Error testing strategy: {e}")

    def _update_strategy_from_form(self):
        """Update proposed strategy from form values."""
        if not self._proposed_strategy:
            return

        self._proposed_strategy.name = self.name_input.text().strip() or "Untitled"
        self._proposed_strategy.description = self.description_input.text().strip()

        try:
            config = json.loads(self.json_editor.toPlainText())
            self._proposed_strategy.strategy_config = config
        except json.JSONDecodeError:
            pass  # Keep existing config

    def _on_save(self):
        """Save the strategy."""
        if not self._proposed_strategy:
            return

        self._update_strategy_from_form()

        if not self._proposed_strategy.name:
            QMessageBox.warning(self, "Missing Name", "Please enter a strategy name.")
            return

        try:
            # Check version
            existing = self.db.list_linker_strategies(self._proposed_strategy.name)
            if existing:
                max_version = max(s.version for s in existing)
                self._proposed_strategy.version = max_version + 1

            # Save
            saved = self.trainer.save_strategy(self._proposed_strategy, activate=True)

            QMessageBox.information(
                self, "Strategy Saved",
                f"Strategy '{saved.name}' v{saved.version} saved and activated."
            )

            self.accept()

        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save strategy:\n{e}")
