"""S32 A1 · The judge drops no flag

Story: The helper judges an invented interview with a fallacy, a false figure and a disputed figure. The judge's
reading is offered only "keep" and "nitpick" and is told that it never drops a flag. When it still answers "drop" for
the disputed figure, as a provider that ignores the schema can, the flag file shows that figure as "keep" with the
judge's reason, and no flag says dropped.

Setup: the invented interview of s32_fakes and its flags. A fake judge LLM that keeps the fallacy, nitpicks the false
figure and answers "drop" for the disputed figure and for the self-contradiction. The helper's judge step, the one that
runs before the flag file says done.
"""
import json

from fact_checker.server import judged
from s32_fakes import DISPUTED_ID, FALLACY_ID, FALSE_ID, FLAGS, SELF_ID, FakeJudge, transcript

DROP_REASON = "Una medida creíble lo respalda."


def test_judge_drops_nothing():
    llm = FakeJudge({FALLACY_ID: ("keep", "El ataque es suyo y no argumenta.", None),
                     FALSE_ID: ("nitpick", "49,8 M frente a 49,4 M, el fondo se sostiene", None),
                     DISPUTED_ID: ("drop", DROP_REASON, None),
                     SELF_ID: ("drop", "Habla de otro impuesto.", None)})
    flags = {f["id"]: f for f in judged(FLAGS, transcript(), llm)}
    assert len(llm.calls) == 1

    # Case 1 · the judge's reading → offered only "keep" and "nitpick", and told it never drops a flag
    verdicts = llm.calls[0]["schema"]["properties"]["rulings"]["items"]["properties"]["verdict"]["enum"]
    assert sorted(verdicts) == ["keep", "nitpick"], verdicts
    prompt = llm.calls[0]["prompt"]
    assert '"drop"' not in prompt and "drop it" not in prompt and "is dropped" not in prompt
    assert "never drop" in prompt.lower(), "the prompt does not say that the judge never drops a flag"

    # Case 2 · the judge still answers "drop" for the disputed figure → "keep", with the judge's reason
    assert flags[DISPUTED_ID]["judge"]["verdict"] == "keep", flags[DISPUTED_ID]["judge"]
    assert flags[DISPUTED_ID]["judge"]["reason"] == DROP_REASON
    assert flags[DISPUTED_ID]["label"] == "disputed"

    # Case 3 · the whole file → no flag says dropped; keep and nitpick stay as ruled
    assert not [f for f in flags.values() if f.get("judge", {}).get("verdict") == "drop"], json.dumps(flags)
    assert flags[FALLACY_ID]["judge"]["verdict"] == "keep"
    assert flags[FALSE_ID]["judge"]["verdict"] == "nitpick"
    print("PASS S32 A1 · The judge drops no flag")
