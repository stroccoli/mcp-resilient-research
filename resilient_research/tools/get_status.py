"""Tool: get_research_status"""

from ..database import repository as repo


async def get_research_status(session_id: str) -> dict:
    """
    Return a progress report for a research session.

    Returns:
        {
            session_id, status, topic, sources_found,
            sources_validated, sources_discarded,
            created_at, updated_at,
            errors: [{stage, error_type, message}]  # capped at 10
        }
    """
    session = await repo.get_session(session_id)
    if session is None:
        return {"error": f"Session '{session_id}' not found."}

    error_logs = await repo.get_error_logs(session_id)
    error_summary = [
        {
            "stage": e["stage"],
            "error_type": e["error_type"],
            "message": e["error_message"],
            "url": e.get("url"),
            "retry_count": e.get("retry_count", 0),
        }
        for e in error_logs[:10]
    ]

    return {
        "session_id": session_id,
        "status": session["status"],
        "topic": session["topic"],
        "sources_found": session["sources_found"],
        "sources_validated": session["sources_validated"],
        "sources_discarded": session["sources_discarded"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "errors": error_summary,
    }
