"""SignalSweep data-quality agent."""

__version__ = "0.3.0"

# ADK discovers ``root_agent`` from the package's agent module. This import is
# safe when google-adk is not installed because agent.py keeps the dependency
# optional for the local CLI and tests.
from . import agent

__all__ = ["__version__", "agent"]
