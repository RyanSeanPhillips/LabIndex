"""
Chat Tab - Primary interface for LabIndex.

Features:
- Folder drag & drop to index
- Conversational LLM interaction
- Message history with timestamps
- Provider selection (Ollama, etc.)
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QPushButton, QLineEdit, QFrame, QComboBox,
    QSizePolicy, QPlainTextEdit, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QPalette, QColor


class MessageBubble(QFrame):
    """A single chat message bubble."""

    def __init__(
        self,
        sender: str,
        content: str,
        timestamp: str,
        is_user: bool = False,
        is_system: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setObjectName("messageBubble")

        # Different styling for user vs assistant vs system
        if is_user:
            bg_color = "#1e3a5f"  # Dark blue for user
            border_color = "#4fc3f7"
        elif is_system:
            bg_color = "#2d2d2d"  # Gray for system
            border_color = "#666666"
        else:
            bg_color = "#1e3d1e"  # Dark green for assistant
            border_color = "#81c784"

        self.setStyleSheet(f"""
            QFrame#messageBubble {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 8px;
                margin: 4px 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header with sender and timestamp
        header = QHBoxLayout()
        sender_label = QLabel(sender)
        sender_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        sender_label.setStyleSheet(f"color: {border_color};")
        header.addWidget(sender_label)

        header.addStretch()

        time_label = QLabel(timestamp)
        time_label.setFont(QFont("Segoe UI", 8))
        time_label.setStyleSheet("color: #888888;")
        header.addWidget(time_label)

        layout.addLayout(header)

        # Content - use QTextEdit for better text selection
        from PyQt6.QtWidgets import QTextEdit
        content_edit = QTextEdit()
        content_edit.setPlainText(content)
        content_edit.setReadOnly(True)
        content_edit.setFrameStyle(QFrame.Shape.NoFrame)
        content_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                padding: 4px 0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
        """)
        # Auto-size to content
        content_edit.document().setDocumentMargin(0)
        content_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Calculate height based on content
        doc_height = content_edit.document().size().height()
        content_edit.setMinimumHeight(int(doc_height) + 10)
        content_edit.setMaximumHeight(int(doc_height) + 10)

        layout.addWidget(content_edit)
        self._content_edit = content_edit


class DropZoneWidget(QFrame):
    """A drop zone that accepts folder drops."""

    folder_dropped = pyqtSignal(str)  # Emitted with folder path

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setMinimumHeight(60)
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        self._is_drag_over = False
        self._update_style()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel("Drop a folder here to index it")
        self.label.setFont(QFont("Segoe UI", 10))
        self.label.setStyleSheet("color: #888888;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.sublabel = QLabel("or paste a path below")
        self.sublabel.setFont(QFont("Segoe UI", 8))
        self.sublabel.setStyleSheet("color: #666666;")
        self.sublabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sublabel)

    def _update_style(self):
        if self._is_drag_over:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e3a5f;
                    border: 2px dashed #4fc3f7;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #252525;
                    border: 2px dashed #444444;
                    border-radius: 8px;
                }
            """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # Check if it's a folder
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    event.acceptProposedAction()
                    self._is_drag_over = True
                    self._update_style()
                    self.label.setText("Drop to index this folder")
                    self.label.setStyleSheet("color: #4fc3f7;")
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._is_drag_over = False
        self._update_style()
        self.label.setText("Drop a folder here to index it")
        self.label.setStyleSheet("color: #888888;")

    def dropEvent(self, event: QDropEvent):
        self._is_drag_over = False
        self._update_style()
        self.label.setText("Drop a folder here to index it")
        self.label.setStyleSheet("color: #888888;")

        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.folder_dropped.emit(path)
                event.acceptProposedAction()
                return

        event.ignore()


