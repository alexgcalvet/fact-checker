"""The invented shared analysis that the S28 tests share."""

SHARED_VIDEO = "sharedv1"


def _flag(id, t, type, label, quote):
    return {"id": id, "t": t, "speaker": "Invitado", "quote": quote, "type": type, "label": label,
            "reason": "Motivo inventado.", "confidence": 0.9, "related": None,
            "sources": [{"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}]
            if type == "inaccuracy" else [], "note": None, "on_player": True,
            "judge": {"verdict": "keep", "reason": "Se sostiene."}}


# A whole Spanish analysis of an invented video, as a helper uploads it.
ANALYSIS = {
    "video_id": SHARED_VIDEO, "lang": "es", "spoken": "es", "status": "done", "published_at": "2026-11-10",
    "title": "Entrevista inventada", "channel": "Canal inventado", "duration": 23.0, "speakers": {},
    "readers": {"parts": {"provider": "claude", "model": "opus"}, "verdict": {"provider": "claude", "model": "opus"},
                "judge": {"provider": "claude", "model": "opus"}, "search": {"provider": "claude", "model": "sonnet"}},
    "cost_usd": 7.9, "analysed_until": 23.0, "helper_version": "0.1.0",
    "flags": [_flag("ad_hominem-3.0", 3.0, "fallacy", "ad_hominem", "mi rival es un mentiroso"),
              _flag("false-5.0", 5.0, "inaccuracy", "false", "el paro bajó a la mitad en un año")],
}
