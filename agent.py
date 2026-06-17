"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re
from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse the query with regex to extract description, size, max_price
    size_match = re.search(r"\bsize\s+([A-Za-z0-9/]+)", query, re.IGNORECASE)
    price_match = re.search(r"under\s+\$?(\d+(?:\.\d+)?)", query, re.IGNORECASE)

    size = size_match.group(1) if size_match else None
    max_price = float(price_match.group(1)) if price_match else None

    # Strip size and price tokens from the query to get a clean description
    description = re.sub(r"\bsize\s+[A-Za-z0-9/]+", "", query, flags=re.IGNORECASE)
    description = re.sub(r"under\s+\$?\d+(?:\.\d+)?", "", description, flags=re.IGNORECASE)
    description = re.sub(r"\$\d+(?:\.\d+)?", "", description)
    description = re.sub(r"\s+", " ", description).strip(" ,.")

    session["parsed"] = {
        "description": description,
        "size": size,
        "max_price": max_price,
    }

    # Step 3: call search_listings — early exit if nothing matches
    results = search_listings(description, size, max_price)
    session["search_results"] = results

    if not results:
        session["error"] = (
            "I couldn't find anything matching that"
            + (f" under ${int(max_price)}" if max_price else "")
            + " — try broadening your search term or raising your budget."
        )
        return session

    # Step 4: select the top result
    session["selected_item"] = results[0]

    # Step 5: call suggest_outfit — early exit if LLM silently returns empty
    outfit_suggestion = suggest_outfit(session["selected_item"], session["wardrobe"])

    if not outfit_suggestion or not outfit_suggestion.strip():
        session["error"] = (
            "I found the item but couldn't generate outfit ideas — try again in a moment."
        )
        return session

    session["outfit_suggestion"] = outfit_suggestion

    # Step 6: call create_fit_card
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a designer ballown under $5, size XXS",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"selected_item: {session['selected_item']}")
        print(f"\noutfit_suggestion going into fit card: {session['outfit_suggestion']}")
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")