from pathlib import Path

from napolnenie.storage import clean_web_artifacts


def test_clean_web_artifacts(tmp_path: Path):
    out = tmp_path / "out"
    (out / "images" / "web").mkdir(parents=True)
    (out / "images" / "web" / "x.jpg").write_bytes(b"x")
    (out / "_cache" / "ddg").mkdir(parents=True)
    (out / "_cache" / "ddg" / "q.json").write_text("{}", encoding="utf-8")
    (out / "web_probe.csv").write_text("a", encoding="utf-8")

    removed = clean_web_artifacts(out)
    assert len(removed) == 3
    assert not (out / "web_probe.csv").exists()
    assert not (out / "images" / "web").exists()
