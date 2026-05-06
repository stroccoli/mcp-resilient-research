"""Tests for the LLM evaluator: prompt format, JSON parsing, score computation."""

import json
from unittest.mock import MagicMock

import pytest

from resilient_research.services.evaluator import (
    AUTHORITY_SCORING_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    RELEVANCE_ASSESSMENT_PROMPT,
    assess_relevance,
    compute_confidence_score,
    extract_metadata,
    score_authority,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_llm_response(content: dict):
    """Build an AsyncMock-compatible LiteLLM response object."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps(content)
    return mock_resp


def _make_fenced_response(content: dict):
    """LLM response wrapped in ```json ... ``` fences."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = f"```json\n{json.dumps(content)}\n```"
    return mock_resp


# ── Prompt placeholder tests ──────────────────────────────────────────────────

def test_metadata_extraction_prompt_placeholders():
    assert "{url}" in METADATA_EXTRACTION_PROMPT
    assert "{content}" in METADATA_EXTRACTION_PROMPT


def test_authority_scoring_prompt_placeholders():
    assert "{url}" in AUTHORITY_SCORING_PROMPT
    assert "{author}" in AUTHORITY_SCORING_PROMPT
    assert "{organization}" in AUTHORITY_SCORING_PROMPT
    assert "{content_type}" in AUTHORITY_SCORING_PROMPT
    assert "{content_preview}" in AUTHORITY_SCORING_PROMPT


def test_relevance_assessment_prompt_placeholders():
    assert "{topic}" in RELEVANCE_ASSESSMENT_PROMPT
    assert "{research_goal}" in RELEVANCE_ASSESSMENT_PROMPT
    assert "{url}" in RELEVANCE_ASSESSMENT_PROMPT
    assert "{content_preview}" in RELEVANCE_ASSESSMENT_PROMPT


# ── extract_metadata ──────────────────────────────────────────────────────────

async def test_extract_metadata_parses_response(mock_litellm):
    expected = {
        "author": "Marie Dupont",
        "organization": "CNRS",
        "country": "FR",
        "publication_date": "2021-06-15",
        "content_type": "academic",
    }
    mock_litellm.return_value = _make_llm_response(expected)

    result = await extract_metadata("https://cnrs.fr/article", "Some academic content...")

    assert result["author"] == "Marie Dupont"
    assert result["country"] == "FR"
    assert result["content_type"] == "academic"


async def test_extract_metadata_strips_markdown_fence(mock_litellm):
    """Some models return JSON wrapped in ```json ... ``` despite instructions."""
    expected = {
        "author": "Jane Smith",
        "organization": "MIT",
        "country": "US",
        "publication_date": "Unknown",
        "content_type": "academic",
    }
    mock_litellm.return_value = _make_fenced_response(expected)

    result = await extract_metadata("https://mit.edu/paper", "content")

    assert result["author"] == "Jane Smith"
    assert result["country"] == "US"


# ── score_authority ───────────────────────────────────────────────────────────

async def test_score_authority_high(mock_litellm):
    expected = {
        "authority_level": "High",
        "authority_score": 0.92,
        "reasoning": "Published on a .edu domain with peer-review markers.",
    }
    mock_litellm.return_value = _make_llm_response(expected)

    result = await score_authority(
        url="https://harvard.edu/history/paper",
        author="Prof. Jean Martin",
        organization="Harvard University",
        content_type="academic",
        content_preview="Peer-reviewed paper on the French Revolution...",
    )

    assert result["authority_level"] == "High"
    assert result["authority_score"] == pytest.approx(0.92)


async def test_score_authority_low(mock_litellm):
    expected = {
        "authority_level": "Low",
        "authority_score": 0.15,
        "reasoning": "Personal blog with no citations.",
    }
    mock_litellm.return_value = _make_llm_response(expected)

    result = await score_authority(
        url="https://myblog.wordpress.com/history",
        author="Unknown",
        organization="Unknown",
        content_type="blog",
        content_preview="Today I'm going to talk about history...",
    )

    assert result["authority_level"] == "Low"


# ── assess_relevance ──────────────────────────────────────────────────────────

async def test_assess_relevance_high_score(mock_litellm):
    expected = {
        "relevance_score": 0.87,
        "key_findings": [
            "The Estates-General convened in 1789.",
            "Economic inequality drove popular discontent.",
            "Enlightenment ideas influenced revolutionary leaders.",
        ],
        "rejection_reason": None,
    }
    mock_litellm.return_value = _make_llm_response(expected)

    result = await assess_relevance(
        topic="French Revolution",
        research_goal="Understand the main causes of the French Revolution",
        url="https://jstor.org/stable/fr-revolution-causes",
        content_preview="The French Revolution was triggered by...",
    )

    assert result["relevance_score"] == pytest.approx(0.87)
    assert len(result["key_findings"]) == 3
    assert result["rejection_reason"] is None


async def test_assess_relevance_low_score(mock_litellm):
    expected = {
        "relevance_score": 0.12,
        "key_findings": [],
        "rejection_reason": "Content is about the American Revolution, not the French Revolution.",
    }
    mock_litellm.return_value = _make_llm_response(expected)

    result = await assess_relevance(
        topic="French Revolution",
        research_goal="Understand causes of the French Revolution",
        url="https://example.com/american-revolution",
        content_preview="The American colonists declared independence in 1776...",
    )

    assert result["relevance_score"] == pytest.approx(0.12)
    assert "American Revolution" in result["rejection_reason"]


# ── compute_confidence_score ──────────────────────────────────────────────────

def test_compute_confidence_score_weighted():
    # 0.4 × 0.9 + 0.6 × 0.8 = 0.36 + 0.48 = 0.84
    score = compute_confidence_score(authority_score=0.9, relevance_score=0.8)
    assert score == pytest.approx(0.84, abs=1e-3)


def test_compute_confidence_score_zero():
    assert compute_confidence_score(0.0, 0.0) == pytest.approx(0.0)


def test_compute_confidence_score_perfect():
    assert compute_confidence_score(1.0, 1.0) == pytest.approx(1.0)


def test_compute_confidence_score_authority_only():
    # High authority, zero relevance: 0.4 × 1.0 + 0.6 × 0.0 = 0.4
    score = compute_confidence_score(authority_score=1.0, relevance_score=0.0)
    assert score == pytest.approx(0.4)
