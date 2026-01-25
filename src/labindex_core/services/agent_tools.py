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
