"""
Agent Service - Orchestrates the LLM agent for LabIndex.

Handles:
- User query processing
- Tool execution loop (native or text-based)
- Response formatting with citations
- Follow-up question generation
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Generator
from enum import Enum

from ..ports.llm_port import LLMPort, Message, ToolCall, ToolResult, LLMResponse
from ..ports.db_port import DBPort
from ..ports.fs_port import FSPort
from .agent_tools import AgentTools


class AgentState(Enum):
    """Current state of the agent."""
    IDLE = "idle"
    THINKING = "thinking"
    CALLING_TOOLS = "calling_tools"
    RESPONDING = "responding"
    ERROR = "error"


@dataclass
class AgentResponse:
    """Response from the agent."""
    content: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls_made: List[str] = field(default_factory=list)
    state: AgentState = AgentState.RESPONDING
    error: Optional[str] = None


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    user_message: str
    assistant_response: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


# System prompt for native tool calling (Claude, GPT-4)
SYSTEM_PROMPT_NATIVE = """You are LabIndex, a helpful research assistant for exploring lab files and data.

Your job is to help users:
1. Understand what's in their indexed files
2. Find files by pattern (e.g., "FP_data_*.txt")
3. Identify relationships between files (data files and their notes)
4. Label files with custom types for later retrieval

## Key behaviors:
1. **Use tools to gather evidence** - Don't guess. Use the provided tools to find actual data.
2. **After indexing, show a summary** - Use get_index_summary to show what was found.
3. **When users describe file patterns** - Use search_glob to find matches (e.g., "FP_data_*.txt").
4. **When users describe file locations** - Use find_parent_files to find files relative to others.
5. **When users confirm file types** - Use label_files to mark them (e.g., "photometry_data").
6. **Cite your sources** - Include file_id and path so users can verify.
7. **Be concise** - Give direct answers with evidence, not lengthy explanations.

## Response format:
- Start with a direct answer
- List relevant files grouped by folder when helpful
- Include counts (e.g., "Found 45 files matching...")
- End with a suggested next step

## File type labeling workflow:
1. User describes a file pattern → search_glob to find matches
2. User confirms those are the right files → label_files to mark them
3. User describes where related files are → find_parent_files to locate them
4. User confirms those files → label_files with a different label
5. Now both file types can be retrieved with get_files_by_label

Remember: You ONLY have read access to the index. You cannot modify actual files on disk."""


# System prompt for text-based tool calling (Ollama, fallback)
SYSTEM_PROMPT_TEXT = """You are LabIndex, a helpful research assistant for exploring lab files and data.

Your job is to help users:
1. Understand what's in their indexed files
2. Find files by pattern (e.g., "FP_data_*.txt")
3. Identify relationships between files (data files and their notes)
4. Label files with custom types for later retrieval

## Available Tools
You can use these tools by including a JSON block in your response:

### Basic Search
1. Search files by name pattern:
   {"tool": "search_files", "query": "experiment"}

2. Full-text search in file contents:
   {"tool": "search_content", "query": "PenkCre"}

3. Search with glob patterns (e.g., FP_data_*.txt):
   {"tool": "search_glob", "pattern": "FP_data_*.txt"}

### File Information
4. Get file details:
   {"tool": "get_file_info", "file_id": 123}

5. Read text from a file:
   {"tool": "read_snippet", "file_id": 123}

6. List folder contents:
   {"tool": "list_folder", "folder_path": "experiments/2024"}

### Index Overview
7. Get summary of indexed files:
   {"tool": "get_index_summary"}

### File Relationships
8. Find related files:
   {"tool": "get_related_files", "file_id": 123}

9. Find notes for a data file:
   {"tool": "find_notes_for_file", "file_id": 123}

10. Find files in parent folders:
    {"tool": "find_parent_files", "file_ids": [1, 2, 3], "extension_filter": ".txt"}

### File Labeling
11. Label files with a type:
    {"tool": "label_files", "file_ids": [1, 2, 3], "label": "photometry_data"}

