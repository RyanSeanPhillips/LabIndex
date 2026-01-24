"""
Ports (interfaces) for LabIndex.

These define the contracts that adapters must implement.
This enables dependency injection and testing with mocks.
"""

from .fs_port import FSPort
from .db_port import DBPort

__all__ = ["FSPort", "DBPort"]
