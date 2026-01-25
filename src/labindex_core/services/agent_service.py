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
SYSTEM_PROMPT_NATIVE = """You are a helpful research assistant for LabIndex, a tool for exploring lab files and data.

Your job is to help users find files, understand relationships between files, and answer questions about their research data.

## Key behaviors:
1. **Use tools to gather evidence** - Don't guess. Use the provided tools to find actual data.
2. **Cite your sources** - When you mention files, include their file_id and path so users can verify.
3. **Ask for clarification** - If a query is ambiguous, ask follow-up questions before searching.
4. **Be concise** - Give direct answers with evidence, not lengthy explanations.

## Response format:
- Start with a direct answer
- List relevant files with their paths
- Include evidence snippets when helpful
- End with a follow-up question if the user might want to explore further

Remember: You ONLY have read access. You cannot modify, delete, or create any files."""


# System prompt for text-based tool calling (Ollama, fallback)
SYSTEM_PROMPT_TEXT = """You are a helpful research assistant for LabIndex, a tool for exploring lab files and data.

Your job is to help users find files, understand relationships between files, and answer questions about their research data.

## Available Tools
You can use these tools by including a JSON block in your response:

1. Search files by name:
   {"tool": "search_files", "query": "experiment"}

2. Full-text search in file contents:
   {"tool": "search_content", "query": "PenkCre"}

3. Get file details:
   {"tool": "get_file_info", "file_id": 123}

4. Find related files:
   {"tool": "get_related_files", "file_id": 123}

5. Read text from a file:
   {"tool": "read_snippet", "file_id": 123}

6. List folder contents:
   {"tool": "list_folder", "folder_path": "experiments/2024"}

7. Find notes for a data file:
   {"tool": "find_notes_for_file", "file_id": 123}

## How to use tools:
1. Include the JSON tool call in your response
2. I will execute the tool and give you the results
3. Then you can provide a final answer based on the results

## Key behaviors:
- Use tools to find actual data - don't guess
- Cite file paths and IDs when mentioning files
- Be concise with direct answers

Example interaction:
User: "Find notes about PenkCre experiments"
You: Let me search for that.
{"tool": "search_content", "query": "PenkCre"}

Remember: You ONLY have read access. You cannot modify, delete, or create any files."""


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
