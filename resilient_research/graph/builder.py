"""
LangGraph graph builder.

"""

import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from ..config import settings
from ..database import repository as repo
from .edges import (
    route_from_authority,
    route_from_check_completion,
    route_from_constraints,
    route_from_metadata,
    route_from_pick_next_url,
    route_from_relevance,
    route_from_save,
    route_from_scrape,
)
from .nodes import (
    node_apply_constraints,
    node_assess_relevance,
    node_check_completion,
    node_extract_metadata,
    node_generate_queries,
    node_handle_error,
    node_log_discard,
    node_pick_next_url,
    node_save_artifact,
    node_score_authority,
    node_scrape_url,
    node_search_web,
)

from .state import ResearchState

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    """Assemble and return the uncompiled StateGraph."""
    builder: StateGraph = StateGraph(ResearchState)

    # ── Register all nodes ────────────────────────────────────────────────────
    builder.add_node("generate_queries", node_generate_queries)
    builder.add_node("search_web", node_search_web)
    builder.add_node("pick_next_url", node_pick_next_url)
    builder.add_node("scrape_url", node_scrape_url)
    builder.add_node("extract_metadata", node_extract_metadata)
    builder.add_node("score_authority", node_score_authority)
    builder.add_node("assess_relevance", node_assess_relevance)
    builder.add_node("apply_constraints", node_apply_constraints)
    builder.add_node("save_artifact", node_save_artifact)
    builder.add_node("log_discard", node_log_discard)
    builder.add_node("check_completion", node_check_completion)
    builder.add_node("handle_error", node_handle_error)

    # ── Entry point ───────────────────────────────────────────────────────────
    builder.set_entry_point("generate_queries")

    # ── Fixed edges ───────────────────────────────────────────────────────────
    builder.add_edge("generate_queries", "search_web")
    builder.add_edge("search_web", "pick_next_url")
    builder.add_edge("log_discard", "pick_next_url")
    builder.add_edge("handle_error", END)

    # ── Conditional edges ─────────────────────────────────────────────────────
    builder.add_conditional_edges(
        "pick_next_url",
        route_from_pick_next_url,
        {"scrape_url": "scrape_url", "check_completion": "check_completion"},
    )
    builder.add_conditional_edges(
        "scrape_url",
        route_from_scrape,
        {"extract_metadata": "extract_metadata", "pick_next_url": "pick_next_url"},
    )
    builder.add_conditional_edges(
        "extract_metadata",
        route_from_metadata,
        {"score_authority": "score_authority", "pick_next_url": "pick_next_url"},
    )
    builder.add_conditional_edges(
        "score_authority",
        route_from_authority,
        {"assess_relevance": "assess_relevance", "pick_next_url": "pick_next_url"},
    )
    builder.add_conditional_edges(
        "assess_relevance",
        route_from_relevance,
        {"apply_constraints": "apply_constraints", "pick_next_url": "pick_next_url"},
    )
    builder.add_conditional_edges(
        "apply_constraints",
        route_from_constraints,
        {"save_artifact": "save_artifact", "pick_next_url": "pick_next_url"},
    )
    builder.add_conditional_edges(
        "save_artifact",
        route_from_save,
        {"pick_next_url": "pick_next_url"},
    )
    builder.add_conditional_edges(
        "check_completion",
        route_from_check_completion,
        {
            "__end__": END,
            "search_web": "search_web",
        },
    )

    return builder


async def run_research_graph(session_id: str, initial_state: ResearchState) -> None:
    """
    Entry point for background graph execution (called via asyncio.create_task).

    Opens an AsyncSqliteSaver checkpointer tied to the same DB file as the
    rest of the application, compiles the graph, and runs it to completion.
    Interrupted sessions can be resumed by calling this function again with
    the same session_id — LangGraph restores from the last checkpoint.
    """
    config = {"configurable": {"thread_id": session_id}}

    try:
        async with AsyncSqliteSaver.from_conn_string(settings.database_path) as checkpointer:
            graph = _build_graph().compile(checkpointer=checkpointer)

            logger.info("[%s] Graph execution started.", session_id)
            async for event in graph.astream(initial_state, config=config):
                # events are dicts of {node_name: state_patch}; logging is
                # handled inside each node — no extra processing needed here.
                pass

            logger.info("[%s] Graph execution finished.", session_id)

    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Unhandled graph error: %s", session_id, exc)
        await repo.update_session_status(session_id, "failed")
