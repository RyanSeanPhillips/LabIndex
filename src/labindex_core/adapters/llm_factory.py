"""
LLM Factory - Creates LLM adapters based on provider selection.
"""

import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any
from ..ports.llm_port import LLMPort, LLMProvider


def get_available_providers() -> List[Dict[str, Any]]:
    """
    Get list of available LLM providers with their status.

    Returns list of dicts with:
    - provider: LLMProvider enum
    - name: Display name
    - available: Whether it's currently usable
    - models: List of available models (if applicable)
    - reason: Why it's not available (if applicable)
    """
    providers = []

    # Check Ollama
    ollama_info = {
        "provider": LLMProvider.OLLAMA,
        "name": "Ollama (Local)",
        "available": False,
        "models": [],
        "reason": None
    }
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            models = data.get("models", [])
            model_names = [m.get("name", "") for m in models]
            if model_names:
                ollama_info["available"] = True
                ollama_info["models"] = model_names
                # Update name to show the model
                ollama_info["name"] = f"Ollama ({model_names[0]})"
            else:
                ollama_info["reason"] = "No models installed"
    except urllib.error.URLError:
        ollama_info["reason"] = "Ollama not running"
    except Exception as e:
        ollama_info["reason"] = str(e)
    providers.append(ollama_info)

    # Check Claude
    claude_info = {
        "provider": LLMProvider.CLAUDE,
        "name": "Claude (Anthropic)",
        "available": False,
        "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "reason": None
    }
    try:
        from .claude_llm import ClaudeLLM
        claude = ClaudeLLM()
        if claude.is_available():
            claude_info["available"] = True
        else:
            claude_info["reason"] = "ANTHROPIC_API_KEY not set"
    except ImportError:
        claude_info["reason"] = "anthropic package not installed"
    except Exception as e:
        claude_info["reason"] = str(e)
    providers.append(claude_info)

    # Check OpenAI
    openai_info = {
        "provider": LLMProvider.OPENAI,
        "name": "OpenAI (GPT)",
        "available": False,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "reason": None
    }
    try:
        import os
        if os.environ.get("OPENAI_API_KEY"):
            openai_info["available"] = True
        else:
            openai_info["reason"] = "OPENAI_API_KEY not set"
    except Exception as e:
        openai_info["reason"] = str(e)
    providers.append(openai_info)

    # Check Gemini
    gemini_info = {
        "provider": LLMProvider.GEMINI,
        "name": "Gemini (Google)",
        "available": False,
        "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
        "reason": None
    }
    try:
        import os
        if os.environ.get("GOOGLE_API_KEY"):
            gemini_info["available"] = True
        else:
            gemini_info["reason"] = "GOOGLE_API_KEY not set"
    except Exception as e:
        gemini_info["reason"] = str(e)
    providers.append(gemini_info)

    return providers


def create_llm(
    provider: LLMProvider,
    model: Optional[str] = None,
    **kwargs
) -> Optional[LLMPort]:
    """
    Create an LLM adapter for the specified provider.

    Args:
        provider: Which provider to use
        model: Model name (optional, uses default if not specified)
        **kwargs: Additional provider-specific options

    Returns:
        LLMPort instance or None if provider not available
    """
    if provider == LLMProvider.OLLAMA:
        from .ollama_llm import OllamaLLM
        return OllamaLLM(
            model=model,  # None = auto-detect first available model
            base_url=kwargs.get("base_url", "http://localhost:11434")
        )

    elif provider == LLMProvider.CLAUDE:
        from .claude_llm import ClaudeLLM
        return ClaudeLLM(
            model=model or "claude-3-5-sonnet-20241022",
            api_key=kwargs.get("api_key")
        )

    elif provider == LLMProvider.OPENAI:
        # TODO: Implement OpenAI adapter
        raise NotImplementedError("OpenAI adapter not yet implemented")

    elif provider == LLMProvider.GEMINI:
        # TODO: Implement Gemini adapter
        raise NotImplementedError("Gemini adapter not yet implemented")

    return None


def get_default_provider() -> Optional[LLMPort]:
    """
    Get the first available LLM provider.

    Priority: Ollama (free/local) > Claude > OpenAI > Gemini
    """
    providers = get_available_providers()

    for p in providers:
        if p["available"]:
            models = p["models"]
            model = models[0] if models else None
            try:
                return create_llm(p["provider"], model)
            except Exception:
                continue

    return None
