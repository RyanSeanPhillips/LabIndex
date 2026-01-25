"""
Ollama LLM Adapter - Local LLM via Ollama.

Requires Ollama to be running locally (default: http://localhost:11434).
Supports tool calling with compatible models (llama3.1, mistral, etc.).
"""

import json
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any

from ..ports.llm_port import (
    LLMPort, LLMProvider, LLMResponse, Message,
    ToolDefinition, ToolCall
)


class OllamaLLM(LLMPort):
    """Ollama adapter for local LLM inference."""

    def __init__(
        self,
        model: str = None,  # Auto-detect if not specified
        base_url: str = "http://localhost:11434",
    ):
        """
        Initialize Ollama adapter.

        Args:
            model: Model name (e.g., "llama3.1", "mistral", "gemma3:4b").
                   If None, uses first available model.
            base_url: Ollama server URL
        """
        self.base_url = base_url.rstrip("/")
        self._available = None  # Cached availability check

        # Auto-detect model if not specified
        if model is None:
            models = self.list_models()
            self.model = models[0] if models else "llama3.1"
        else:
            self.model = model

    def get_provider(self) -> LLMProvider:
        return LLMProvider.OLLAMA

    def get_model_name(self) -> str:
        return self.model

    def is_available(self) -> bool:
        """Check if Ollama server is running and has at least one model."""
        if self._available is not None:
            return self._available

        try:
            # Check if server is running
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = data.get("models", [])
                self._available = len(models) > 0
                return self._available
        except Exception:
            self._available = False
            return False

    def list_models(self) -> List[str]:
        """List available models in Ollama."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = data.get("models", [])
                return [m.get("name", "") for m in models]
        except Exception:
            pass
        return []

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Send chat request to Ollama using /api/generate."""
        # Convert messages to a single prompt (like the working MetadataBrowser code)
        prompt_parts = []
        system_prompt = None

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        prompt = "\n\n".join(prompt_parts)
        if prompt_parts:
            prompt += "\n\nAssistant:"

        # If there's a system prompt, prepend it
        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"

        # Build request payload (matching working implementation)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        try:
            # Use urllib.request like the working MetadataBrowser code
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result.get('response', '')

                # Determine finish reason
                finish_reason = "stop"
                if result.get("done_reason") == "length":
                    finish_reason = "length"

                return LLMResponse(
                    content=content,
                    tool_calls=[],  # /api/generate doesn't support tools natively
                    finish_reason=finish_reason,
                    usage={
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                    }
                )

        except urllib.error.URLError as e:
            return LLMResponse(
                content=f"Error: Cannot connect to Ollama. Is it running? ({str(e)})",
                finish_reason="error"
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                finish_reason="error"
            )

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinition to Ollama tool format."""
        ollama_tools = []
        for tool in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return ollama_tools

    def simple_chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Simple single-turn chat without tools."""
        messages = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=prompt))

        response = self.chat(messages)
        return response.content
