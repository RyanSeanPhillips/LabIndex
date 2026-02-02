"""
Graph filter dialog for selecting file types to display.
"""

from typing import Set
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QGroupBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal


class GraphFilterDialog(QDialog):
    """Dialog for configuring graph file type filter."""

    filter_changed = pyqtSignal(set, float, bool)  # categories, opacity, hide_mode

    CATEGORIES = [
        ("presentations", "Presentations (PPTX, ODP)"),
        ("data", "Data Files (ABF, SMRX, CSV, MAT...)"),
        ("documents", "Documents (DOCX, PDF, TXT...)"),
        ("spreadsheets", "Spreadsheets (XLSX, XLS)"),
        ("code", "Code (PY, IPYNB, M, JS...)"),
        ("images", "Images (PNG, JPG, TIFF...)"),
        ("video", "Video (MP4, AVI, MOV...)"),
        ("archives", "Archives (ZIP, TAR, 7Z...)"),
    ]

    def __init__(self, parent=None, current_categories: Set[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Filter by File Type")
        self.setMinimumWidth(350)

        self._current_categories = current_categories or set()
        self._checkboxes: dict = {}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # File type checkboxes
        type_group = QGroupBox("Show File Types")
        type_layout = QVBoxLayout(type_group)

        for cat_id, cat_label in self.CATEGORIES:
            cb = QCheckBox(cat_label)
            cb.setChecked(cat_id in self._current_categories or not self._current_categories)
            cb.stateChanged.connect(self._on_checkbox_changed)
            self._checkboxes[cat_id] = cb
            type_layout.addWidget(cb)

        layout.addWidget(type_group)

        # Select All / Clear buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)

        # Fade opacity slider
        opacity_group = QGroupBox("Non-Matching Items")
        opacity_layout = QVBoxLayout(opacity_group)

        self._fade_radio = QRadioButton("Fade to:")
        self._hide_radio = QRadioButton("Hide completely")
        self._fade_radio.setChecked(True)

        opacity_layout.addWidget(self._fade_radio)

        slider_layout = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(5, 50)
        self._opacity_slider.setValue(20)
        self._opacity_label = QLabel("20%")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        slider_layout.addWidget(self._opacity_slider)
        slider_layout.addWidget(self._opacity_label)
        opacity_layout.addLayout(slider_layout)

        opacity_layout.addWidget(self._hide_radio)
        layout.addWidget(opacity_group)

        # Dialog buttons
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _on_checkbox_changed(self):
        pass  # Could emit live updates

    def _select_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _clear_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def _apply(self):
        # Collect selected categories
        selected = set()
        all_checked = True
        for cat_id, cb in self._checkboxes.items():
            if cb.isChecked():
                selected.add(cat_id)
            else:
                all_checked = False

        # If all checked, treat as "no filter"
        if all_checked:
            selected = set()

        opacity = self._opacity_slider.value() / 100.0
        hide_mode = self._hide_radio.isChecked()

        self.filter_changed.emit(selected, opacity, hide_mode)