12. Get files by label:
    {"tool": "get_files_by_label", "label": "photometry_data"}

## How to use tools:
1. Include the JSON tool call in your response
2. I will execute the tool and give you the results
3. Then you can provide a final answer based on the results

## Key behaviors:
- Use get_index_summary after a folder is indexed to show what was found
- Use search_glob when users describe patterns like "FP_data_*.txt"
- Use find_parent_files when users say "notes are in the parent folder"
- Use label_files when users confirm file types
- Always cite file IDs and paths
- Be concise with direct answers

## Example workflow:
User: "I just indexed my photometry folder"
You: Let me show you what's in it.
{"tool": "get_index_summary"}

User: "My data files are FP_data_*.txt"
You: Let me find those.
{"tool": "search_glob", "pattern": "FP_data_*.txt"}

User: "Yes, label those as photometry_data"
You: {"tool": "label_files", "file_ids": [1, 2, 3, ...], "label": "photometry_data"}

Remember: You ONLY have read access to the index. You cannot modify actual files on disk."""


class AgentService:
    """
    Agent service for handling user queries with tool calling.

    Supports multiple LLM providers (Ollama, Claude, OpenAI, Gemini).
    """

    def __init__(
        self,
        llm: LLMPort,
        db: DBPort,
        fs: FSPort,
        max_tool_rounds: int = 5,
    ):
        """
        Initialize the agent service.

        Args:
            llm: LLM provider to use
            db: Database port
            fs: Filesystem port
            max_tool_rounds: Maximum tool call rounds per query
        """
        self.llm = llm
        self.db = db
        self.fs = fs
        self.max_tool_rounds = max_tool_rounds
        self.tools = AgentTools(db, fs)
        self.conversation_history: List[Message] = []

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()

    def _get_system_prompt(self) -> str:
        """Get the appropriate system prompt based on LLM capabilities."""
        if self.llm.supports_native_tools():
            return SYSTEM_PROMPT_NATIVE
        return SYSTEM_PROMPT_TEXT

    def _parse_text_tool_calls(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response text (for text-based tool calling)."""
        tool_calls = []

        # Try multiple patterns to find JSON tool calls
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
            r'```\s*([\s\S]*?)\s*```',      # ``` ... ```
            r'(\{"tool":\s*"[^"]+?"[^}]*\})',  # inline {"tool": ...}
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response_text)
            for match in matches:
                try:
                    tool_call = json.loads(match.strip())
                    if 'tool' in tool_call:
                        tool_calls.append(tool_call)
                except json.JSONDecodeError:
                    continue

        return tool_calls

    def _extract_citations(self, result: Dict[str, Any], citations: List[Dict[str, Any]]):
        """Extract file citations from tool results."""
        if isinstance(result, dict):
            if "files" in result:
                for f in result["files"]:
                    citations.append({
                        "file_id": f.get("file_id"),
                        "name": f.get("name"),
                        "path": f.get("path")
                    })
            if "related_files" in result:
                for f in result["related_files"]:
                    citations.append({
                        "file_id": f.get("file_id"),
                        "name": f.get("name"),
                        "path": f.get("path")
                    })

    def query(self, user_message: str) -> AgentResponse:
        """Process a user query and return a response."""
        # Use the appropriate method based on LLM capabilities
        if self.llm.supports_native_tools():
            return self._query_native(user_message)
        return self._query_text_based(user_message)

    def _query_native(self, user_message: str) -> AgentResponse:
        """Process query using native tool calling (Claude, GPT-4)."""
        self.conversation_history.append(Message(role="user", content=user_message))

        messages = [
            Message(role="system", content=SYSTEM_PROMPT_NATIVE)
        ] + self.conversation_history

        tool_defs = self.tools.get_tool_definitions()
        tool_calls_made = []
        citations = []

        for round_num in range(self.max_tool_rounds):
            response = self.llm.chat(
                messages=messages,
                tools=tool_defs,
                temperature=0.3,
                max_tokens=2000,
            )

            if response.finish_reason == "error":
                return AgentResponse(
                    content=response.content,
                    state=AgentState.ERROR,
                    error=response.content
                )

            if not response.tool_calls:
                self.conversation_history.append(Message(
                    role="assistant",
                    content=response.content
                ))
                return AgentResponse(
                    content=response.content,
                    citations=citations,
                    tool_calls_made=tool_calls_made,
                    state=AgentState.RESPONDING
                )

            # Execute tool calls
            tool_results = []
            for tool_call in response.tool_calls:
                tool_calls_made.append(tool_call.tool_name)
                result = self.tools.execute_tool(tool_call.tool_name, tool_call.arguments)
                self._extract_citations(result, citations)
                tool_results.append(ToolResult(
                    tool_name=tool_call.tool_name,
                    result=result,
                    call_id=tool_call.call_id
                ))

            messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls
            ))
            messages.append(Message(role="tool", content="", tool_results=tool_results))

        return AgentResponse(
            content="I've made several tool calls but couldn't complete. Please try a more specific query.",
            citations=citations,
            tool_calls_made=tool_calls_made,
            state=AgentState.ERROR,
            error="Max tool rounds reached"
        )

    def _query_text_based(self, user_message: str) -> AgentResponse:
        """Process query using text-based tool calling (Ollama, fallback)."""
        self.conversation_history.append(Message(role="user", content=user_message))

        messages = [
            Message(role="system", content=SYSTEM_PROMPT_TEXT)
        ] + self.conversation_history

        tool_calls_made = []
        citations = []

        for round_num in range(self.max_tool_rounds):
            response = self.llm.chat(
                messages=messages,
                tools=None,  # No native tools
                temperature=0.3,
                max_tokens=2000,
            )

            if response.finish_reason == "error":
                return AgentResponse(
                    content=response.content,
                    state=AgentState.ERROR,
                    error=response.content
                )

            # Parse tool calls from response text
            text_tool_calls = self._parse_text_tool_calls(response.content)

            if not text_tool_calls:
                # No tool calls - this is the final response
                self.conversation_history.append(Message(
                    role="assistant",
                    content=response.content
                ))
                return AgentResponse(
                    content=response.content,
                    citations=citations,
                    tool_calls_made=tool_calls_made,
                    state=AgentState.RESPONDING
                )

            # Execute text-based tool calls
            tool_results_text = []
            for tc in text_tool_calls:
                tool_name = tc.get('tool', 'unknown')
                tool_args = {k: v for k, v in tc.items() if k != 'tool'}
                tool_calls_made.append(tool_name)

                result = self.tools.execute_tool(tool_name, tool_args)
                self._extract_citations(result, citations)

                # Format result for text context
                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                tool_results_text.append(f"[{tool_name}] Result:\n{result_str}")

            # Add assistant response and tool results to conversation
            messages.append(Message(role="assistant", content=response.content))

            # Send tool results back as a user message
            followup = f"Tool results:\n\n" + "\n\n".join(tool_results_text) + "\n\nBased on these results, please provide a helpful answer."
            messages.append(Message(role="user", content=followup))

        return AgentResponse(
            content="I've made several tool calls but couldn't complete. Please try a more specific query.",
            citations=citations,
            tool_calls_made=tool_calls_made,
            state=AgentState.ERROR,
            error="Max tool rounds reached"
        )

    def query_stream(self, user_message: str) -> Generator[str, None, AgentResponse]:
        """Process a query with streaming updates."""
        if self.llm.supports_native_tools():
            return self._query_stream_native(user_message)
        return self._query_stream_text_based(user_message)

    def _query_stream_native(self, user_message: str) -> Generator[str, None, AgentResponse]:
        """Stream query using native tool calling."""
        yield "Thinking..."

        self.conversation_history.append(Message(role="user", content=user_message))

        messages = [
            Message(role="system", content=SYSTEM_PROMPT_NATIVE)
        ] + self.conversation_history

        tool_defs = self.tools.get_tool_definitions()
        tool_calls_made = []
        citations = []

        for round_num in range(self.max_tool_rounds):
            response = self.llm.chat(
                messages=messages,
                tools=tool_defs,
                temperature=0.3,
                max_tokens=2000,
            )

            if response.finish_reason == "error":
                return AgentResponse(
                    content=response.content,
                    state=AgentState.ERROR,
                    error=response.content
                )

            if not response.tool_calls:
                self.conversation_history.append(Message(
                    role="assistant",
                    content=response.content
                ))
                return AgentResponse(
                    content=response.content,
                    citations=citations,
                    tool_calls_made=tool_calls_made,
                    state=AgentState.RESPONDING
                )

            tool_results = []
            for tool_call in response.tool_calls:
                yield f"Calling {tool_call.tool_name}..."
                tool_calls_made.append(tool_call.tool_name)
                result = self.tools.execute_tool(tool_call.tool_name, tool_call.arguments)
                self._extract_citations(result, citations)
                tool_results.append(ToolResult(
                    tool_name=tool_call.tool_name,
                    result=result,
                    call_id=tool_call.call_id
                ))

                # Show result count
                if isinstance(result, dict) and "count" in result:
                    yield f"Found {result['count']} results"

            messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls
            ))
            messages.append(Message(role="tool", content="", tool_results=tool_results))
            yield "Analyzing results..."

        return AgentResponse(
            content="I've made several tool calls but couldn't complete the response.",
            citations=citations,
            tool_calls_made=tool_calls_made,
            state=AgentState.ERROR,
            error="Max tool rounds reached"
        )

    def _query_stream_text_based(self, user_message: str) -> Generator[str, None, AgentResponse]:
        """Stream query using text-based tool calling (Ollama, fallback)."""
        yield "Thinking..."

        self.conversation_history.append(Message(role="user", content=user_message))

        messages = [
            Message(role="system", content=SYSTEM_PROMPT_TEXT)
        ] + self.conversation_history

        tool_calls_made = []
        citations = []

        for round_num in range(self.max_tool_rounds):
            response = self.llm.chat(
                messages=messages,
                tools=None,
                temperature=0.3,
                max_tokens=2000,
            )

            if response.finish_reason == "error":
                return AgentResponse(
                    content=response.content,
                    state=AgentState.ERROR,
                    error=response.content
                )

            text_tool_calls = self._parse_text_tool_calls(response.content)

            if not text_tool_calls:
                self.conversation_history.append(Message(
                    role="assistant",
                    content=response.content
                ))
                return AgentResponse(
                    content=response.content,
                    citations=citations,
                    tool_calls_made=tool_calls_made,
                    state=AgentState.RESPONDING
                )

            # Execute text-based tool calls with status updates
            tool_results_text = []
            for tc in text_tool_calls:
                tool_name = tc.get('tool', 'unknown')
                tool_args = {k: v for k, v in tc.items() if k != 'tool'}

                yield f"Calling {tool_name}..."
                tool_calls_made.append(tool_name)

                result = self.tools.execute_tool(tool_name, tool_args)
                self._extract_citations(result, citations)

                # Show result count
                if isinstance(result, dict) and "count" in result:
                    yield f"Found {result['count']} results"

                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                tool_results_text.append(f"[{tool_name}] Result:\n{result_str}")

            messages.append(Message(role="assistant", content=response.content))
            followup = f"Tool results:\n\n" + "\n\n".join(tool_results_text) + "\n\nBased on these results, please provide a helpful answer."
            messages.append(Message(role="user", content=followup))
            yield "Analyzing results..."

        return AgentResponse(
            content="I've made several tool calls but couldn't complete the response.",
            citations=citations,
            tool_calls_made=tool_calls_made,
            state=AgentState.ERROR,
            error="Max tool rounds reached"
        )

    def get_suggested_queries(self) -> List[str]:
        """Get suggested queries for new users."""
        return [
            "Find all ABF files from 2024",
            "Search for surgery notes",
            "What files mention PenkCre?",
            "Find notes for recording_001.abf",
            "List files in the Data folder",
            "Show me recent Excel spreadsheets",
        ]
