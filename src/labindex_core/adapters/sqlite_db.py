"""
SQLite Database Adapter.

Implements the database port with SQLite + FTS5 for fast search.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ..ports.db_port import DBPort
from ..domain.models import (
    FileRecord, ContentRecord, Edge, IndexRoot, CrawlJob, SearchResult
)
from ..domain.enums import FileCategory, IndexStatus, EdgeType, JobStatus


# SQL Schema
SCHEMA_SQL = """
-- Enable WAL mode for better concurrency
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Indexed roots (folders added for indexing)
CREATE TABLE IF NOT EXISTS roots (
    root_id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    scan_config_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_scan_at TEXT
);

-- File inventory
CREATE TABLE IF NOT EXISTS files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_id INTEGER NOT NULL REFERENCES roots(root_id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    parent_path TEXT NOT NULL,
    name TEXT NOT NULL,
    ext TEXT NOT NULL,
    is_dir INTEGER NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mtime TEXT NOT NULL,
    ctime TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    status TEXT NOT NULL DEFAULT 'pending',
    error_msg TEXT,
    last_indexed_at TEXT,
    UNIQUE(root_id, path)
);

CREATE INDEX IF NOT EXISTS idx_files_root_parent ON files(root_id, parent_path);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);
CREATE INDEX IF NOT EXISTS idx_files_ext ON files(ext);
CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);

-- Extracted content
CREATE TABLE IF NOT EXISTS content (
    file_id INTEGER PRIMARY KEY REFERENCES files(file_id) ON DELETE CASCADE,
    title TEXT,
    summary TEXT,
    keywords_json TEXT DEFAULT '[]',
    entities_json TEXT DEFAULT '{}',
    content_excerpt TEXT,
    full_text TEXT,
    extraction_version TEXT DEFAULT '1.0',
    extracted_at TEXT NOT NULL
);

