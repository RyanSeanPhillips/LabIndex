"""
Agent worker thread.

Runs LLM agent queries in the background without blocking the UI.
"""

from typing import List
from PyQt6.QtCore import QThread, pyqtSignal


class AgentWorker(QThread):
    """
    Background thread for agent queries.

    Signals:
        status_update(str): Emitted during processing with status message
        finished(str, list, str): Emitted when complete with (response, tool_calls, error)
    """

    status_update = pyqtSignal(str)  # status message
    finished = pyqtSignal(str, list, str)  # response, tool_calls, error

    def __init__(self, agent, message: str):
        """
        Initialize the worker.

        Args:
            agent: The agent service to use (AgentService)
            message: The user message to process
        """
        super().__init__()
        self.agent = agent
        self.message = message

    def run(self):
        """Run the agent query."""
        try:
            # Use the streaming query to get status updates
            response = None
            for update in self.agent.query_stream(self.message):
                if isinstance(update, str):
                    self.status_update.emit(update)
                else:
                    response = update

            if response:
                self.finished.emit(
                    response.content,
                    response.tool_calls_made,
                    response.error or ""
                )
            else:
                # Fallback to non-streaming
                response = self.agent.query(self.message)
                self.finished.emit(
                    response.content,
                    response.tool_calls_made,
                    response.error or ""
                )
        except Exception as e:
            self.finished.emit("", [], str(e))
