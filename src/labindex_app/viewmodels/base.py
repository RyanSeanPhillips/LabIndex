"""
Base ViewModel class for LabIndex MVVM architecture.

Provides the foundation for all ViewModels with:
- PyQt6 signal support for UI binding
- Property change notification pattern
- Service injection support
"""

from typing import Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal


class BaseViewModel(QObject):
    """
    Base class for all ViewModels.

    Pattern:
    - Properties with signals on change
    - Commands as methods
    - No widget references (UI-agnostic)
    - Services injected via constructor

    Example:
        class MyViewModel(BaseViewModel):
            value_changed = pyqtSignal(int)

            def __init__(self, service):
                super().__init__()
                self._service = service
                self._value = 0

            @property
            def value(self) -> int:
                return self._value

            def set_value(self, v: int) -> None:
                if self._value != v:
                    self._value = v
                    self.value_changed.emit(v)
    """

    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize the ViewModel.

        Args:
            parent: Optional parent QObject for Qt memory management
        """
        super().__init__(parent)

    def _notify_change(self, signal: pyqtSignal, *args: Any) -> None:
        """
        Helper to emit a signal only if connected.

        Args:
            signal: The signal to emit
            *args: Arguments to pass to the signal
        """
        signal.emit(*args)
