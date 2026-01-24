"""
Safety tests for ReadOnlyFS.

These tests verify that the filesystem adapter is strictly read-only
and cannot perform any destructive operations.
"""

import pytest
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from labindex_core.adapters.readonly_fs import ReadOnlyFS
from labindex_core.ports.fs_port import ReadBudget


class TestReadOnlyFSSafety:
    """Test that ReadOnlyFS cannot perform destructive operations."""

    def test_write_forbidden(self):
        """Verify write() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.write("path", b"data")

    def test_delete_forbidden(self):
        """Verify delete() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.delete("path")

    def test_remove_forbidden(self):
        """Verify remove() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.remove("path")

    def test_unlink_forbidden(self):
        """Verify unlink() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.unlink("path")

    def test_rmdir_forbidden(self):
        """Verify rmdir() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.rmdir("path")

    def test_rename_forbidden(self):
        """Verify rename() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.rename("old", "new")

    def test_move_forbidden(self):
        """Verify move() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.move("src", "dst")

    def test_copy_forbidden(self):
        """Verify copy() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.copy("src", "dst")

    def test_mkdir_forbidden(self):
        """Verify mkdir() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.mkdir("path")

    def test_chmod_forbidden(self):
        """Verify chmod() raises NotImplementedError."""
        fs = ReadOnlyFS()
        with pytest.raises(NotImplementedError, match="forbidden"):
            fs.chmod("path", 0o755)


class TestReadOnlyFSReadOperations:
    """Test that read operations work correctly."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")

            sub_dir = Path(tmpdir) / "subdir"
            sub_dir.mkdir()

            (sub_dir / "nested.txt").write_text("Nested content")

            yield Path(tmpdir)

    def test_exists(self, temp_dir):
        """Test exists() returns True for existing paths."""
        fs = ReadOnlyFS()
        assert fs.exists(temp_dir)
        assert fs.exists(temp_dir / "test.txt")
        assert not fs.exists(temp_dir / "nonexistent.txt")

    def test_is_dir(self, temp_dir):
        """Test is_dir() correctly identifies directories."""
        fs = ReadOnlyFS()
        assert fs.is_dir(temp_dir)
        assert fs.is_dir(temp_dir / "subdir")
        assert not fs.is_dir(temp_dir / "test.txt")

    def test_is_file(self, temp_dir):
        """Test is_file() correctly identifies files."""
        fs = ReadOnlyFS()
        assert fs.is_file(temp_dir / "test.txt")
        assert not fs.is_file(temp_dir)
        assert not fs.is_file(temp_dir / "subdir")

    def test_scandir(self, temp_dir):
        """Test scandir() returns directory entries."""
        fs = ReadOnlyFS()
        entries = list(fs.scandir(temp_dir))

        names = {e.name for e in entries}
        assert "test.txt" in names
        assert "subdir" in names

    def test_read_text(self, temp_dir):
        """Test read_text() returns file contents."""
        fs = ReadOnlyFS()
        content = fs.read_text(temp_dir / "test.txt")
        assert content == "Hello, World!"

    def test_read_bytes(self, temp_dir):
        """Test read_bytes() returns file contents."""
        fs = ReadOnlyFS()
        content = fs.read_bytes(temp_dir / "test.txt")
        assert content == b"Hello, World!"

    def test_read_with_budget(self, temp_dir):
        """Test read operations respect budget limits."""
        fs = ReadOnlyFS()

        # Create a larger file
        large_file = temp_dir / "large.txt"
        large_file.write_text("X" * 10000)

        # Read with small budget
        budget = ReadBudget(max_bytes=100)
        content = fs.read_bytes(large_file, budget)

        assert len(content) <= 100

    def test_stat(self, temp_dir):
        """Test stat() returns file metadata."""
        fs = ReadOnlyFS()
        entry = fs.stat(temp_dir / "test.txt")

        assert entry.name == "test.txt"
        assert entry.size_bytes == 13  # len("Hello, World!")
        assert entry.is_file
        assert not entry.is_dir


class TestReadOnlyFSAllowedRoots:
    """Test path validation with allowed roots."""

    @pytest.fixture
    def temp_dirs(self):
        """Create two temporary directories."""
        with tempfile.TemporaryDirectory() as allowed, \
             tempfile.TemporaryDirectory() as forbidden:

            (Path(allowed) / "allowed.txt").write_text("allowed")
            (Path(forbidden) / "forbidden.txt").write_text("forbidden")

            yield Path(allowed), Path(forbidden)

    def test_allowed_root_access(self, temp_dirs):
        """Test access is allowed within allowed roots."""
        allowed, forbidden = temp_dirs
        fs = ReadOnlyFS(allowed_roots=[allowed])

        # Should work
        assert fs.exists(allowed / "allowed.txt")
        content = fs.read_text(allowed / "allowed.txt")
        assert content == "allowed"

    def test_forbidden_root_blocked(self, temp_dirs):
        """Test access is blocked outside allowed roots."""
        allowed, forbidden = temp_dirs
        fs = ReadOnlyFS(allowed_roots=[allowed])

        # Should raise PermissionError
        with pytest.raises(PermissionError, match="not under any allowed root"):
            fs.exists(forbidden / "forbidden.txt")


class TestReadOnlyFSBlockedExtensions:
    """Test that dangerous file extensions are blocked."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with blocked extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with blocked extensions
            for ext in [".exe", ".bat", ".ps1", ".sh"]:
                (Path(tmpdir) / f"test{ext}").write_bytes(b"blocked content")

            # Create a safe file
            (Path(tmpdir) / "safe.txt").write_text("safe content")

            yield Path(tmpdir)

    def test_blocked_extension_read_fails(self, temp_dir):
        """Test reading files with blocked extensions fails."""
        fs = ReadOnlyFS()

        for ext in [".exe", ".bat", ".ps1", ".sh"]:
            with pytest.raises(PermissionError, match="blocked"):
                fs.read_bytes(temp_dir / f"test{ext}")

    def test_safe_extension_read_works(self, temp_dir):
        """Test reading files with safe extensions works."""
        fs = ReadOnlyFS()
        content = fs.read_text(temp_dir / "safe.txt")
        assert content == "safe content"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
