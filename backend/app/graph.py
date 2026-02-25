"""LangGraph workflow — wires pipeline nodes with error routing."""

from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.nodes.analyze import analyze
from app.nodes.capture import capture
from app.nodes.error_handler import handle_error
from app.nodes.generate import generate
from app.nodes.ingest import ingest
from app.state import AgentState

logger = logging.getLogger(__name__)

# Module-level singleton — populated during FastAPI lifespan
compiled_graph = None
_checkpointer_ctx = None


def _should_handle_error(state: AgentState) -> str:
    """Route to error_handler if state contains an error, else continue."""
    if state.get("error"):
        return "error_handler"
    return "continue"


def build_graph(checkpointer: AsyncPostgresSaver) -> object:
    """Build and compile the StateGraph with conditional error routing."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("ingest", ingest)
    graph.add_node("analyze", analyze)
    graph.add_node("capture", capture)
    graph.add_node("generate", generate)
    graph.add_node("error_handler", handle_error)

    # Entry point
    graph.set_entry_point("ingest")

    # Conditional edges: after each node, check for errors
    for source, target in [
        ("ingest", "analyze"),
        ("analyze", "capture"),
        ("capture", "generate"),
    ]:
        graph.add_conditional_edges(
            source,
            _should_handle_error,
            {"error_handler": "error_handler", "continue": target},
        )

    # After generate, check for error or finish
    graph.add_conditional_edges(
        "generate",
        _should_handle_error,
        {"error_handler": "error_handler", "continue": END},
    )

    # Error handler always ends the graph
    graph.add_edge("error_handler", END)

    return graph.compile(checkpointer=checkpointer)


async def init_graph(checkpoint_url: str) -> None:
    """Initialize the checkpointer and compile the graph."""
    global compiled_graph, _checkpointer_ctx

    _checkpointer_ctx = AsyncPostgresSaver.from_conn_string(checkpoint_url)
    checkpointer = await _checkpointer_ctx.__aenter__()
    await checkpointer.setup()

    compiled_graph = build_graph(checkpointer)
    logger.info("LangGraph pipeline initialized")


async def shutdown_graph() -> None:
    """Close the checkpointer connection pool."""
    global compiled_graph, _checkpointer_ctx

    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
        _checkpointer_ctx = None
    compiled_graph = None
    logger.info("LangGraph pipeline shut down")
