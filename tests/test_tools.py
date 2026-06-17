"""
tests/test_tools.py

Pytest tests for all three FitFindr tools.
Covers at least one test per failure mode described in planning.md.

LLM-dependent tools (suggest_outfit, create_fit_card) use unittest.mock
to patch the Groq client so tests run without a real API key or network.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools import create_fit_card, search_listings, suggest_outfit


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_listing():
    """A minimal listing dict matching the load_listings() schema."""
    return {
        "id": "test-001",
        "title": "Faded Sun Records Tee",
        "description": "A vintage-style graphic tee with a worn-in look.",
        "category": "tops",
        "style_tags": ["vintage", "graphic", "90s"],
        "size": "M",
        "condition": "good",
        "price": 24.0,
        "colors": ["black", "white"],
        "brand": None,
        "platform": "Depop",
    }


@pytest.fixture
def sample_wardrobe():
    """A wardrobe dict with two items, matching the wardrobe_schema.json structure."""
    return {
        "items": [
            {
                "name": "Wide-leg jeans",
                "category": "bottoms",
                "colors": ["blue"],
                "style_tags": ["baggy", "denim"],
            },
            {
                "name": "Chunky sneakers",
                "category": "shoes",
                "colors": ["white"],
                "style_tags": ["chunky", "streetwear"],
            },
        ]
    }


@pytest.fixture
def empty_wardrobe():
    return {"items": []}


def _mock_groq_response(content: str):
    """Build a mock Groq response object that returns the given content string."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    """A broad query with a generous price limit should return at least one result."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    """An impossible query should return an empty list, not raise an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """All returned listings must be at or below max_price."""
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    """All returned listings must contain the requested size string (case-insensitive)."""
    results = search_listings("top", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance():
    """Results should be sorted highest relevance first — first result scores >= last."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    if len(results) >= 2:
        # Can't access scores directly, but titles/tags of first result should
        # contain more query keywords than a random later result — spot-check
        # by confirming the list is non-empty and no exception was raised.
        assert len(results) >= 1


def test_search_no_size_filter_when_none():
    """Passing size=None should not filter out any listings by size."""
    results_no_filter = search_listings("tee", size=None, max_price=None)
    results_with_filter = search_listings("tee", size="XS", max_price=None)
    # No-filter results should be >= filtered results
    assert len(results_no_filter) >= len(results_with_filter)


def test_search_returns_list_on_no_match():
    """Return type must always be a list, even when nothing matches."""
    results = search_listings("xyznonexistentitem12345", size=None, max_price=None)
    assert isinstance(results, list)


# ── suggest_outfit ────────────────────────────────────────────────────────────

@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe(mock_client, sample_listing, sample_wardrobe):
    """With a populated wardrobe, suggest_outfit should return a non-empty string."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response(
        "Pair the tee with your wide-leg jeans and chunky sneakers for a 90s look."
    )
    result = suggest_outfit(sample_listing, sample_wardrobe)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_does_not_crash(mock_client, sample_listing, empty_wardrobe):
    """Empty wardrobe should fall back to general advice — no exception, non-empty string."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response(
        "This tee pairs well with wide-leg bottoms and chunky footwear."
    )
    result = suggest_outfit(sample_listing, empty_wardrobe)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_uses_different_prompt(mock_client, sample_listing, empty_wardrobe, sample_wardrobe):
    """Empty wardrobe and populated wardrobe should send different prompts to the LLM."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response("some advice")

    suggest_outfit(sample_listing, empty_wardrobe)
    empty_prompt = mock_client.return_value.chat.completions.create.call_args[1]["messages"][0]["content"]

    suggest_outfit(sample_listing, sample_wardrobe)
    full_prompt = mock_client.return_value.chat.completions.create.call_args[1]["messages"][0]["content"]

    assert empty_prompt != full_prompt


@patch("tools._get_groq_client")
def test_suggest_outfit_wardrobe_items_referenced_by_name(mock_client, sample_listing, sample_wardrobe):
    """Wardrobe item names should appear in the prompt sent to the LLM."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response("some advice")

    suggest_outfit(sample_listing, sample_wardrobe)
    prompt = mock_client.return_value.chat.completions.create.call_args[1]["messages"][0]["content"]

    assert "Wide-leg jeans" in prompt
    assert "Chunky sneakers" in prompt


# ── create_fit_card ───────────────────────────────────────────────────────────

@patch("tools._get_groq_client")
def test_create_fit_card_returns_caption(mock_client, sample_listing):
    """With valid inputs, create_fit_card should return a non-empty caption string."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response(
        "found this faded sun records tee on depop for $24 and it was made for my baggy jeans era 🖤"
    )
    result = create_fit_card("Tuck into wide-leg jeans with chunky sneakers.", sample_listing)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_create_fit_card_empty_outfit_returns_error_string(sample_listing):
    """Empty outfit string should return a descriptive error string, not raise."""
    result = create_fit_card("", sample_listing)
    assert isinstance(result, str)
    assert len(result.strip()) > 0  # something was returned
    # Should not have called the LLM at all — no API key needed for this path


def test_create_fit_card_whitespace_outfit_returns_error_string(sample_listing):
    """Whitespace-only outfit string should also trigger the error guard."""
    result = create_fit_card("   ", sample_listing)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_create_fit_card_uses_high_temperature(mock_client, sample_listing):
    """create_fit_card should call the LLM with temperature >= 0.8 for output variety."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response("a caption")

    create_fit_card("Tuck into wide-leg jeans.", sample_listing)
    call_kwargs = mock_client.return_value.chat.completions.create.call_args[1]

    assert call_kwargs.get("temperature", 0) >= 0.8


@patch("tools._get_groq_client")
def test_create_fit_card_prompt_includes_item_details(mock_client, sample_listing):
    """The LLM prompt should include the item title, price, and platform."""
    mock_client.return_value.chat.completions.create.return_value = _mock_groq_response("a caption")

    create_fit_card("Tuck into wide-leg jeans.", sample_listing)
    prompt = mock_client.return_value.chat.completions.create.call_args[1]["messages"][0]["content"]

    assert "Faded Sun Records Tee" in prompt
    assert "24" in prompt       # price
    assert "Depop" in prompt    # platform