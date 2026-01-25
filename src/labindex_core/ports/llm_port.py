"""
LLM Port - Abstract interface for LLM providers.

Supports tool calling for agent interactions.
Implementations: Ollama, Claude, OpenAI, Gemini.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class LLMProvider(Enum):
    """Available LLM providers."""
    OLLAMA = "ollama"
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"


@dataclass
class ToolDefinition:
    """Definition of a tool the LLM can call."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for parameters
    handler: Callable[..., Any]  # Function to execute


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None  # Some providers use IDs


@dataclass
class ToolResult:
    """Result from executing a tool."""
    tool_name: str
    result: Any
    success: bool = True
    error: Optional[str] = None
    call_id: Optional[str] = None


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    content: str  # Text response
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # "stop", "tool_calls", "length", "error"
    usage: Optional[Dict[str, int]] = None  # Token usage stats


class LLMPort(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: Conversation history
            tools: Available tools the LLM can call
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with content and/or tool calls
        """
        pass

    @abstractmethod
    def get_provider(self) -> LLMProvider:
        """Get the provider type."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available (API key set, server running, etc.)."""
        pass

    def supports_native_tools(self) -> bool:
        """
        Check if this LLM supports native tool calling.

        If True, tools are passed to the API and the LLM returns structured tool calls.
        If False, use text-based tool calling (tools described in prompt, JSON parsed from response).

        Default is False for safety - override in adapters that support native tools.
        """
        return False
