"""Node 7: assess_relevance — score how well the source supports the research goal."""

from ...database import repository as repo
from ...services.evaluator import assess_relevance
from ..state import ResearchState


async def node_assess_relevance(state: ResearchState) -> dict:
    url = state["current_url"]
    content = state.get("scraped_content", "")

    try:
        result = await assess_relevance(
            topic=state["topic"],
            research_goal=state["research_goal"],
            url=url,
            content_preview=content,
        )

        relevance_score = float(result.get("relevance_score", 0.0))
        key_findings = result.get("key_findings") or []

        # If the LLM already flagged it as irrelevant, discard immediately.
        if relevance_score < 0.4:
            rejection_reason = (
                result.get("rejection_reason") or "Relevance score below threshold"
            )
            await repo.create_discard(
                state["session_id"], url, rejection_reason, "relevance_assessment"
            )
            await repo.increment_session_counter(state["session_id"], "sources_discarded")
            return {
                "relevance_score": relevance_score,
                "current_url": None,
                "current_stage": "pick_url",
            }

        return {
            "relevance_score": relevance_score,
            "key_findings": key_findings,
            "current_stage": "apply_constraints",
        }

    except Exception as exc:  # noqa: BLE001
        err = {
            "stage": "evaluate",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "url": url,
        }
        await repo.create_error_log(
            state["session_id"], "evaluate", type(exc).__name__, str(exc), url=url
        )
        await repo.create_discard(
            state["session_id"], url, f"Relevance assessment failed: {exc}",
            "relevance_assessment",
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {"errors": [err], "current_url": None, "current_stage": "pick_url"}
