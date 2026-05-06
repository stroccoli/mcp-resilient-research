"""
LLM-based source evaluator.

Three evaluation stages, each a separate LiteLLM call:
  1. extract_metadata  — author, org, country, date, content_type
  2. score_authority   — High / Medium / Low with numeric authority_score
  3. assess_relevance  — relevance_score 0–1, key_findings, optional rejection_reason

Composite confidence:
  confidence_score = AUTHORITY_WEIGHT * authority_score
                   + RELEVANCE_WEIGHT * relevance_score
"""

import json
import logging
from typing import Any

import litellm

from ..config import settings

logger = logging.getLogger(__name__)

# ── Evaluation prompts ────────────────────────────────────────────────────────

METADATA_EXTRACTION_PROMPT = """\
You are a metadata extraction assistant.

Given the web page URL and extracted text content below, identify structured metadata.

URL: {url}

CONTENT (first 3000 characters):
{content}

Respond with ONLY a valid JSON object matching this exact schema — no explanation, \
no markdown fences:
{{
  "author": "Full name or 'Unknown'",
  "organization": "Publisher, institution, or news outlet name — or 'Unknown'",
  "country": "ISO 3166-1 alpha-2 code (e.g. 'US', 'FR', 'DE') — or 'Unknown'",
  "publication_date": "ISO 8601 date string (e.g. '2023-05-01') — or 'Unknown'",
  "content_type": "One of: academic | government | news | blog | social | unknown"
}}"""

AUTHORITY_SCORING_PROMPT = """\
You are an authority assessment agent.

Evaluate the credibility and authority of the following web source.

URL: {url}
Author: {author}
Organization: {organization}
Content Type: {content_type}
Content Preview (first 2000 chars):
{content_preview}

Authority levels — choose ONE:
  High   — Peer-reviewed academic publications (.edu domains), official government sources
            (.gov, official national archives), UNESCO/UN documents, established academic
            institutions, primary source repositories.
  Medium — Established news organisations (Reuters, BBC, NYT, Le Monde, Der Spiegel,
            AP), recognised policy think tanks, well-sourced encyclopaedias
            (Encyclopædia Britannica, Wikipedia articles with inline citations).
  Low    — Personal blogs, social media profiles, unknown or self-published websites,
            user-generated content without verifiable authorship or citations.

Respond with ONLY a valid JSON object — no explanation, no markdown fences:
{{
  "authority_level": "High | Medium | Low",
  "authority_score": <float 0.0–1.0: High ≥ 0.75 | Medium 0.40–0.74 | Low < 0.40>,
  "reasoning": "One concise sentence justifying the classification."
}}"""

RELEVANCE_ASSESSMENT_PROMPT = """\
You are a relevance evaluation agent.

Assess how well the following source content supports the stated research goal.

RESEARCH TOPIC:  {topic}
RESEARCH GOAL:   {research_goal}

SOURCE URL: {url}
CONTENT PREVIEW (first 3000 chars):
{content_preview}

Instructions:
  • Score relevance from 0.0 (completely off-topic) to 1.0 (directly answers the goal).
  • If relevance_score >= 0.4 extract 3–5 concise key findings as bullet strings.
  • If relevance_score < 0.4 provide a short rejection_reason; key_findings may be [].

Respond with ONLY a valid JSON object — no explanation, no markdown fences:
{{
  "relevance_score": <float 0.0–1.0>,
  "key_findings": ["finding 1", "finding 2", "finding 3"],
  "rejection_reason": "Short reason if score < 0.4, otherwise null"
}}"""


# ── LiteLLM helpers ───────────────────────────────────────────────────────────

def _build_llm_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model": settings.litellm_model, "temperature": 0.0}
    if settings.litellm_api_base:
        kwargs["api_base"] = settings.litellm_api_base
    return kwargs


async def _call_llm(prompt: str) -> dict:
    """Send *prompt* to the configured LLM and parse the JSON response."""
    response = await litellm.acompletion(
        messages=[{"role": "user", "content": prompt}],
        **_build_llm_kwargs(),
    )
    raw: str = response.choices[0].message.content.strip()

    # Strip markdown code fences that some models add despite instructions.
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())


# ── Public evaluation functions ───────────────────────────────────────────────

async def extract_metadata(url: str, content: str) -> dict:
    """
    Return metadata dict with keys:
      author, organization, country, publication_date, content_type.
    """
    prompt = METADATA_EXTRACTION_PROMPT.format(url=url, content=content[:3000])
    return await _call_llm(prompt)


async def score_authority(
    url: str,
    author: str,
    organization: str,
    content_type: str,
    content_preview: str,
) -> dict:
    """
    Return authority dict with keys:
      authority_level (High/Medium/Low), authority_score (0–1), reasoning.
    """
    prompt = AUTHORITY_SCORING_PROMPT.format(
        url=url,
        author=author,
        organization=organization,
        content_type=content_type,
        content_preview=content_preview[:2000],
    )
    return await _call_llm(prompt)


async def assess_relevance(
    topic: str,
    research_goal: str,
    url: str,
    content_preview: str,
) -> dict:
    """
    Return relevance dict with keys:
      relevance_score (0–1), key_findings (list), rejection_reason (str | None).
    """
    prompt = RELEVANCE_ASSESSMENT_PROMPT.format(
        topic=topic,
        research_goal=research_goal,
        url=url,
        content_preview=content_preview[:3000],
    )
    return await _call_llm(prompt)


def compute_confidence_score(authority_score: float, relevance_score: float) -> float:
    """
    Weighted composite score (Further Consideration #3):
      confidence = 0.4 × authority_score + 0.6 × relevance_score

    Weights are read from settings so they can be tuned via env vars.
    """
    raw = settings.authority_weight * authority_score + settings.relevance_weight * relevance_score
    return round(raw, 4)
