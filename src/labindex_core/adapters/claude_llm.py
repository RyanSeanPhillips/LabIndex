"""
Claude LLM Adapter - Anthropic's Claude API.

Requires ANTHROPIC_API_KEY environment variable or explicit key.
Excellent tool calling support.
"""

import os
import json
from typing import List, Optional, Dict, Any

from ..ports.llm_port import (
    LLMPort, LLMProvider, LLMResponse, Message,
    ToolDefinition, ToolCall
)


class ClaudeLLM(LLMPort):
    """Claude adapter using Anthropic API."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Claude adapter.

        Args:
            model: Model name (e.g., "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307")
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        """
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def get_provider(self) -> LLMProvider:
        return LLMProvider.CLAUDE

    def get_model_name(self) -> str:
        return self.model

    def is_available(self) -> bool:
        """Check if API key is set and client can be created."""
        if not self.api_key:
            return False
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def supports_native_tools(self) -> bool:
        """Claude has excellent native tool calling support."""
        return True

    def _get_client(self):
        """Lazy load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
        return self._client

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Send chat request to Claude."""

        client = self._get_client()

        # Separate system message from conversation
        system_content = None
        claude_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            elif msg.role == "tool":
                # Convert tool results to Claude format
                for result in msg.tool_results:
                    claude_messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": result.call_id or "unknown",
                            "content": json.dumps(result.result) if not isinstance(result.result, str) else result.result
                        }]
                    })
            else:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Build request kwargs
        kwargs = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_content:
            kwargs["system"] = system_content

        # Add tools if provided
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            response = client.messages.create(**kwargs)

            # Parse response
            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        tool_name=block.name,
                        arguments=block.input,
                        call_id=block.id
                    ))

            # Determine finish reason
            finish_reason = "stop"
            if response.stop_reason == "tool_use":
                finish_reason = "tool_calls"
            elif response.stop_reason == "max_tokens":
                finish_reason = "length"

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                }
            )

        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                finish_reason="error"
            )

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinition to Claude tool format."""
        claude_tools = []
        for tool in tools:
            claude_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters
            })
        return claude_tools

    def simple_chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Simple single-turn chat without tools."""
        messages = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=prompt))

        response = self.chat(messages)
        return response.content
