"""AI Advisor module — Phase 1 MVP Chat.

Exports high-level agent + config; internal modules (tools, prompts)
are imported directly by agent.py.
"""

from dashboard_pipeline.ai.config import AIConfig, load_ai_config
from dashboard_pipeline.ai.agent import AIAgent, AIAgentError

__all__ = ["AIAgent", "AIAgentError", "AIConfig", "load_ai_config"]
