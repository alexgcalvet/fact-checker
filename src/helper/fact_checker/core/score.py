from fact_checker.core.pipeline import _norm

BARS = (0.5, 0.6, 0.7, 0.8, 0.9)
TARGET = 0.8
MIN_FLAGS = 5
OVERLAP = 0.5


def _words(text: str) -> set[str]:
    return {w for w in (_norm(x) for x in text.split()) if w}


def _matches(flag: dict, expected: dict) -> bool:
    if flag["type"] != expected["type"]:
        return False
    if flag["type"] == "fallacy" and flag["label"] != expected["label"]:
        return False
    want = _words(expected["quote"])
    return len(want & _words(flag["quote"])) >= OVERLAP * len(want)


def score(flags: list[dict], expected: list[dict], kind: str) -> tuple[list[tuple[float, bool]], int, int]:
    """(confidence, right) per flag of `kind`, the expected ones found, and the expected total."""
    open_expected = [e for e in expected if e["type"] == kind]
    total = len(open_expected)
    scored = []
    for flag in sorted((f for f in flags if f["type"] == kind), key=lambda f: -f["confidence"]):
        hit = next((e for e in open_expected if _matches(flag, e)), None)
        if hit:
            open_expected.remove(hit)
        scored.append((flag["confidence"], hit is not None))
    return scored, total - len(open_expected), total


def precision_recall(scored: list[tuple[float, bool]], total: int, bar: float = 0.0) -> tuple[float | None, float | None]:
    kept = [right for conf, right in scored if conf >= bar]
    precision = sum(kept) / len(kept) if kept else None
    recall = sum(kept) / total if total else None
    return precision, recall


def pick_bar(scored: list[tuple[float, bool]]) -> float | None:
    """The lowest confidence whose flags at or above it are right at least TARGET of the time."""
    if len(scored) < MIN_FLAGS:
        return None
    for conf in sorted({c for c, _ in scored}):
        precision, _ = precision_recall(scored, 1, conf)
        if precision is not None and precision >= TARGET:
            return conf
    return None
