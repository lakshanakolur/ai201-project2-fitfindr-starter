# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset from `listings.json` for secondhand items that match what the user is looking for. It filters by price and size if those were provided, then scores the remaining listings by how well they match the description keywords. Items with no keyword overlap get dropped entirely.

**Input parameters:**

- `description` (str): Keywords describing what the user wants, e.g. "vintage graphic tee" or "floral midi skirt". Used to score listings by overlap against title, description, and style_tags.
- `size` (str | None): Size string to filter by, e.g. "M" or "S/M". Matching is case-insensitive. Pass None to skip size filtering or if not provided in prompt.
- `max_price` (float | None): The highest price the user is willing to pay, inclusive. Pass None to skip price filtering or if nothing is provided into prompt.

**What it returns:**
A list of listing dicts sorted by relevance score, highest first. Each dict has: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list of str), `size` (str), `condition` (str), `price` (float), `colors` (list of str), `brand` (str), `platform` (str). Returns an empty list if nothing matches — does not raise.

**What happens if it fails or returns nothing:**
If the list is empty, the agent sets an error message and returns early without calling the next tool. It tells the user something like: "I couldn't find anything matching that under $30 — try raising your budget a bit or broadening the search term (e.g. 'graphic tee' instead of 'vintage graphic tee')."

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Takes the top item from tool 1 and their existing wardrobe, then uses an LLM to suggest 1–2 complete outfits. If the wardrobe is empty it falls back to general styling advice for that item type instead.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A single listing dict from `search_listings` — the item the user is thinking about buying. Used to tell the LLM what the piece looks like, its style tags, colors, and category.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each item has fields like `title`, `category`, `colors`, and `style_tags`. May be empty from `wardrobe_schema.json`


**What it returns:**
<!-- Describe the return value -->
A non-empty string with outfit suggestions. If the wardrobe has items, suggestions reference specific pieces by name (e.g. "your wide-leg jeans"). If the wardrobe is empty, the response is more general (e.g. "this tee pairs well with baggy bottoms and chunky footwear").

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
The function always returns a string — if the wardrobe is empty it switches to a general styling prompt rather than crashing. If the LLM call fails and returns an empty string, the agent skips `create_fit_card` and surfaces a message: "I found the item but couldn't generate outfit ideas — try again in a moment."

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generates a short, shareable caption for the thrifted item. Reads like something you'd actually post on Instagram or TikTok — casual, specific, and different every time.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Used to give the LLM context for the vibe and specific pieces in the look.
- `new_item` (dict): The listing dict for the item being captioned. The LLM pulls `title`, `price`, and `platform` from here to mention them naturally in the caption.

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence string written in casual first-person, e.g. "found this faded band tee on depop for $22 and it was made for my wide-legs untucked with a flannel and chunky sneakers, full look in stories." Sounds different each time because the LLM runs at higher temperature.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If `outfit` is empty or whitespace-only, the function returns a descriptive error string without raising. The agent shows that message and skips the caption rather than crashing.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->
N/A

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The agent runs a linear loop with early exits — it doesn't retry or reorder tools, it just stops and explains if something goes wrong.

1. Parse the user's message to extract `description`, `size` (optional), and `max_price` (optional). These become the inputs to `search_listings`.

2. Call `search_listings(description, size, max_price)`. Check if `results` is empty. If yes, make sure it logs error and gives out a no-results message and return early — nothing else runs. If no, keep in mind the top result and continue.

3. Call `suggest_outfit(session["selected_item"], session["wardrobe"])`. Check if the returned string is empty or whitespace. If yes, set `session["error"]` to the outfit-generation failure message and return early — `create_fit_card` does not run. If no, set `session["outfit_suggestion"]` to the returned string and continue.

4. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. Set `session["fit_card"]` to the result.

5. Return the full session to the response layer, which formats and displays `selected_item`, `outfit_suggestion`, and `fit_card` to the user.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
Each tool's output gets stored in a session dict that gets passed forward. Nothing is recomputed — each tool reads from what the previous one wrote.

- After `search_listings`: `session["selected_item"]` = `results[0]`
- After `suggest_outfit`: `session["outfit_suggestion"]` = the returned string
- After `create_fit_card`: `session["fit_card"]` = the returned caption
- On any early exit: `session["error"]` = the relevant message, and the loop returns immediately

