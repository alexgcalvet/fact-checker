"""Dollar prices of the API models, read from the vendors' pricing pages on 2026-11-15.

Per million tokens: new input, five-minute cache write, cache read, output. A model missing here has no cost.
xAI bills no cache write, so its write price is the input price.
"""
PER_MILLION = {
    "claude-opus-5-5": (4, 5, 0.20, 20),
    "claude-sonnet-5-5": (2, 2.50, 0.10, 10),
    "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50),
    "gpt-6-astra": (10, 10, 1, 50),
    "gpt-6-luna": (0.10, 0.10, 0.01, 0.50),
    "gpt-5.5": (5, 5, 0.50, 30),
    "gpt-5.4-mini": (0.75, 0.75, 0.075, 4.50),
    "grok-4.7": (2, 2, 0.50, 6),
    "grok-4.6": (2, 2, 0.50, 6),
    "grok-4.5": (2, 2, 0.30, 6),
    "grok-4.3": (1.25, 1.25, 0.20, 2.50),
}
# A request whose prompt (new, written and read tokens) reaches the bar pays every price times the factor.
LONG_PROMPT = {"claude-haiku-5-5": (100_001, 5), **{m: (200_000, 2) for m in PER_MILLION if m.startswith("grok-")}}
# Per web search, by vendor: $10 per 1,000 at Anthropic and OpenAI. xAI publishes no search price.
PER_SEARCH = {"claude": 0.01, "gpt": 0.01}


def cost(model: str, usage: dict, searches: int = 0) -> float | None:
    """The dollar cost of one request, from its usage in the log's token fields; None for a price that is not known."""
    vendor = model.split("-")[0]
    if model not in PER_MILLION or (searches and vendor not in PER_SEARCH):
        return None
    fresh, write, read, out = PER_MILLION[model]
    prompt = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
    bar, factor = LONG_PROMPT.get(model, (0, 1))
    scale = factor if bar and prompt >= bar else 1
    return scale * (usage["input_tokens"] * fresh + usage["cache_creation_input_tokens"] * write
                    + usage["cache_read_input_tokens"] * read + usage["output_tokens"] * out) / 1e6 \
        + searches * PER_SEARCH.get(vendor, 0)
