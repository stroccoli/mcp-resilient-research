"""Tool: get_discarded_logs"""

from ..database import repository as repo


async def get_discarded_logs(session_id: str) -> dict:
    """
    Return all rejected sources and their rejection details for a session.

    Returns:
        {
            session_id, total_discarded,
            discards: [{source_url, rejection_reason, rejection_stage,
                        authority_level, confidence_score, discarded_at}]
        }
    """
    session = await repo.get_session(session_id)
    if session is None:
        return {"error": f"Session '{session_id}' not found."}

    discards = await repo.get_discards(session_id)

    return {
        "session_id": session_id,
        "total_discarded": len(discards),
        "discards": [
            {
                "source_url": d["source_url"],
                "rejection_reason": d["rejection_reason"],
                "rejection_stage": d["rejection_stage"],
                "authority_level": d.get("authority_level"),
                "confidence_score": d.get("confidence_score"),
                "discarded_at": d["created_at"],
            }
            for d in discards
        ],
    }