The wardrobe is loaded once at startup (or extracted from the user's message) and lives in `session["wardrobe"]` for the duration of the interaction.

---

## Error Handling

| Tool              | Failure mode                          | Agent response |
| ----------------- | ------------------------------------- | -------------- |
| `search_listings`  | Returns an empty list — no listings matched the description, size, or price filters | Tell the user nothing was found and suggest adjusting the search: "No results for that under $30 — try a broader term or raise your max price." Stop the loop here. |
| `suggest_outfit`   | Wardrobe is empty — user gave no style context | Don't crash. Switch to a general styling prompt and return advice like "This type of tee pairs well with wide-leg bottoms and chunky sneakers." Continue to `create_fit_card`. |
| `create_fit_card` | Defensive guard only — `outfit` should never be empty in normal flow, but if the LLM call in `suggest_outfit` silently fails and returns `""` instead of raising, this catches it | Return a descriptive error string without raising. Agent shows the item but skips the caption and notes it couldn't be generated. |


---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

User query

│

▼

Planning Loop

│

├─► search_listings(description, size, max_price)

│       │

│       ├── results=[] ──► [STOP] "No results found. Try broadening your search."

│       │

│       │ results=[item, ...]

│       ▼

│   session["selected_item"] = results[0]

│       │

├─► suggest_outfit(selected_item, wardrobe)

│       │

│       ├── wardrobe empty ──► general styling advice (no crash, continue)

│       │

│       ├── LLM silently returns "" ──► [STOP] "Couldn't generate outfit ideas, try again."

│       │

│       │ returns outfit string

│       ▼

│   session["outfit_suggestion"] = outfit string

│       │

└─► create_fit_card(outfit_suggestion, selected_item)

│

├── outfit="" (defensive) ──► return error string, skip caption

│

│ returns caption string

▼

session["fit_card"] = caption

│

▼

Return session → display item + outfit + caption to user

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

For search_listings, I'll give Claude the Tool 1 block from this file (inputs, return value, failure mode) plus the load_listings() docs, and ask it to implement the function. Before using the output I'll check that it filters by all three parameters independently, scores by keyword overlap against title/description/style_tags, drops zero-score results, and returns an empty list (not an exception) when nothing matches. I'll test it with at least three queries: one that returns results, one with a tight price filter that should return nothing, and one with a size that doesn't exist.

For suggest_outfit, I'll give Claude the Tool 2 block and the wardrobe schema, and ask it to implement both branches (empty wardrobe vs populated wardrobe). I'll verify the empty wardrobe case explicitly by passing `{"items": []}` and confirming it still returns a non-empty string.

For create_fit_card, I'll give Claude the Tool 3 block and ask it to implement the caption generator with the defensive guard against empty outfit. I'll verify the guard by passing `""` and checking it returns an error string without raising.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop and State Management sections from this file plus the Architecture diagram, and ask it to implement the loop in agent.py. I'll verify by tracing through the diagram manually — checking that an empty earch_listings result exits early, that suggest_outfit with an empty wardrobe still continues, and that the session dict has the right keys after each step. I'll run the full loop with the example query from the walkthrough and compare the output to the Final Output section.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The user mentioned a specific item and a price ceiling, so the agent goes straight to search. No size was given so that filter gets skipped.

The agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`. It loads all listings, checks price < $30, checks which ones have similarity to "vintage graphic tee", and returns matches sorted by relevanc/closest similarity score.

Returned: `[{"title": "Faded Sun Records Tee", "price": 24.0, "size": "M/L", "platform": "Depop", "condition": "Good", "style_tags": ["vintage", "graphic"], ...}, ...]`

If this comes back empty, the agent stops here and tells the user what to adjust — something like "Nothing matched under $30 right now, try raising your budget or broadening to 'graphic tee' or 'band tee'." It doesn't call `suggest_outfit` if result is empty.

**Step 2:**
Step 1 returned at least one result, so now the agent takes the top listing and pairs it with the wardrobe context the user already gave (baggy jeans, chunky sneakers).

The agent calls `suggest_outfit(new_item=<Faded Sun Records Tee dict>, wardrobe=<wardrobe with baggy jeans + chunky sneakers>)`. It formats those wardrobe pieces into an LLM prompt and asks for specific outfit combinations.

Returned: `"Tuck the front of the tee into your wide-leg jeans and add chunky sneakers for a clean 90s look."`

If the wardrobe is empty because the user gave no style context, the tool doesn't crash — it falls back to a standard wardrobe template for the item type instead. Either way it returns a string and the agent moves on does not crash and does not stop.

**Step 3:**
Step 2 returned a result (custom or standard), so the agent now has everything it needs for a caption — the item details and the outfit description.

The agent calls `create_fit_card(outfit=<suggestion from Step 2>, new_item=<Faded Sun Records Tee dict>)`. It prompts the LLM for a casual 2–3 sentence caption that mentions the item name, price, and platform.

Returned: `"found this faded sun records tee on depop for $24 and it was literally made for my baggy jeans era 🖤 untucked with a flannel and chunky sneakers and i'm never taking it off"`

If `outfit` came in empty or whitespace-only, the tool returns a descriptive error string instead of raising. The agent shows that message and skips the caption rather than crashing.

**Final output to user:**
Here's what I found: Faded Sun Records Tee — $24, Depop, Good condition.

How to style it: Tuck the front into your wide-leg jeans and add chunky sneakers for a 90s-inspired look. Or leave it untucked with an open flannel for a looser, grungier fit.

Caption it: "found this faded sun records tee on depop for $24 and it was literally made for my baggy jeans era 🖤"
