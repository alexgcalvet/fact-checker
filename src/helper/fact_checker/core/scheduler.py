import copy
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fact_checker.core.flags import Chunk, Segment, Transcript

FIRST = 30
STEP = 120
CONTEXT = 180  # seconds before a part that its short window holds
PARALLEL = 3
CALLS_PER_HOUR = 60
HORIZON = 600  # no part starts more than this many seconds after the playback second last heard
SILENCE = 60  # seconds with no poll from the extension before the analysis pauses


def _chunks(transcript: Transcript, bounds: list[tuple[float, float]]) -> list[Chunk]:
    out = []
    for start, end in bounds:
        segs = [s for s in transcript.segments if start <= s.t < end]
        if segs:
            out.append(Chunk(start=start, end=end, segments=segs))
    return out


def plan(transcript: Transcript, from_t: float) -> list[Chunk]:
    """Parts from the playback second forward (30 s, then 2 min), then the earlier part."""
    if not transcript.segments:
        return []
    last = transcript.segments[-1].t
    bounds = [(from_t, from_t + FIRST)]
    start = from_t + FIRST
    while start <= last:
        bounds.append((start, start + STEP))
        start += STEP
    start = 0
    while start < from_t:
        bounds.append((start, min(start + STEP, from_t)))
        start += STEP
    return _chunks(transcript, bounds)


class Viewer:
    """The playback second last heard from the extension, and when it was heard."""

    def __init__(self, t: float):
        self.moved = threading.Condition()
        self.t, self.heard = t, time.monotonic()

    def hear(self, t: float) -> None:
        with self.moved:
            self.t, self.heard = t, time.monotonic()
            self.moved.notify_all()


def _free(taken: list[tuple[float, float]], at: float) -> float:
    """The first second from `at` that no taken part holds."""
    while (cover := next((b for a, b in taken if a <= at < b), None)) is not None:
        at = cover
    return at


def _next_part(transcript: Transcript, taken: list[tuple[float, float]], at: float) -> tuple[float, float] | None:
    """The first part not taken from the playback second on (30 s when it starts there, else 2 min, cut where a
    taken part starts), or None when it would start past the horizon or the end of the video."""
    start = _free(taken, at)
    if start > at + HORIZON or start > transcript.segments[-1].t:
        return None
    return start, min([start + (FIRST if start == at else STEP), *(a for a, _ in taken if a > start)])


def follow(transcript: Transcript, viewer: Viewer, stop: threading.Event):
    """Parts from the playback second up to HORIZON ahead of it, as the viewer moves; it waits while no part is due or
    the viewer has been silent for SILENCE seconds. It ends once every part from the playback second to the end of
    the video is taken, so the stretches the viewer skipped stay unanalysed."""
    taken = []
    while transcript.segments and not stop.is_set():
        with viewer.moved:
            silent = time.monotonic() - viewer.heard > SILENCE
            bounds = None if silent else _next_part(transcript, taken, viewer.t)
            if bounds is None:
                if not silent and _free(taken, viewer.t) > transcript.segments[-1].t:
                    return
                viewer.moved.wait(1)
                continue
        taken.append(bounds)
        yield from _chunks(transcript, [bounds])


def context_before(transcript: Transcript, chunk: Chunk) -> list[Segment]:
    return [s for s in transcript.segments if chunk.start - CONTEXT <= s.t < chunk.start]


def budget(transcript: Transcript) -> int:
    duration = transcript.segments[-1].t if transcript.segments else 0
    return CALLS_PER_HOUR * max(1, math.ceil(duration / 3600))


class BudgetExceeded(Exception):
    pass


class BudgetedLLM:
    """Counts every Claude tool call and refuses the ones over the budget."""

    def __init__(self, llm, max_calls: int):
        self.llm = llm
        self._left = [max_calls]  # shared with the LLMs of `through`
        self._lock = threading.Lock()

    @property
    def left(self) -> int:
        return self._left[0]

    def through(self, llm) -> "BudgetedLLM":
        """Another LLM that spends this same budget."""
        other = copy.copy(self)
        other.llm = llm
        return other

    def complete(self, prompt: str, schema: dict, tools: tuple = ()) -> dict:
        with self._lock:
            if self._left[0] <= 0:
                raise BudgetExceeded()
            self._left[0] -= 1
        return self.llm.complete(prompt, schema, tools=tools) if tools else self.llm.complete(prompt, schema)


def run(chunks, work, on_done, stop: threading.Event | None = None) -> tuple[str, str | None]:
    """Runs `work(chunk)` on up to PARALLEL chunks at once, in the order `chunks` gives them; `on_done(chunk, result)`
    gets each result, one at a time. `chunks` may wait until its next part is due; a failure sets `stop`.

    Returns the final status and stop reason.
    """
    stop = stop or threading.Event()
    outcome = ["done", None]
    lock = threading.Lock()
    slots = threading.Semaphore(PARALLEL)

    def task(chunk):
        try:
            result = work(chunk)
            with lock:
                if not stop.is_set():
                    on_done(chunk, result)
        except Exception as e:
            with lock:
                if not stop.is_set():
                    outcome[:] = ["stopped", "budget" if isinstance(e, BudgetExceeded) else f"error: {e}"]
                    stop.set()
        finally:
            slots.release()

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        parts = iter(chunks)
        while True:
            slots.acquire()
            chunk = None if stop.is_set() else next(parts, None)
            if chunk is None:
                break
            pool.submit(task, chunk)
    return outcome[0], outcome[1]
