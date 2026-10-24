import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from napolnenie.sources.mouser import MouserClient


SAMPLE_RESPONSE = {
    "Errors": [],
    "SearchResults": {
        "NumberOfResult": 1,
        "Parts": [
            {
                "MouserPartNumber": "81-ALC3248",
                "ManufacturerPartNumber": "ALC3248",
                "Manufacturer": "Realtek",
                "Description": "Audio Codec",
                "ImagePath": "https://www.mouser.com/images/test.jpg",
                "ProductDetailUrl": "https://www.mouser.com/ProductDetail/ALC3248",
            }
        ],
    },
}


def test_mouser_search_parses_image(tmp_path: Path):
    client = MouserClient(api_key="test-key", cache_dir=tmp_path, min_interval=0)

    resp = MagicMock()
    resp.read.return_value = json.dumps(SAMPLE_RESPONSE).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    mock_opener = MagicMock()
    mock_opener.open.return_value = resp

    with patch.object(client, "_build_opener", return_value=mock_opener):
        result = client.search_part("ALC3248")

    assert len(result.hits) == 1
    assert result.hits[0].image_url.endswith("test.jpg")
    assert result.search_mode == "Exact"
    assert Path(result.raw_cache_path).is_file()
