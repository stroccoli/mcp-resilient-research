"""
Conditional edge routing functions for the research graph.

Each function receives the current ResearchState and returns the *name* of the
next node.  The names here must match the node names registered in builder.py.
"""

from .state import ResearchState


def route_from_pick_next_url(state: ResearchState) -> str:
    if state.get("current_url") is None:
        return "check_completion"
    return "scrape_url"


def route_from_scrape(state: ResearchState) -> str:
    if state.get("current_stage") == "extract_metadata":
        return "extract_metadata"
    return "pick_next_url"  # permanent failure or error → skip


def route_from_metadata(state: ResearchState) -> str:
    if state.get("current_url") is None:
        return "pick_next_url"
    return "score_authority"


def route_from_authority(state: ResearchState) -> str:
    if state.get("current_url") is None:
        return "pick_next_url"
    return "assess_relevance"


def route_from_relevance(state: ResearchState) -> str:
    if state.get("current_url") is None:
        return "pick_next_url"
    return "apply_constraints"


def route_from_constraints(state: ResearchState) -> str:
    if state.get("current_stage") == "save_artifact":
        return "save_artifact"
    return "pick_next_url"  # any constraint failure → skip


def route_from_save(state: ResearchState) -> str:
    # save_artifact always routes back to pick_next_url; the completion check
    # happens when pick_next_url finds an empty queue.
    return "pick_next_url"


def route_from_check_completion(state: ResearchState) -> str:
    stage = state.get("current_stage", "")
    if stage == "end":
        return "__end__"
    if stage == "search":
        return "search_web"
    # Fallback — should not reach here in normal flow.
    return "__end__"
