"""
Agent ViewModel for the chat assistant.

Manages:
- LLM provider selection
- Chat messages
- Agent query state
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt6.QtCore import pyqtSignal

from .base import BaseViewModel
from labindex_core.ports.db_port import DBPort
from labindex_core.ports.fs_port import FSPort


@dataclass
class ChatMessage:
    """A chat message for display."""
    sender: str  # "You", "Assistant", "Tools", "Error"
    content: str
    color: str  # CSS color string
    timestamp: str  # HH:MM format


@dataclass
class LLMProvider:
    """Information about an LLM provider."""
    name: str
    provider: str  # Provider ID
    available: bool
    reason: str = ""  # Reason if not available


class AgentVM(BaseViewModel):
    """
    ViewModel for the chat assistant.

    Signals:
        providers_changed: Emitted when provider list changes
        status_changed(str): Emitted when status message changes
        message_added(ChatMessage): Emitted when a new message is added
        thinking_changed(bool): Emitted when thinking state changes

    State:
        available_providers: List of LLM providers
        selected_provider_index: Index of selected provider
        provider_status: Current status message
        messages: Chat history
        is_thinking: Whether agent is processing
        current_status: Current status message during processing
    """

    # Signals
    providers_changed = pyqtSignal()
    status_changed = pyqtSignal(str)
    message_added = pyqtSignal(object)  # ChatMessage
    thinking_changed = pyqtSignal(bool)

    def __init__(self, db: DBPort, fs: FSPort):
        """
        Initialize the ViewModel.

        Args:
            db: Database adapter for agent tools
            fs: Filesystem adapter for agent tools
        """
        super().__init__()

        self._db = db
        self._fs = fs

        # State
        self._providers: List[LLMProvider] = []
        self._selected_provider_index: int = -1
        self._provider_status: str = ""
        self._messages: List[ChatMessage] = []
        self._is_thinking: bool = False
        self._current_status: str = ""

        # Agent instance (created on-demand)
        self._agent = None
        self._current_worker = None

        # Load providers
        self.refresh_providers()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def available_providers(self) -> List[LLMProvider]:
        """Get list of available LLM providers."""
        return self._providers.copy()

    @property
    def selected_provider_index(self) -> int:
        """Get index of selected provider."""
        return self._selected_provider_index

    @property
    def selected_provider(self) -> Optional[LLMProvider]:
        """Get the selected provider, or None."""
        if 0 <= self._selected_provider_index < len(self._providers):
            return self._providers[self._selected_provider_index]
        return None

    @property
    def provider_status(self) -> str:
        """Get current provider status message."""
        return self._provider_status

    @property
    def messages(self) -> List[ChatMessage]:
        """Get chat message history."""
        return self._messages.copy()

    @property
    def is_thinking(self) -> bool:
        """Check if agent is processing."""
        return self._is_thinking

    @property
    def current_status(self) -> str:
        """Get current processing status."""
        return self._current_status

    @property
    def has_agent(self) -> bool:
        """Check if an agent is initialized."""
        return self._agent is not None

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def refresh_providers(self) -> None:
        """Refresh the list of available LLM providers."""
        try:
            from labindex_core.adapters.llm_factory import get_available_providers
            providers = get_available_providers()

            self._providers = [
                LLMProvider(
                    name=p["name"],
                    provider=p["provider"],
                    available=p["available"],
                    reason=p.get("reason", ""),
                )
                for p in providers
            ]

            # Select first available
            self._selected_provider_index = -1
            for i, p in enumerate(self._providers):
                if p.available:
                    self._selected_provider_index = i
                    break

            self._init_agent()
            self.providers_changed.emit()

        except Exception as e:
            self._providers = []
            self._provider_status = f"Error loading providers: {e}"
            self.status_changed.emit(self._provider_status)

    def select_provider(self, index: int) -> None:
        """
        Select an LLM provider.

        Args:
            index: Index of provider to select
        """
        if index == self._selected_provider_index:
            return

        if 0 <= index < len(self._providers):
            self._selected_provider_index = index
            provider = self._providers[index]

            if provider.available:
                self._agent = None  # Reset to use new provider
                self._init_agent()
            else:
                self._agent = None
                self._provider_status = f"Not available: {provider.reason}"
                self.status_changed.emit(self._provider_status)

    def send_message(self, message: str) -> bool:
        """
        Send a message to the agent.

        Args:
            message: The user message

        Returns:
            True if message was sent
        """
        message = message.strip()
        if not message:
            return False

        # Add user message to history
        user_msg = ChatMessage(
            sender="You",
            content=message,
            color="#4fc3f7",
            timestamp=datetime.now().strftime("%H:%M"),
        )
        self._messages.append(user_msg)
        self.message_added.emit(user_msg)

        # Check if we have an agent
        if self._agent is None:
            self._init_agent()

        if self._agent is None:
            error_msg = ChatMessage(
                sender="Assistant",
                content="No LLM available. Please select a provider or start Ollama.",
                color="#ff6b6b",
                timestamp=datetime.now().strftime("%H:%M"),
            )
            self._messages.append(error_msg)
            self.message_added.emit(error_msg)
            return False

        # Start processing
        self._is_thinking = True
        self._current_status = "Thinking..."
        self.thinking_changed.emit(True)
        self.status_changed.emit(self._current_status)

        # Run in background thread
        from ..workers import AgentWorker

        self._current_worker = AgentWorker(self._agent, message)
        self._current_worker.status_update.connect(self._on_agent_status)
        self._current_worker.finished.connect(self._on_agent_response)
        self._current_worker.start()

        return True

    def clear_history(self) -> None:
        """Clear chat history."""
        self._messages = []
        if self._agent:
            self._agent.clear_history()
        self.providers_changed.emit()  # Trigger UI refresh

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _init_agent(self) -> None:
        """Initialize the agent with selected provider."""
        if self._selected_provider_index < 0:
            self._agent = None
            return

        if self._selected_provider_index >= len(self._providers):
            self._agent = None
            return

        provider = self._providers[self._selected_provider_index]
        if not provider.available:
            self._agent = None
            return

        try:
            from labindex_core.adapters.llm_factory import create_llm
            from labindex_core.services.agent_service import AgentService

            llm = create_llm(provider.provider)
            if llm:
                self._agent = AgentService(llm, self._db, self._fs)
                self._provider_status = f"Ready: {llm.get_model_name()}"
            else:
                self._agent = None
                self._provider_status = "Failed to create LLM"

            self.status_changed.emit(self._provider_status)

        except Exception as e:
            self._agent = None
            self._provider_status = f"Error: {str(e)[:30]}"
            self.status_changed.emit(self._provider_status)

    def _on_agent_status(self, status: str) -> None:
        """Handle agent status update."""
        if "tool" in status.lower() or "search" in status.lower():
            display = f"🔧 {status}"
        else:
            display = f"🤔 {status}"
        self._current_status = display
        self.status_changed.emit(display)

    def _on_agent_response(self, response: str, tool_calls: list, error: str) -> None:
        """Handle agent response."""
        self._is_thinking = False
        self._current_status = ""
        self._current_worker = None

        self.thinking_changed.emit(False)
        self.status_changed.emit("")

        if error:
            error_msg = ChatMessage(
                sender="Error",
                content=error,
                color="#ff6b6b",
                timestamp=datetime.now().strftime("%H:%M"),
            )
            self._messages.append(error_msg)
            self.message_added.emit(error_msg)
        else:
            # Show tool calls if any
            if tool_calls:
                tools_str = ", ".join(tool_calls)
                tools_msg = ChatMessage(
                    sender="Tools",
                    content=f"🔧 Used: {tools_str}",
                    color="#888888",
                    timestamp=datetime.now().strftime("%H:%M"),
                )
                self._messages.append(tools_msg)
                self.message_added.emit(tools_msg)

            # Add assistant response
            assistant_msg = ChatMessage(
                sender="Assistant",
                content=response,
                color="#90ff90",
                timestamp=datetime.now().strftime("%H:%M"),
            )
            self._messages.append(assistant_msg)
            self.message_added.emit(assistant_msg)
