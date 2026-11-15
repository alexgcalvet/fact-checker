"""S32 A3 · A speaker fix rules out an unfair flag in the marks check

Story: The person runs `fact-checker judge <video id> --against-marks` on an invented analysed interview. They marked
unfair one flag that gives the host's words to the guest, and marked two flags correct. The judge gives the unfair one
to the host and keeps the other two. The check prints "marked unfair, nitpicked or given to another speaker: 1 of 1"
and "marked correct, touched: 0 of 2".

Setup: a temporary helper home with the flag file of the invented interview of s32_fakes and three marks: the host's
reproach given to the guest unfair, the guest's fallacy and the false figure correct. A fake YouTube that serves the
interview, no speech engine, and a fake judge LLM in place of the provider: it gives the reproach to "Presentadora"
and keeps the fallacy and the false figure.
"""
import json

from fact_checker import cli, server
from s32_fakes import FALLACY_ID, FALSE_ID, FLAGS, REPROACH_ID, FakeJudge, transcript

VIDEO = "entrevista-inventada"


class FakeYouTube:
    def __init__(self, workdir, speech=None):
        pass

    def fetch(self, video_id):
        return transcript()


def test_marks_speaker_fix(tmp_path, monkeypatch, capsys):
    (tmp_path / "videos").mkdir()
    tr = transcript()
    (tmp_path / "videos" / f"{VIDEO}.json").write_text(json.dumps(
        {"video_id": VIDEO, "status": "done", "speakers": tr.speakers, "lang": "es", "flags": FLAGS}))
    (tmp_path / "marks.jsonl").write_text("".join(
        json.dumps({"video_id": VIDEO, "flag_id": i, "verdict": v}) + "\n"
        for i, v in ((REPROACH_ID, "unfair"), (FALLACY_ID, "correct"), (FALSE_ID, "correct"))))
    llm = FakeJudge({REPROACH_ID: ("keep", "Lo dice la presentadora.", "Presentadora"),
                     FALLACY_ID: ("keep", "El ataque es suyo.", None),
                     FALSE_ID: ("keep", "La cifra es otra.", None)})
    monkeypatch.setattr(cli, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "speech_cli", lambda: None)
    monkeypatch.setattr(server, "provider_llm", lambda home, name, **options: llm)

    cli.run_judge(VIDEO, tmp_path, against_marks=True)
    out = capsys.readouterr().out
    saved = {f["id"]: f for f in json.loads((tmp_path / "videos" / f"{VIDEO}.json").read_text())["flags"]}

    # Case 1 · the unfair flag given to the host → written to the file and counted as ruled out
    assert saved[REPROACH_ID]["judge"]["speaker"] == "Presentadora"
    assert "marked unfair, nitpicked or given to another speaker: 1 of 1" in out, out

    # Case 2 · the two flags marked correct and kept as found → not touched
    assert "marked correct, touched: 0 of 2" in out, out
    print("PASS S32 A3 · A speaker fix rules out an unfair flag in the marks check")
