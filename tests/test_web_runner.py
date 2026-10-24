from pathlib import Path
from unittest.mock import patch

from napolnenie.sources.base import ImageHit, SearchResult
from napolnenie.web_runner import run_web_search


def test_each_row_gets_own_search_and_file(tmp_path: Path):
    rows = [
        {
            "source_file": "t.xlsx",
            "row_num": "1",
            "group": "BGA чип и микросхема для ноутбуков",
            "series_raw": "88E8042, 0001",
            "query_sent": "88E8042",
        },
        {
            "source_file": "t.xlsx",
            "row_num": "2",
            "group": "BGA чип и микросхема для ноутбуков",
            "series_raw": "88E8042, 0002",
            "query_sent": "88E8042",
        },
    ]
    hit = ImageHit(
        query="x",
        image_url="https://example.com/88E8042.jpg",
        description="88E8042 chip",
    )
    sr = SearchResult(query="q", hits=[hit], search_mode="test")

    with patch("napolnenie.web_runner.DuckDuckGoImages") as mock_cls:
        mock_cls.return_value.search.return_value = sr
        with patch("napolnenie.web_runner.download_image", return_value=(True, "image/jpeg", 5000)):
            results = run_web_search(
                rows,
                out_dir=tmp_path,
                images_dir=tmp_path / "img",
                min_interval=0,
                download=True,
            )

    assert len(results) == 2
    assert mock_cls.return_value.search.call_count == 2
    assert results[0].local_path != results[1].local_path
    assert "r1_" in results[0].local_path
    assert "r2_" in results[1].local_path
