"""The invented interviews that the S36 tests share, and the helper that runs `fact-checker compare` on them.

`interview()` builds a flag file as the helper keeps it: one host "Presentador", one guest, the guest's checked claims
and questions, and the guest's flags, all kept by the judge with no mark. Each interview also holds a serious flag of
the guest that the person marks unfair (UNFAIR_QUOTE) and a serious flag of the host: neither counts in any column.
MARTA, JORGE and NURIA are the three interviews of the board «La entrevista de las 9». Every name, quote and figure is
invented.
"""
import sys

from fact_checker import cli, server
from fact_checker.store import Store

HOST = "Presentador"
UNFAIR_QUOTE = "esto lo dicen todos los estudios serios"
HOST_QUOTE = "usted nunca contesta a nada de lo que le pregunto"


def numbered_flag(n, speaker, type, label, verdict="keep", severity=None):
    judge = {"verdict": verdict, "reason": "Regla inventada."} | ({"severity": severity} if severity else {})
    return {"id": f"{label}-{n}", "t": 60.0 * n, "speaker": speaker, "quote": f"frase inventada {n}", "type": type,
            "label": label, "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "note": None,
            "on_player": True, "judge": judge,
            "sources": [{"publisher": "INE", "url": "https://example.org/fuente", "date": "2026-10-01"}]
            if type == "inaccuracy" else []}


def interview(video_id, guest, person, *, spoken_s, claims, asked, false, misleading, nitpicks, serious, device,
              repeats, dodged, other_device=None, published_at="2026-10-14", title="La entrevista de las 9",
              voices=True):
    """One interview of `guest`. The first `serious` figures (false first) are serious; when there are fewer figures,
    the rest of the serious flags are uses of `device`. Without `voices` the file has no `people` and no host."""
    labels = ["false"] * false + ["misleading"] * misleading
    flags = [numbered_flag(i, guest, "inaccuracy", label, severity="serious" if i < serious else "moderate")
             for i, label in enumerate(labels)]
    n = len(flags)
    flags += [numbered_flag(n + i, guest, "inaccuracy", "false", verdict="nitpick") for i in range(nitpicks)]
    n = len(flags)
    flags += [numbered_flag(n + i, guest, "fallacy", device, severity="serious" if len(labels) + i < serious else "minor")
              for i in range(repeats)]
    if other_device:
        flags.append(numbered_flag(len(flags), guest, "fallacy", other_device, severity="minor"))
    n = len(flags)
    flags += [numbered_flag(n + i, guest, "question", "dodged", severity="minor") for i in range(dodged)]
    unfair = numbered_flag(len(flags), guest, "fallacy", device, severity="serious") | {"quote": UNFAIR_QUOTE}
    flags.append(unfair)
    data = {"video_id": video_id, "published_at": published_at, "status": "done", "stop_reason": None, "lang": "es",
            "spoken": "es", "title": title, "channel": "Canal inventado", "duration": spoken_s + 1200.0,
            "claims": {guest: claims}, "questions": {guest: asked}}
    if voices:
        flags.append(numbered_flag(len(flags), HOST, "fallacy", "ad_hominem", severity="serious") | {"quote": HOST_QUOTE})
        data |= {"speakers": {"SPEAKER_00": HOST, "SPEAKER_01": guest},
                 "people": {HOST: {"role": "host", "person": HOST, "spoken_s": 1200, "set_by": "llm"},
                            guest: {"role": "guest", "spoken_s": spoken_s, "set_by": "llm"}
                            | ({"person": person} if person else {})}}
    else:
        data |= {"speakers": {}}
    return data | {"flags": flags}, {unfair["id"]: "unfair"}


# Marta Ibarra: 41 min, 26 figures (2 false, 4 misleading, 3 puntualizaciones, 17 correct), 3 serious,
# "Datos a conveniencia" ×4, 2 of 11 questions dodged.
MARTA = interview("marta36", "Marta Ibarra (invitada)", "Marta Ibarra", spoken_s=2460, claims=26, asked=11, false=2,
                  misleading=4, nitpicks=3, serious=3, device="cherry_picking", repeats=4, other_device="ad_hominem",
                  dodged=2, published_at="2026-10-14")
# Jorge Salcedo: 52 min, 31 figures (1 false, 2 misleading, 4 puntualizaciones, 24 correct), 2 serious,
# "Y tú más" ×5, 4 of 12 questions dodged.
JORGE = interview("jorge36", "Jorge Salcedo (invitado)", "Jorge Salcedo", spoken_s=3120, claims=31, asked=12, false=1,
                  misleading=2, nitpicks=4, serious=2, device="tu_quoque", repeats=5, dodged=4,
                  published_at="2026-10-28")
# Núria Vidal: 47 min, 21 figures (3 false, 3 misleading, 2 puntualizaciones, 13 correct), 4 serious,
# "Apelación al miedo" ×3, 1 of 10 questions dodged.
NURIA = interview("nuria36", "Núria Vidal (invitada)", "Núria Vidal", spoken_s=2820, claims=21, asked=10, false=3,
                  misleading=3, nitpicks=2, serious=4, device="appeal_to_fear", repeats=3, dodged=1,
                  published_at="2026-11-04")


def save(home, *interviews) -> None:
    store = Store(home)
    for data, marks in interviews:
        store.save(data)
        for f in data["flags"]:
            if f["id"] in marks:
                store.add_mark(data["video_id"], f, marks[f["id"]], "", shared=False)


def compare(home, out, monkeypatch, capsys, *args, thumbnail=None) -> tuple[int, str]:
    """Runs `fact-checker compare <args>` in `out` with the helper home `home`, `thumbnail` for every video and a screenshot
    that returns the HTML of the card instead of a PNG. Returns the exit code and what the command printed."""
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.chdir(out)
    monkeypatch.setattr(server, "thumbnail", lambda video_id, home: thumbnail)
    monkeypatch.setattr(server, "screenshot", lambda html, *a, **k: html.encode())
    monkeypatch.setattr(sys, "argv", ["fact-checker", "compare", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as stop:
        code = stop.code if isinstance(stop.code, int) else 1
    printed = capsys.readouterr()
    return code, printed.out + printed.err


def column(card: str, name: str, names: list[str]) -> str:
    """The visible text of the column of `name`: from its name to the next person's name, or to the legend."""
    start = card.index(name)
    ends = [card.index(other, start) for other in names if other != name and other in card[start:]]
    return card[start:min(ends + [card.index("Correcto", start)])]
