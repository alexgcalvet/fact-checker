"""S32 A2 · A small slip of any kind becomes a "Puntualización"

Story: In the same interview, the judge rules "nitpick" on the fallacy ("el ataque es leve, lo matiza en la frase
siguiente") and on a self-contradiction. The flag file keeps both as "nitpick" with those reasons, so the player shows
them as grey "Puntualización" cards; each original label and reason is still there.

Setup: the invented interview of s32_fakes and its flags. A fake judge LLM that nitpicks the guest's fallacy and the
self-contradiction and keeps the rest. The helper's judge step, the one that runs before the flag file says done.
"""
from fact_checker.server import judged
from s32_fakes import FALLACY_ID, FLAGS, SELF_ID, FakeJudge, transcript

SOFT = "el ataque es leve, lo matiza en la frase siguiente"
RECONCILED = "lo explica ella: la subida fue temporal"


def test_nitpick_any_type():
    llm = FakeJudge({FALLACY_ID: ("nitpick", SOFT, None), SELF_ID: ("nitpick", RECONCILED, None)})
    flags = {f["id"]: f for f in judged(FLAGS, transcript(), llm)}
    found = {f["id"]: f for f in FLAGS}

    # Case 1 · a nitpick on a fallacy → stays "nitpick" with the judge's reason; label and reason as found
    fallacy = flags[FALLACY_ID]
    assert fallacy["judge"] == {"verdict": "nitpick", "reason": SOFT}, fallacy["judge"]
    assert (fallacy["label"], fallacy["reason"]) == ("ad_hominem", found[FALLACY_ID]["reason"])

    # Case 2 · a nitpick on a self-contradiction → stays "nitpick" with the judge's reason; label and reason as found
    contradiction = flags[SELF_ID]
    assert contradiction["judge"] == {"verdict": "nitpick", "reason": RECONCILED}, contradiction["judge"]
    assert (contradiction["label"], contradiction["reason"]) == ("self", found[SELF_ID]["reason"])
    print('PASS S32 A2 · A small slip of any kind becomes a "Puntualización"')
