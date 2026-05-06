"""Node 8: apply_constraints — gate artifact persistence against session constraints.

Constraint checks (in order):
  1. min_authority   — authority level must meet or exceed the configured minimum.
  2. allowed_countries — soft check: only enforced when country is positively
     identified (not 'Unknown'), to avoid discarding sources with missing metadata.
  3. min_confidence_score — composite score must meet the configured threshold.
"""

from ...config import settings
from ...database import repository as repo
from ...services.evaluator import compute_confidence_score
from ..state import ResearchState

_AUTHORITY_RANK: dict[str, int] = {"High": 3, "Medium": 2, "Low": 1}


async def node_apply_constraints(state: ResearchState) -> dict:
    url = state["current_url"]
    constraints = state["constraints"]
    authority_level = state.get("authority_level") or "Low"
    authority_score = state.get("authority_score") or 0.0
    relevance_score = state.get("relevance_score") or 0.0
    meta = state.get("extracted_metadata") or {}
    country = meta.get("country", "Unknown")

    confidence_score = compute_confidence_score(authority_score, relevance_score)

    # ── Constraint 1: min_authority ───────────────────────────────────────────
    min_auth = constraints.get("min_authority", "Low")
    if _AUTHORITY_RANK.get(authority_level, 0) < _AUTHORITY_RANK.get(min_auth, 1):
        reason = (
            f"Authority '{authority_level}' is below the required minimum '{min_auth}'"
        )
        await repo.create_discard(
            state["session_id"], url, reason, "constraint_check",
            authority_level=authority_level, confidence_score=confidence_score,
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {
            "confidence_score": confidence_score,
            "current_url": None,
            "current_stage": "pick_url",
        }

    # ── Constraint 2: allowed_countries (soft — skip when country is Unknown) ─
    allowed_countries = constraints.get("allowed_countries", [])
    if allowed_countries and country != "Unknown" and country not in allowed_countries:
        reason = (
            f"Country '{country}' is not in the allowed list {allowed_countries}. "
            "(Soft constraint: sources with unknown country are not filtered.)"
        )
        await repo.create_discard(
            state["session_id"], url, reason, "constraint_check",
            authority_level=authority_level, confidence_score=confidence_score,
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {
            "confidence_score": confidence_score,
            "current_url": None,
            "current_stage": "pick_url",
        }

    # ── Constraint 3: min_confidence_score ────────────────────────────────────
    if confidence_score < settings.min_confidence_score:
        reason = (
            f"Composite confidence score {confidence_score:.4f} is below the "
            f"minimum threshold {settings.min_confidence_score}"
        )
        await repo.create_discard(
            state["session_id"], url, reason, "constraint_check",
            authority_level=authority_level, confidence_score=confidence_score,
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {
            "confidence_score": confidence_score,
            "current_url": None,
            "current_stage": "pick_url",
        }

    return {"confidence_score": confidence_score, "current_stage": "save_artifact"}