class ChatTab(QWidget):
    """
    Chat tab widget with folder drop support.

    Provides a conversational interface for interacting with LabIndex.
    """

    # Signals for coordination
    folder_index_requested = pyqtSignal(str)  # Folder path to index
    file_selected = pyqtSignal(int)  # File ID to show in inspector

    def __init__(self, agent_vm, index_vm=None, parent: Optional[QWidget] = None):
        """
        Initialize the chat tab.

        Args:
            agent_vm: AgentVM for chat functionality
            index_vm: IndexStatusVM for indexing (optional)
            parent: Parent widget
        """
        super().__init__(parent)

        self._agent_vm = agent_vm
        self._index_vm = index_vm

        self._setup_ui()
        self._bind_viewmodel()

        # Add welcome message
        self._add_welcome_message()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with title and provider selector
        header = QHBoxLayout()

        title = QLabel("LabIndex Assistant")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #4fc3f7;")
        header.addWidget(title)

        header.addStretch()

        # Provider selector
        provider_label = QLabel("LLM:")
        provider_label.setStyleSheet("color: #888888;")
        header.addWidget(provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(150)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        header.addWidget(self.provider_combo)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #81c784; font-size: 10px;")
        self.status_label.setMinimumWidth(100)
        header.addWidget(self.status_label)

        layout.addLayout(header)

        # Drop zone for folders
        self.drop_zone = DropZoneWidget()
        self.drop_zone.folder_dropped.connect(self._on_folder_dropped)
        layout.addWidget(self.drop_zone)

        # Chat messages area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
            }
        """)

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(8, 8, 8, 8)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()  # Push messages to top

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)

        self.input_box = QPlainTextEdit()
        self.input_box.setPlaceholderText(
            "Type a message, paste a folder path, or ask about your files..."
        )
        self.input_box.setMaximumHeight(80)
        self.input_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        input_layout.addWidget(self.input_box, stretch=1)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primaryButton")
        self.send_button.setMinimumHeight(40)
        self.send_button.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.send_button)

        layout.addWidget(input_frame)

        # Keyboard shortcut hint
        hint = QLabel("Press Ctrl+Enter to send")
        hint.setStyleSheet("color: #666666; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(hint)

        # Install event filter for Ctrl+Enter
        self.input_box.installEventFilter(self)

    def _bind_viewmodel(self):
        """Bind to ViewModel signals."""
        # Agent VM bindings
        self._agent_vm.message_added.connect(self._on_message_added)
        self._agent_vm.thinking_changed.connect(self._on_thinking_changed)
        self._agent_vm.status_changed.connect(self._on_status_changed)
        self._agent_vm.providers_changed.connect(self._populate_providers)

        # Index VM bindings (if available)
        if self._index_vm:
            self._index_vm.progress_changed.connect(self._on_index_progress)
            self._index_vm.operation_finished.connect(self._on_index_finished)

        # Initial population
        self._populate_providers()

    def _populate_providers(self):
        """Populate the provider dropdown."""
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()

        for p in self._agent_vm.available_providers:
            icon = "+" if p.available else "x"
            self.provider_combo.addItem(f"{icon} {p.name}")

        if self._agent_vm.selected_provider_index >= 0:
            self.provider_combo.setCurrentIndex(self._agent_vm.selected_provider_index)

        self.provider_combo.blockSignals(False)
        self.status_label.setText(self._agent_vm.provider_status)

    def _add_welcome_message(self):
        """Add the initial welcome message."""
        welcome_text = (
            "Hi! I'm LabIndex, your research file assistant.\n\n"
            "To get started:\n"
            "- Drag a folder above to index it\n"
            "- Or type/paste a folder path\n"
            "- Then tell me about how your files are organized\n\n"
            "I can help you find files, discover patterns, and link related data."
        )
        bubble = MessageBubble(
            sender="Assistant",
            content=welcome_text,
            timestamp=datetime.now().strftime("%H:%M"),
            is_user=False,
        )
        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1, bubble
        )

    def _add_message(
        self,
        sender: str,
        content: str,
        is_user: bool = False,
        is_system: bool = False
    ):
        """Add a message bubble to the chat."""
        bubble = MessageBubble(
            sender=sender,
            content=content,
            timestamp=datetime.now().strftime("%H:%M"),
            is_user=is_user,
            is_system=is_system,
        )
        # Insert before the stretch at the end
        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1, bubble
        )

        # Scroll to bottom
        QApplication.processEvents()
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_folder_dropped(self, folder_path: str):
        """Handle folder drop."""
        self._add_message(
            "You",
            f"Index folder: {folder_path}",
            is_user=True
        )
        self._start_indexing(folder_path)

    def _on_send_clicked(self):
        """Handle send button click."""
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        self.input_box.clear()

        # Check if it's a folder path
        if os.path.isdir(text):
            self._add_message("You", f"Index folder: {text}", is_user=True)
            self._start_indexing(text)
        else:
            # Regular chat message
            self._agent_vm.send_message(text)

    def _start_indexing(self, folder_path: str):
        """Start indexing a folder."""
        if self._index_vm:
            # Normalize path for comparison
            normalized_path = str(Path(folder_path).resolve())
            label = Path(folder_path).name

            # Check if root already exists
            existing_root = None
            for root in self._index_vm.roots:
                if str(Path(root.root_path).resolve()) == normalized_path:
                    existing_root = root
                    break

            if existing_root:
                # Root already exists - refresh it
                self._add_message(
                    "System",
                    f"'{existing_root.label}' is already indexed. Refreshing...",
                    is_system=True
                )
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self._index_vm.select_root(existing_root.root_id)
                self._index_vm.start_crawl(existing_root.root_id)
            else:
                # Add new root and start crawl
                try:
                    root = self._index_vm.add_root(folder_path)
                    self._add_message(
                        "System",
                        f"Starting to index '{label}'...",
                        is_system=True
                    )
                    self.progress_bar.setVisible(True)
                    self.progress_bar.setValue(0)
                    self._index_vm.select_root(root.root_id)
                    self._index_vm.start_crawl(root.root_id)
                except Exception as e:
                    self._add_message(
                        "Error",
                        f"Failed to index folder: {e}",
                        is_system=True
                    )
        else:
            # Just notify via signal
            self.folder_index_requested.emit(folder_path)
            self._add_message(
                "System",
                f"Indexing requested for: {folder_path}",
                is_system=True
            )

    def _on_message_added(self, msg):
        """Handle new message from AgentVM."""
        is_user = msg.sender == "You"
        is_system = msg.sender in ("Tools", "Error", "System")

        self._add_message(
            sender=msg.sender,
            content=msg.content,
            is_user=is_user,
            is_system=is_system,
        )

    def _on_thinking_changed(self, thinking: bool):
        """Handle thinking state change."""
        self.input_box.setEnabled(not thinking)
        self.send_button.setEnabled(not thinking)
        self.send_button.setText("Thinking..." if thinking else "Send")

    def _on_status_changed(self, status: str):
        """Handle status change."""
        self.status_label.setText(status)

    def _on_provider_changed(self, index: int):
        """Handle provider selection change."""
        self._agent_vm.select_provider(index)

    def _on_index_progress(self, percent: int, message: str):
        """Handle indexing progress update."""
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{message} ({percent}%)")

    def _on_index_finished(self, success: bool, message: str):
        """Handle indexing completion."""
        self.progress_bar.setVisible(False)

        if success:
            # Get stats and report
            if self._index_vm:
                stats = self._index_vm.stats
                summary = (
                    f"Indexing complete!\n\n"
                    f"Found {stats.file_count:,} files in {stats.roots_count} root(s).\n"
                    f"Extracted content from {stats.indexed_count:,} files.\n\n"
                    f"Now tell me about your files - what are your data files? "
                    f"What are your notes files? I'll help you link them together."
                )
            else:
                summary = f"Indexing complete: {message}"

            self._add_message("Assistant", summary)
        else:
            self._add_message("Error", f"Indexing failed: {message}", is_system=True)

    def eventFilter(self, obj, event):
        """Handle Ctrl+Enter to send."""
        from PyQt6.QtCore import QEvent

        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_Return and
                event.modifiers() == Qt.KeyboardModifier.ControlModifier):
                self._on_send_clicked()
                return True
        return super().eventFilter(obj, event)
