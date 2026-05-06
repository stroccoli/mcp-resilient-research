"""
MCP Resource: research://knowledge-graph/{session_id}

Returns the curated knowledge graph for a completed research session.
Only includes sources that passed all evaluation gates.
"""

import json

from ..database import repository as repo


async def get_knowledge_graph(session_id: str) -> str:
    """
    Build and return the full knowledge graph as a JSON string.

    Each artifact entry includes:
      source_url, author, organization, country, publication_date,
      authority_level, confidence_score, key_findings, provenance_metadata.

    The top-level object also includes a summary with authority distribution
    and average confidence score — useful for a quick quality assessment.
    """
    session = await repo.get_session(session_id)
    if session is None:
        return json.dumps({"error": f"Session '{session_id}' not found."})

    artifacts = await repo.get_artifacts(session_id)

    high = sum(1 for a in artifacts if a["authority_level"] == "High")
    medium = sum(1 for a in artifacts if a["authority_level"] == "Medium")
    low = sum(1 for a in artifacts if a["authority_level"] == "Low")
    avg_confidence = (
        round(sum(a["confidence_score"] for a in artifacts) / len(artifacts), 4)
        if artifacts
        else 0.0
    )

    knowledge_graph = {
        "session_id": session_id,
        "topic": session["topic"],
        "research_goal": session["research_goal"],
        "status": session["status"],
        "summary": {
            "total_validated_sources": len(artifacts),
            "authority_distribution": {
                "High": high,
                "Medium": medium,
                "Low": low,
            },
            "average_confidence_score": avg_confidence,
        },
        "sources": [
            {
                "source_url": a["source_url"],
                "author": a["author"],
                "organization": a["organization"],
                "country": a["country"],
                "publication_date": a["publication_date"],
                "authority_level": a["authority_level"],
                "confidence_score": a["confidence_score"],
                "key_findings": a["key_findings"],
                "provenance_metadata": a["provenance_metadata"],
            }
            for a in artifacts
        ],
    }

    return json.dumps(knowledge_graph, ensure_ascii=False, indent=2)
