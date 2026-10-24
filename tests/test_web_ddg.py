from pathlib import Path
from unittest.mock import MagicMock, patch

from napolnenie.sources.web_ddg import DuckDuckGoImages


def test_ddg_search_parses_hits(tmp_path: Path):
    client = DuckDuckGoImages(cache_dir=tmp_path, min_interval=0)

    fake_items = [
        {"image": "https://example.com/a.jpg", "title": "chip photo", "url": "https://x.com"},
    ]

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = lambda s: s
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.images.return_value = iter(fake_items)

    with patch("napolnenie.sources.web_ddg.DDGS", return_value=mock_ddgs):
        result = client.search("ALC3248 BGA")

    assert len(result.hits) == 1
    assert result.hits[0].image_url.endswith("a.jpg")
    assert Path(result.raw_cache_path).is_file()
