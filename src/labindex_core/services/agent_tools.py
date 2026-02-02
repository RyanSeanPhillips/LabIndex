"""
Agent Tools - Read-only tools for the LLM agent.

These tools operate on file_id handles, never on raw paths.
All operations are strictly read-only.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..ports.db_port import DBPort
from ..ports.fs_port import FSPort
from ..ports.llm_port import ToolDefinition
from ..domain.enums import EdgeType


@dataclass
class ToolContext:
    """Context passed to all tools."""
    db: DBPort
    fs: FSPort
    root_path: Optional[str] = None  # Current root path for file access


class AgentTools:
    """
    Collection of read-only tools for the LabIndex agent.

    All tools operate on file_id handles and return structured results
    with evidence that can be cited.
    """

    def __init__(self, db: DBPort, fs: FSPort):
        self.db = db
        self.fs = fs
        self._root_path = None

    def set_root_path(self, root_path: str):
        """Set the current root path for file access."""
        self._root_path = root_path

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all available tool definitions for the LLM."""
        return [
            self._def_search_files(),
            self._def_search_content(),
            self._def_get_file_info(),
            self._def_get_related_files(),
            self._def_read_snippet(),
            self._def_list_folder(),
            self._def_find_notes_for_file(),
            # New candidate workflow tools
            self._def_get_candidate_edges(),
            self._def_review_candidate(),
            self._def_get_linking_strategies(),
            self._def_get_candidate_stats(),
            # File exploration workflow tools
            self._def_search_glob(),
            self._def_get_index_summary(),
            self._def_find_parent_files(),
            self._def_label_files(),
            self._def_get_files_by_label(),
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
        tool_map = {
            "search_files": self.search_files,
            "search_content": self.search_content,
            "get_file_info": self.get_file_info,
            "get_related_files": self.get_related_files,
            "read_snippet": self.read_snippet,
            "list_folder": self.list_folder,
            "find_notes_for_file": self.find_notes_for_file,
            # New candidate workflow tools
            "get_candidate_edges": self.get_candidate_edges,
            "review_candidate": self.review_candidate,
            "get_linking_strategies": self.get_linking_strategies,
            "get_candidate_stats": self.get_candidate_stats,
            # File exploration workflow tools
            "search_glob": self.search_glob,
            "get_index_summary": self.get_index_summary,
            "find_parent_files": self.find_parent_files,
            "label_files": self.label_files,
            "get_files_by_label": self.get_files_by_label,
        }

        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool_map[tool_name](**arguments)
        except Exception as e:
            return {"error": str(e)}

    # === Tool Definitions ===

    def _def_search_files(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_files",
            description="Search for files by name pattern. Use this to find files when you know part of the filename.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (filename pattern, e.g., '2024', 'surgery', '.abf')"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by file category (data, documents, spreadsheets, images, code, etc.)",
                        "enum": ["data", "documents", "spreadsheets", "images", "code", "slides", "other"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 20)",
                        "default": 20
                    }
                },
                "required": ["query"]
            },
            handler=self.search_files
        )

    def _def_search_content(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_content",
            description="Full-text search in file contents. Use this to find files containing specific text, keywords, or phrases.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (words or phrases to find in file contents)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 20)",
                        "default": 20
                    }
                },
                "required": ["query"]
            },
            handler=self.search_content
        )

    def _def_get_file_info(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_file_info",
            description="Get detailed information about a specific file by its ID.",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "The file ID to get info for"
                    }
                },
                "required": ["file_id"]
            },
            handler=self.get_file_info
        )

    def _def_get_related_files(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_related_files",
            description="Get files related to a specific file (linked via detected relationships like notes, analysis, same animal, etc.).",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "The file ID to find related files for"
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Filter by relationship type",
                        "enum": ["notes_for", "analysis_of", "same_animal", "same_session", "mentions"]
                    }
                },
                "required": ["file_id"]
            },
            handler=self.get_related_files
        )

    def _def_read_snippet(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_snippet",
            description="Read a text snippet from a file. Use this to examine file contents.",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "The file ID to read from"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to read (default 2000)",
                        "default": 2000
                    }
                },
                "required": ["file_id"]
            },
            handler=self.read_snippet
        )

    def _def_list_folder(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_folder",
            description="List contents of a folder by path.",
            parameters={
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Folder path (relative to index root)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items to return (default 50)",
                        "default": 50
                    }
                },
                "required": ["folder_path"]
            },
            handler=self.list_folder
        )

    def _def_find_notes_for_file(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_notes_for_file",
            description="Find notes, documents, or spreadsheets related to a data file. Useful for finding surgery notes, experiment logs, etc.",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "The data file ID to find notes for"
                    }
                },
                "required": ["file_id"]
            },
            handler=self.find_notes_for_file
        )

    # === Candidate Workflow Tool Definitions ===

    def _def_get_candidate_edges(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_candidate_edges",
            description="Get proposed link candidates awaiting review. Use this to see pending links that need approval.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status",
                        "enum": ["pending", "needs_audit", "accepted", "rejected"],
                        "default": "pending"
                    },
                    "strategy_id": {
                        "type": "integer",
                        "description": "Filter by linking strategy ID (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum candidates to return (default 20)",
                        "default": 20
                    }
                },
                "required": []
            },
            handler=self.get_candidate_edges
        )

    def _def_review_candidate(self) -> ToolDefinition:
        return ToolDefinition(
            name="review_candidate",
            description="Accept or reject a candidate link. Only use when the user explicitly asks to review links.",
            parameters={
                "type": "object",
                "properties": {
                    "candidate_id": {
                        "type": "integer",
                        "description": "The candidate edge ID to review"
                    },
                    "action": {
                        "type": "string",
                        "description": "Review action: 'accept' to promote to confirmed link, 'reject' to discard, 'audit' to flag for LLM review",
                        "enum": ["accept", "reject", "audit"]
                    }
                },
                "required": ["candidate_id", "action"]
            },
            handler=self.review_candidate
        )

    def _def_get_linking_strategies(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_linking_strategies",
            description="List available linking strategies. Strategies define how files are matched and linked.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Filter by strategy name (optional)"
                    },
                    "active_only": {
                        "type": "boolean",
                        "description": "Only return active strategies (default true)",
                        "default": True
                    }
                },
                "required": []
            },
            handler=self.get_linking_strategies
        )

    def _def_get_candidate_stats(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_candidate_stats",
            description="Get statistics about link candidates: counts by status (pending, accepted, rejected, needs_audit).",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self.get_candidate_stats
        )

    # === Tool Implementations ===

    def search_files(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search files by name pattern."""
        from ..services.search import SearchService
        search = SearchService(self.db)

        results = search.search(query, limit=limit)

        # Filter by category if specified
        if category:
            results = [r for r in results if r.file_record.category.value == category]

        return {
            "count": len(results),
            "files": [
                {
                    "file_id": r.file_id,
                    "name": r.name,
                    "path": r.path,
                    "category": r.file_record.category.value,
                    "size_bytes": r.file_record.size_bytes,
                    "score": r.score
                }
                for r in results[:limit]
            ]
        }

    def search_content(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Full-text search in file contents."""
        from ..services.search import SearchService
        search = SearchService(self.db)

        results = search.search_fts(query, limit=limit)

        return {
            "count": len(results),
            "files": [
                {
                    "file_id": r.file_id,
                    "name": r.name,
                    "path": r.path,
                    "category": r.file_record.category.value,
                    "excerpt": r.snippet[:200] if r.snippet else None,
                    "score": r.score
                }
                for r in results
            ]
        }

    def get_file_info(self, file_id: int) -> Dict[str, Any]:
        """Get detailed file information."""
        file = self.db.get_file(file_id)
        if not file:
            return {"error": f"File not found: {file_id}"}

        content = self.db.get_content(file_id)

        return {
            "file_id": file.file_id,
            "name": file.name,
            "path": file.path,
            "category": file.category.value,
            "size_bytes": file.size_bytes,
            "status": file.status.value,
            "has_content": content is not None,
            "content_excerpt": content.content_excerpt if content else None
        }

    def get_related_files(
        self,
        file_id: int,
        relation_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get files related to a given file."""
        edges_from = self.db.get_edges_from(file_id)
        edges_to = self.db.get_edges_to(file_id)

        related = []

        for edge in edges_from:
            if relation_type and edge.relation_type.value != relation_type:
                continue
            other = self.db.get_file(edge.dst_file_id)
            if other:
                related.append({
                    "file_id": other.file_id,
                    "name": other.name,
                    "path": other.path,
                    "relation": edge.relation_type.value,
                    "direction": "outgoing",
                    "confidence": edge.confidence,
                    "evidence": edge.evidence
                })

        for edge in edges_to:
            if relation_type and edge.relation_type.value != relation_type:
                continue
            other = self.db.get_file(edge.src_file_id)
            if other:
                related.append({
                    "file_id": other.file_id,
                    "name": other.name,
                    "path": other.path,
                    "relation": edge.relation_type.value,
                    "direction": "incoming",
                    "confidence": edge.confidence,
                    "evidence": edge.evidence
                })

        # Sort by confidence
        related.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "file_id": file_id,
            "related_count": len(related),
            "related_files": related
        }

    def read_snippet(self, file_id: int, max_chars: int = 2000) -> Dict[str, Any]:
        """Read a text snippet from a file."""
        # First check if we have extracted content
        content = self.db.get_content(file_id)
        if content and content.full_text:
            text = content.full_text[:max_chars]
            return {
                "file_id": file_id,
                "source": "extracted_content",
                "text": text,
                "truncated": len(content.full_text) > max_chars
            }

        # Otherwise, file info only
        file = self.db.get_file(file_id)
        if not file:
            return {"error": f"File not found: {file_id}"}

        return {
            "file_id": file_id,
            "source": "no_content",
            "message": f"No extracted content available for {file.name}. File type: {file.category.value}"
        }

    def list_folder(self, folder_path: str, limit: int = 50) -> Dict[str, Any]:
        """List contents of a folder."""
        # Get all roots and find matching files
        roots = self.db.list_roots()
        if not roots:
            return {"error": "No indexed roots found"}

        all_files = []
        for root in roots:
            files = self.db.list_files(root.root_id, limit=10000)
            for f in files:
                # Check if file is in the requested folder
                if f.parent_path == folder_path or f.path.startswith(folder_path + "/"):
                    all_files.append(f)

        # Separate folders and files
        folders = set()
        files = []

        for f in all_files:
            if f.is_dir:
                folders.add(f.path)
            else:
                # Only include direct children
                rel_path = f.path[len(folder_path):].lstrip("/")
                if "/" not in rel_path:  # Direct child
                    files.append({
                        "file_id": f.file_id,
                        "name": f.name,
                        "category": f.category.value,
                        "size_bytes": f.size_bytes
                    })

        return {
            "folder_path": folder_path,
            "subfolder_count": len(folders),
            "file_count": len(files),
            "files": files[:limit]
        }

    def find_notes_for_file(self, file_id: int) -> Dict[str, Any]:
        """Find notes/documents related to a data file."""
        file = self.db.get_file(file_id)
        if not file:
            return {"error": f"File not found: {file_id}"}

        # Get related files that are documents/spreadsheets
        related = self.get_related_files(file_id)

        notes = []
        for r in related.get("related_files", []):
            if r["relation"] in ["notes_for", "mentions"]:
                notes.append(r)

        # Also search for files mentioning this filename
        from ..services.search import SearchService
        search = SearchService(self.db)

        # Search for the filename in content
        filename_base = Path(file.name).stem
        fts_results = search.search_fts(filename_base, limit=10)

        for result in fts_results:
            if result.file_id != file_id:
                # Check if not already in notes
                if not any(n["file_id"] == result.file_id for n in notes):
                    notes.append({
                        "file_id": result.file_id,
                        "name": result.name,
                        "path": result.path,
                        "relation": "mentions_in_content",
                        "confidence": 0.7,
                        "evidence": f"File content mentions '{filename_base}'"
                    })

        return {
            "file_id": file_id,
            "file_name": file.name,
            "notes_found": len(notes),
            "notes": notes
        }

    # === Candidate Workflow Tool Implementations ===

    def get_candidate_edges(
        self,
        status: str = "pending",
        strategy_id: Optional[int] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get candidate edges awaiting review."""
        from ..domain.enums import CandidateStatus

        # Map status string to enum
        status_enum = None
        if status:
            try:
                status_enum = CandidateStatus(status)
            except ValueError:
                return {"error": f"Invalid status: {status}. Valid: pending, accepted, rejected, needs_audit"}

        candidates = self.db.list_candidate_edges(
            status=status_enum.value if status_enum else None,
            strategy_id=strategy_id,
            limit=limit
        )

        results = []
        for c in candidates:
            src_file = self.db.get_file(c.src_file_id)
            dst_file = self.db.get_file(c.dst_file_id)

            results.append({
                "candidate_id": c.candidate_id,
                "src_file_id": c.src_file_id,
                "src_name": src_file.name if src_file else "Unknown",
                "dst_file_id": c.dst_file_id,
                "dst_name": dst_file.name if dst_file else "Unknown",
                "relation_type": c.relation_type.value,
                "confidence": c.confidence,
                "status": c.status.value,
                "evidence_type": c.evidence.get("type", "unknown"),
                "evidence_excerpt": c.evidence.get("evidence_text", "")[:100] if c.evidence.get("evidence_text") else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })

        return {
            "status_filter": status,
            "count": len(results),
            "candidates": results
        }

    def review_candidate(
        self,
        candidate_id: int,
        action: str
    ) -> Dict[str, Any]:
        """Accept, reject, or flag a candidate edge for audit."""
        from ..domain.enums import CandidateStatus

        # Validate action
        valid_actions = {"accept", "reject", "audit"}
        if action not in valid_actions:
            return {"error": f"Invalid action: {action}. Valid: accept, reject, audit"}

        # Get candidate
        candidate = self.db.get_candidate_edge(candidate_id)
        if not candidate:
            return {"error": f"Candidate not found: {candidate_id}"}

        # Map action to status
        status_map = {
            "accept": CandidateStatus.ACCEPTED,
            "reject": CandidateStatus.REJECTED,
            "audit": CandidateStatus.NEEDS_AUDIT,
        }

        new_status = status_map[action]

        # Update candidate status
        success = self.db.update_candidate_status(
            candidate_id,
            new_status.value,
            reviewed_by="agent"
        )

        if not success:
            return {"error": f"Failed to update candidate {candidate_id}"}

        result = {
            "candidate_id": candidate_id,
            "action": action,
            "new_status": new_status.value,
            "success": True,
        }

        # If accepted, promote to confirmed edge
        if action == "accept":
            edge = self.db.promote_candidate_to_edge(candidate_id, reviewed_by="agent")
            if edge:
                result["promoted_edge_id"] = edge.edge_id
                result["message"] = "Candidate accepted and promoted to confirmed edge"
            else:
                result["message"] = "Candidate accepted but promotion failed"
        elif action == "reject":
            result["message"] = "Candidate rejected"
        else:
            result["message"] = "Candidate flagged for LLM audit"

        return result

    def get_linking_strategies(
        self,
        name: Optional[str] = None,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """List available linking strategies."""
        strategies = self.db.list_linker_strategies(name=name)

        # Filter by active status if requested
        if active_only:
            strategies = [s for s in strategies if s.is_active]

        results = []
        for s in strategies:
            results.append({
                "strategy_id": s.strategy_id,
                "name": s.name,
                "version": s.version,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "thresholds": s.thresholds,
                "column_mappings_count": len(s.column_mappings) if s.column_mappings else 0,
                "token_patterns_count": len(s.token_patterns) if s.token_patterns else 0,
            })

        return {
            "filter_name": name,
            "active_only": active_only,
            "count": len(results),
            "strategies": results
        }

    def get_candidate_stats(self) -> Dict[str, Any]:
        """Get statistics about link candidates."""
        from ..domain.enums import CandidateStatus

        stats = {
            "pending": 0,
            "accepted": 0,
            "rejected": 0,
            "needs_audit": 0,
            "total": 0,
        }

        # Count candidates by status
        for status in CandidateStatus:
            candidates = self.db.list_candidate_edges(
                status=status.value,
                limit=10000  # Get count
            )
            stats[status.value] = len(candidates)
            stats["total"] += len(candidates)

        # Get strategy counts
        strategies = self.db.list_linker_strategies()
        active_strategies = [s for s in strategies if s.is_active]

        stats["strategy_count"] = len(strategies)
        stats["active_strategy_count"] = len(active_strategies)

        return stats

    # === File Exploration Workflow Tool Definitions ===

    def _def_search_glob(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_glob",
            description="Search for files using glob patterns like 'FP_data_*.txt' or '*.abf'. Use this when the user describes a filename pattern.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g., 'FP_data_*.txt', '*.abf', 'notes*.txt')"
                    },
                    "folder": {
                        "type": "string",
                        "description": "Limit search to this folder path (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 50)",
                        "default": 50
                    }
                },
                "required": ["pattern"]
            },
            handler=self.search_glob
        )

    def _def_get_index_summary(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_index_summary",
            description="Get a summary of what's in the index: file counts by category, common extensions, folder structure. Use this after indexing to show the user what was found.",
            parameters={
                "type": "object",
                "properties": {
                    "root_id": {
                        "type": "integer",
                        "description": "Limit to specific root (optional, omit for all roots)"
                    }
                },
                "required": []
            },
            handler=self.get_index_summary
        )

    def _def_find_parent_files(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_parent_files",
            description="Find files in parent or ancestor folders of given files. Use this when the user says 'notes are in the parent folder' or similar.",
            parameters={
                "type": "object",
                "properties": {
                    "file_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of file IDs to find parents for"
                    },
                    "extension_filter": {
                        "type": "string",
                        "description": "Filter parent files by extension (e.g., '.txt', '.xlsx')"
                    },
                    "levels_up": {
                        "type": "integer",
                        "description": "How many levels up to look (default 2)",
                        "default": 2
                    }
                },
                "required": ["file_ids"]
            },
            handler=self.find_parent_files
        )

    def _def_label_files(self) -> ToolDefinition:
        return ToolDefinition(
            name="label_files",
            description="Assign a custom label/type to files (e.g., 'photometry_data', 'surgery_notes'). Use this when the user confirms a file type.",
            parameters={
                "type": "object",
                "properties": {
                    "file_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of file IDs to label"
                    },
                    "label": {
                        "type": "string",
                        "description": "The label to assign (e.g., 'photometry_data', 'photometry_notes', 'surgery_notes')"
                    }
                },
                "required": ["file_ids", "label"]
            },
            handler=self.label_files
        )

    def _def_get_files_by_label(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_files_by_label",
            description="Get all files with a specific label. Use this to find previously labeled files.",
            parameters={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "The label to search for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 100)",
                        "default": 100
                    }
                },
                "required": ["label"]
            },
            handler=self.get_files_by_label
        )

    # === File Exploration Workflow Tool Implementations ===

    def search_glob(
        self,
        pattern: str,
        folder: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Search files using glob pattern."""
        import fnmatch

        roots = self.db.list_roots()
        if not roots:
            return {"error": "No indexed roots found", "total_matches": 0}

        matching_files = []

        # Also try case-insensitive matching
        pattern_lower = pattern.lower()

        for root in roots:
            files = self.db.list_files(root.root_id, limit=50000)
            for f in files:
                # Skip directories
                if f.is_dir:
                    continue

                # Check folder filter
                if folder and not f.path.startswith(folder):
                    continue

                # Check glob pattern against filename (case-insensitive)
                if fnmatch.fnmatch(f.name, pattern) or fnmatch.fnmatch(f.name.lower(), pattern_lower):
                    matching_files.append({
                        "file_id": f.file_id,
                        "name": f.name,
                        "path": f.path,
                        "parent_path": f.parent_path,
                        "category": f.category.value,
                        "size_bytes": f.size_bytes,
                    })

                    if len(matching_files) >= limit:
                        break

            if len(matching_files) >= limit:
                break

        # If no matches, provide helpful feedback
        if not matching_files:
            # Check if there are similar files with different extension
            base_pattern = pattern.rsplit('.', 1)[0] if '.' in pattern else pattern
            similar_extensions = set()

            for root in roots:
                files = self.db.list_files(root.root_id, limit=10000)
                for f in files:
                    if f.is_dir:
                        continue
                    base_name = f.name.rsplit('.', 1)[0] if '.' in f.name else f.name
                    if fnmatch.fnmatch(base_name, base_pattern) or fnmatch.fnmatch(base_name.lower(), base_pattern.lower()):
                        ext = f.name.rsplit('.', 1)[1] if '.' in f.name else ''
                        if ext:
                            similar_extensions.add(ext)

            return {
                "pattern": pattern,
                "folder_filter": folder,
                "total_matches": 0,
                "message": f"NO FILES FOUND matching pattern '{pattern}'. Do NOT make up file IDs.",
                "suggestion": f"Files with similar base names exist with extensions: {', '.join(sorted(similar_extensions))}" if similar_extensions else "No similar files found. Check the pattern.",
                "files": []
            }

        # Group by parent folder for easier viewing
        by_folder = {}
        for f in matching_files:
            parent = f["parent_path"] or "/"
            if parent not in by_folder:
                by_folder[parent] = []
            by_folder[parent].append(f)

        return {
            "pattern": pattern,
            "folder_filter": folder,
            "total_matches": len(matching_files),
            "folders_with_matches": len(by_folder),
            "files": matching_files[:limit],
            "by_folder": {k: v for k, v in list(by_folder.items())[:20]}  # Top 20 folders
        }

    def get_index_summary(self, root_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of indexed files."""
        roots = self.db.list_roots()
        if not roots:
            return {"error": "No indexed roots found"}

        # Filter to specific root if requested
        if root_id:
            roots = [r for r in roots if r.root_id == root_id]
            if not roots:
                return {"error": f"Root not found: {root_id}"}

        summary = {
            "roots": [],
            "total_files": 0,
            "by_category": {},
            "by_extension": {},
            "top_folders": [],
        }

        all_files = []
        for root in roots:
            files = self.db.list_files(root.root_id, limit=50000)
            all_files.extend(files)

            root_files = [f for f in files if not f.is_dir]
            summary["roots"].append({
                "root_id": root.root_id,
                "label": root.label,
                "path": root.root_path,
                "file_count": len(root_files),
            })

        # Count non-directory files
        files_only = [f for f in all_files if not f.is_dir]
        summary["total_files"] = len(files_only)

        # Group by category
        for f in files_only:
            cat = f.category.value
            if cat not in summary["by_category"]:
                summary["by_category"][cat] = 0
            summary["by_category"][cat] += 1

        # Group by extension
        for f in files_only:
            ext = Path(f.name).suffix.lower() or "(no extension)"
            if ext not in summary["by_extension"]:
                summary["by_extension"][ext] = 0
            summary["by_extension"][ext] += 1

        # Sort extensions by count
        summary["by_extension"] = dict(
            sorted(summary["by_extension"].items(), key=lambda x: -x[1])[:15]
        )

        # Top folders by file count
        folder_counts = {}
        for f in files_only:
            parent = f.parent_path or "/"
            if parent not in folder_counts:
                folder_counts[parent] = 0
            folder_counts[parent] += 1

        summary["top_folders"] = [
            {"path": k, "file_count": v}
            for k, v in sorted(folder_counts.items(), key=lambda x: -x[1])[:10]
        ]

        return summary

    def find_parent_files(
        self,
        file_ids: List[int],
        extension_filter: Optional[str] = None,
        levels_up: int = 2
    ) -> Dict[str, Any]:
        """Find files in parent folders of given files."""
        if not file_ids:
            return {"error": "No file IDs provided"}

        # Get the files and their parent paths
        source_files = []
        parent_paths = set()

        for fid in file_ids[:100]:  # Limit to 100 source files
            f = self.db.get_file(fid)
            if f:
                source_files.append(f)
                # Collect parent paths up to N levels
                current_path = f.parent_path
                for _ in range(levels_up):
                    if current_path:
                        parent_paths.add(current_path)
                        # Go up one level
                        current_path = str(Path(current_path).parent)
                        if current_path == ".":
                            current_path = None

        if not parent_paths:
            return {
                "source_file_count": len(source_files),
                "parent_files_found": 0,
                "message": "No parent folders found"
            }

        # Find files in those parent folders
        roots = self.db.list_roots()
        parent_files = []

        for root in roots:
            all_files = self.db.list_files(root.root_id, limit=50000)
            for f in all_files:
                if f.is_dir:
                    continue
                if f.parent_path in parent_paths:
                    # Apply extension filter if specified
                    if extension_filter:
                        if not f.name.lower().endswith(extension_filter.lower()):
                            continue
                    parent_files.append({
                        "file_id": f.file_id,
                        "name": f.name,
                        "path": f.path,
                        "parent_path": f.parent_path,
                        "category": f.category.value,
                        "size_bytes": f.size_bytes,
                    })

        # Group by parent path
        by_parent = {}
        for f in parent_files:
            parent = f["parent_path"]
            if parent not in by_parent:
                by_parent[parent] = []
            by_parent[parent].append(f)

        return {
            "source_file_count": len(source_files),
            "parent_paths_checked": list(parent_paths),
            "parent_files_found": len(parent_files),
            "extension_filter": extension_filter,
            "files": parent_files[:100],
            "by_parent_folder": by_parent
        }

    def label_files(self, file_ids: List[int], label: str) -> Dict[str, Any]:
        """Assign a label to files."""
        if not file_ids:
            return {"error": "No file IDs provided"}
        if not label:
            return {"error": "No label provided"}

        # Normalize label
        label = label.lower().replace(" ", "_")

        labeled_count = 0
        errors = []

        for fid in file_ids[:500]:  # Limit to 500 files at once
            try:
                # Get existing content or create new
                content = self.db.get_content(fid)
                if content:
                    # Update entities with label
                    entities = content.entities or {}
                    if "labels" not in entities:
                        entities["labels"] = []
                    if label not in entities["labels"]:
                        entities["labels"].append(label)

                    # Update the content record
                    self.db.update_content_entities(fid, entities)
                    labeled_count += 1
                else:
                    # Create a minimal content record with the label
                    self.db.create_content_with_label(fid, label)
                    labeled_count += 1
            except Exception as e:
                errors.append({"file_id": fid, "error": str(e)})

        return {
            "label": label,
            "requested_count": len(file_ids),
            "labeled_count": labeled_count,
            "errors": errors[:10] if errors else []
        }

    def get_files_by_label(self, label: str, limit: int = 100) -> Dict[str, Any]:
        """Get files with a specific label."""
        if not label:
            return {"error": "No label provided"}

        label = label.lower().replace(" ", "_")

        roots = self.db.list_roots()
        if not roots:
            return {"error": "No indexed roots found"}

        matching_files = []

        for root in roots:
            files = self.db.list_files(root.root_id, limit=50000)
            for f in files:
                if f.is_dir:
                    continue

                content = self.db.get_content(f.file_id)
                if content and content.entities:
                    labels = content.entities.get("labels", [])
                    if label in labels:
                        matching_files.append({
                            "file_id": f.file_id,
                            "name": f.name,
                            "path": f.path,
                            "category": f.category.value,
                            "size_bytes": f.size_bytes,
                            "all_labels": labels,
                        })

                        if len(matching_files) >= limit:
                            break

            if len(matching_files) >= limit:
                break

        return {
            "label": label,
            "count": len(matching_files),
            "files": matching_files
        }