-- Relationship edges
CREATE TABLE IF NOT EXISTS edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_file_id INTEGER NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    dst_file_id INTEGER NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    evidence TEXT,
    evidence_file_id INTEGER REFERENCES files(file_id),
    created_by TEXT NOT NULL DEFAULT 'rule',
    created_at TEXT NOT NULL,
    UNIQUE(src_file_id, dst_file_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_file_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_file_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(relation_type);

-- Job queue for background processing
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    root_id INTEGER REFERENCES roots(root_id) ON DELETE CASCADE,
    dir_path TEXT,
    payload_json TEXT DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    locked_by TEXT,
    locked_at TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, priority DESC);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(
    file_id UNINDEXED,
    path,
    name,
    title,
    summary,
    keywords,
    entities,
    excerpt,
    full_text,
    content='',
    tokenize='porter unicode61'
);
"""


class SqliteDB(DBPort):
    """SQLite implementation of the database port."""

    def __init__(self, db_path: Path):
        """
        Initialize the SQLite database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None  # Autocommit mode
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self._conn.executescript(SCHEMA_SQL)
        self._run_migrations()

    def _run_migrations(self):
        """Run any necessary schema migrations."""
        # Check if full_text column exists in content table
        cursor = self._conn.execute("PRAGMA table_info(content)")
        columns = {row[1] for row in cursor.fetchall()}

        if 'full_text' not in columns:
            try:
                self._conn.execute("ALTER TABLE content ADD COLUMN full_text TEXT")
            except Exception:
                pass  # Column might already exist

        # Rebuild FTS table if needed (to add full_text column)
        # Note: This is destructive - only do on first migration
        cursor = self._conn.execute("PRAGMA table_info(fts_docs)")
        fts_columns = {row[1] for row in cursor.fetchall()}
        if 'full_text' not in fts_columns:
            try:
                self._conn.execute("DROP TABLE IF EXISTS fts_docs")
                self._conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(
                        file_id UNINDEXED,
                        path,
                        name,
                        title,
                        summary,
                        keywords,
                        entities,
                        excerpt,
                        full_text,
                        content='',
                        tokenize='porter unicode61'
                    )
                """)
            except Exception:
                pass

    @contextmanager
    def _transaction(self):
        """Context manager for transactions."""
        self._conn.execute("BEGIN")
        try:
            yield
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def _now(self) -> str:
        """Get current timestamp as ISO string."""
        return datetime.now().isoformat()

    # === Root Management ===

    def add_root(self, path: str, label: str, config: Dict[str, Any] = None) -> IndexRoot:
        cursor = self._conn.execute(
            """INSERT INTO roots (root_path, label, scan_config_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (path, label, json.dumps(config or {}), self._now())
        )
        return IndexRoot(
            root_id=cursor.lastrowid,
            root_path=path,
            label=label,
            scan_config=config or {},
            created_at=datetime.now(),
        )

    def get_root(self, root_id: int) -> Optional[IndexRoot]:
        row = self._conn.execute(
            "SELECT * FROM roots WHERE root_id = ?", (root_id,)
        ).fetchone()
        if row:
            return self._row_to_root(row)
        return None

    def list_roots(self) -> List[IndexRoot]:
        rows = self._conn.execute("SELECT * FROM roots ORDER BY label").fetchall()
        return [self._row_to_root(row) for row in rows]

    def remove_root(self, root_id: int) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM roots WHERE root_id = ?", (root_id,)
        )
        return cursor.rowcount > 0

    def _row_to_root(self, row) -> IndexRoot:
        return IndexRoot(
            root_id=row["root_id"],
            root_path=row["root_path"],
            label=row["label"],
            scan_config=json.loads(row["scan_config_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_scan_at=datetime.fromisoformat(row["last_scan_at"]) if row["last_scan_at"] else None,
        )

    # === File Records ===

    def upsert_file(self, file: FileRecord) -> FileRecord:
        self._conn.execute(
            """INSERT INTO files
               (root_id, path, parent_path, name, ext, is_dir, size_bytes,
                mtime, ctime, category, status, error_msg, last_indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(root_id, path) DO UPDATE SET
                 parent_path=excluded.parent_path,
                 name=excluded.name,
                 ext=excluded.ext,
                 is_dir=excluded.is_dir,
                 size_bytes=excluded.size_bytes,
                 mtime=excluded.mtime,
                 ctime=excluded.ctime,
                 category=excluded.category,
                 status=excluded.status,
                 error_msg=excluded.error_msg,
                 last_indexed_at=excluded.last_indexed_at""",
            (
                file.root_id, file.path, file.parent_path, file.name, file.ext,
                1 if file.is_dir else 0, file.size_bytes,
                file.mtime.isoformat(), file.ctime.isoformat(),
                file.category.value, file.status.value, file.error_msg,
                file.last_indexed_at.isoformat() if file.last_indexed_at else None,
            )
        )

        # Get the file_id (either new or existing)
        row = self._conn.execute(
            "SELECT file_id FROM files WHERE root_id = ? AND path = ?",
            (file.root_id, file.path)
        ).fetchone()
        file.file_id = row["file_id"]
        return file

    def get_file(self, file_id: int) -> Optional[FileRecord]:
        row = self._conn.execute(
            "SELECT * FROM files WHERE file_id = ?", (file_id,)
        ).fetchone()
        if row:
            return self._row_to_file(row)
        return None

    def get_file_by_path(self, root_id: int, path: str) -> Optional[FileRecord]:
        row = self._conn.execute(
            "SELECT * FROM files WHERE root_id = ? AND path = ?",
            (root_id, path)
        ).fetchone()
        if row:
            return self._row_to_file(row)
        return None

    def list_files(self, root_id: int, parent_path: Optional[str] = None,
                   category: Optional[str] = None, limit: int = 1000) -> List[FileRecord]:
        sql = "SELECT * FROM files WHERE root_id = ?"
        params = [root_id]

        if parent_path is not None:
            sql += " AND parent_path = ?"
            params.append(parent_path)

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY name LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_file(row) for row in rows]

    def update_file_status(self, file_id: int, status: IndexStatus,
                          error_msg: Optional[str] = None) -> bool:
        cursor = self._conn.execute(
            """UPDATE files SET status = ?, error_msg = ?, last_indexed_at = ?
               WHERE file_id = ?""",
            (status.value, error_msg, self._now(), file_id)
        )
        return cursor.rowcount > 0

    def _row_to_file(self, row) -> FileRecord:
        return FileRecord(
            file_id=row["file_id"],
            root_id=row["root_id"],
            path=row["path"],
            parent_path=row["parent_path"],
            name=row["name"],
            ext=row["ext"],
            is_dir=bool(row["is_dir"]),
            size_bytes=row["size_bytes"],
            mtime=datetime.fromisoformat(row["mtime"]),
            ctime=datetime.fromisoformat(row["ctime"]),
            category=FileCategory(row["category"]),
            status=IndexStatus(row["status"]),
            error_msg=row["error_msg"],
            last_indexed_at=datetime.fromisoformat(row["last_indexed_at"]) if row["last_indexed_at"] else None,
        )

    # === Content Records ===

    def upsert_content(self, content: ContentRecord) -> ContentRecord:
        self._conn.execute(
            """INSERT INTO content
               (file_id, title, summary, keywords_json, entities_json,
                content_excerpt, full_text, extraction_version, extracted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(file_id) DO UPDATE SET
                 title=excluded.title,
                 summary=excluded.summary,
                 keywords_json=excluded.keywords_json,
                 entities_json=excluded.entities_json,
                 content_excerpt=excluded.content_excerpt,
                 full_text=excluded.full_text,
                 extraction_version=excluded.extraction_version,
                 extracted_at=excluded.extracted_at""",
            (
                content.file_id, content.title, content.summary,
                json.dumps(content.keywords), json.dumps(content.entities),
                content.content_excerpt, content.full_text, content.extraction_version,
                content.extracted_at.isoformat(),
            )
        )

        # Update FTS index
        file = self.get_file(content.file_id)
        if file:
            self._update_fts(content, file)

        return content

    def _update_fts(self, content: ContentRecord, file: FileRecord):
        """Update the FTS index for a file."""
        # Delete existing entry
        self._conn.execute(
            "DELETE FROM fts_docs WHERE file_id = ?", (content.file_id,)
        )

        # Insert new entry
        self._conn.execute(
            """INSERT INTO fts_docs
               (file_id, path, name, title, summary, keywords, entities, excerpt, full_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                content.file_id, file.path, file.name,
                content.title or "", content.summary or "",
                " ".join(content.keywords),
                " ".join(f"{k}: {', '.join(v)}" for k, v in content.entities.items()),
                content.content_excerpt or "",
                content.full_text or "",
            )
        )

    def get_content(self, file_id: int) -> Optional[ContentRecord]:
        row = self._conn.execute(
            "SELECT * FROM content WHERE file_id = ?", (file_id,)
        ).fetchone()
        if row:
            return ContentRecord(
                file_id=row["file_id"],
                title=row["title"],
                summary=row["summary"],
                keywords=json.loads(row["keywords_json"]),
                entities=json.loads(row["entities_json"]),
                content_excerpt=row["content_excerpt"],
                full_text=row["full_text"] if "full_text" in row.keys() else None,
                extraction_version=row["extraction_version"],
                extracted_at=datetime.fromisoformat(row["extracted_at"]),
            )
        return None

    # === Edges ===

    def add_edge(self, edge: Edge) -> Edge:
        cursor = self._conn.execute(
            """INSERT INTO edges
               (src_file_id, dst_file_id, relation_type, confidence,
                evidence, evidence_file_id, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(src_file_id, dst_file_id, relation_type) DO UPDATE SET
                 confidence=excluded.confidence,
                 evidence=excluded.evidence,
                 evidence_file_id=excluded.evidence_file_id""",
            (
                edge.src_file_id, edge.dst_file_id, edge.relation_type.value,
                edge.confidence, edge.evidence, edge.evidence_file_id,
                edge.created_by, self._now(),
            )
        )
        edge.edge_id = cursor.lastrowid
        return edge

    def get_edges_from(self, file_id: int, relation_type: Optional[str] = None) -> List[Edge]:
        sql = "SELECT * FROM edges WHERE src_file_id = ?"
        params = [file_id]
        if relation_type:
            sql += " AND relation_type = ?"
            params.append(relation_type)

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_edge(row) for row in rows]

    def get_edges_to(self, file_id: int, relation_type: Optional[str] = None) -> List[Edge]:
        sql = "SELECT * FROM edges WHERE dst_file_id = ?"
        params = [file_id]
        if relation_type:
            sql += " AND relation_type = ?"
            params.append(relation_type)

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_edge(row) for row in rows]

    def _row_to_edge(self, row) -> Edge:
        return Edge(
            edge_id=row["edge_id"],
            src_file_id=row["src_file_id"],
            dst_file_id=row["dst_file_id"],
            relation_type=EdgeType(row["relation_type"]),
            confidence=row["confidence"],
            evidence=row["evidence"],
            evidence_file_id=row["evidence_file_id"],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def count_edges(self, root_id: Optional[int] = None) -> int:
        """Count total edges (optionally filtered by root)."""
        if root_id is None:
            sql = "SELECT COUNT(*) FROM edges"
            row = self._conn.execute(sql).fetchone()
        else:
            # Count edges where source file belongs to the root
            sql = """
                SELECT COUNT(*) FROM edges e
                JOIN files f ON e.src_file_id = f.file_id
                WHERE f.root_id = ?
            """
            row = self._conn.execute(sql, [root_id]).fetchone()
        return row[0] if row else 0

    def delete_edge(self, edge_id: int) -> bool:
        """Delete an edge by ID. Returns True if deleted."""
        cursor = self._conn.execute(
            "DELETE FROM edges WHERE edge_id = ?",
            [edge_id]
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # === Search ===

    def search_filename(self, query: str, root_id: Optional[int] = None,
                       limit: int = 100) -> List[SearchResult]:
        sql = "SELECT * FROM files WHERE name LIKE ?"
        params = [f"%{query}%"]

        if root_id:
            sql += " AND root_id = ?"
            params.append(root_id)

        sql += " ORDER BY name LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            file = self._row_to_file(row)
            results.append(SearchResult(
                file_id=file.file_id,
                file_record=file,
                score=1.0,  # Simple LIKE doesn't have scores
                match_type="filename",
            ))
        return results

    def search_fts(self, query: str, root_id: Optional[int] = None,
                  limit: int = 100) -> List[SearchResult]:
        # FTS5 search with BM25 ranking
        sql = """
            SELECT f.*, fts.rank
            FROM fts_docs fts
            JOIN files f ON f.file_id = fts.file_id
            WHERE fts_docs MATCH ?
        """
        params = [query]

        if root_id:
            sql += " AND f.root_id = ?"
            params.append(root_id)

        sql += " ORDER BY fts.rank LIMIT ?"
        params.append(limit)

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS query syntax error - fall back to filename search
            return self.search_filename(query, root_id, limit)

        results = []
        for row in rows:
            file = self._row_to_file(row)
            results.append(SearchResult(
                file_id=file.file_id,
                file_record=file,
                score=-row["rank"],  # BM25 returns negative scores (higher = better match)
                match_type="fts",
            ))
        return results

    # === Jobs ===

    def create_job(self, job: CrawlJob) -> CrawlJob:
        cursor = self._conn.execute(
            """INSERT INTO jobs
               (job_type, root_id, dir_path, payload_json, status, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "crawl_dir", job.root_id, job.dir_path,
                "{}", job.status.value, job.priority, self._now(),
            )
        )
        job.job_id = cursor.lastrowid
        return job

    def claim_job(self, worker_id: str) -> Optional[CrawlJob]:
        # Claim the highest priority pending job
        row = self._conn.execute(
            """UPDATE jobs SET
                 status = 'running', locked_by = ?, locked_at = ?, attempts = attempts + 1
               WHERE job_id = (
                 SELECT job_id FROM jobs
                 WHERE status = 'pending'
                 ORDER BY priority DESC, created_at ASC
                 LIMIT 1
               )
               RETURNING *""",
            (worker_id, self._now())
        ).fetchone()

        if row:
            return CrawlJob(
                job_id=row["job_id"],
                root_id=row["root_id"],
                dir_path=row["dir_path"],
                status=JobStatus.RUNNING,
                priority=row["priority"],
                attempts=row["attempts"],
                locked_by=row["locked_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def complete_job(self, job_id: int, status: JobStatus,
                    error_msg: Optional[str] = None) -> bool:
        cursor = self._conn.execute(
            """UPDATE jobs SET status = ?, completed_at = ?, error_msg = ?, locked_by = NULL
               WHERE job_id = ?""",
            (status.value, self._now(), error_msg, job_id)
        )
        return cursor.rowcount > 0

    def get_job_stats(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    # === Maintenance ===

    def vacuum(self) -> None:
        self._conn.execute("VACUUM")

    def close(self) -> None:
        self._conn.close()

    def get_file_count(self, root_id: Optional[int] = None) -> int:
        """Get total file count."""
        if root_id:
            row = self._conn.execute(
                "SELECT COUNT(*) as count FROM files WHERE root_id = ?", (root_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) as count FROM files").fetchone()
        return row["count"]

    def get_indexed_count(self, root_id: Optional[int] = None) -> int:
        """Get count of files with extracted content."""
        if root_id:
            row = self._conn.execute(
                "SELECT COUNT(*) as count FROM content c JOIN files f ON c.file_id = f.file_id WHERE f.root_id = ?",
                (root_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) as count FROM content").fetchone()
        return row["count"]
