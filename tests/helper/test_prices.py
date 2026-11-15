"""Long prompts cost more on some models: the whole request takes the higher price once its prompt passes the bar."""
from pytest import approx

from fact_checker.core.prices import cost


def usage(fresh, read=0, out=0):
    return {"input_tokens": fresh, "cache_creation_input_tokens": 0, "cache_read_input_tokens": read,
            "output_tokens": out}


def test_haiku_prompt_over_100k_pays_five_times():
    assert cost("claude-haiku-5-5", usage(100_000, out=1_000_000)) == approx(0.01 + 0.50)
    # Cache reads count toward the prompt length.
    assert cost("claude-haiku-5-5", usage(1, read=100_000, out=1_000_000)) == approx((1 * 0.50 + 100_000 * 0.05) / 1e6 + 2.50)


def test_grok_prompt_at_200k_pays_double():
    assert cost("grok-4.7", usage(199_999)) == approx(199_999 * 2 / 1e6)
    assert cost("grok-4.7", usage(200_000, out=1_000_000)) == approx(0.8 + 12)


def test_grok_searches_have_no_published_price():
    assert cost("grok-4.7", usage(1_000), searches=3) is None
