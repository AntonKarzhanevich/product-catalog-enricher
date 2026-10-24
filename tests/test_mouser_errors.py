from pathlib import Path

from napolnenie.sources.mouser import MouserClient

INVALID_KEY_RESPONSE = {
    "Errors": [
        {
            "Code": "Invalid",
            "Message": "Invalid unique identifier.",
            "PropertyName": "API Key",
        }
    ],
    "SearchResults": None,
}


def test_invalid_api_key_surfaces_error(tmp_path: Path):
    client = MouserClient(api_key="bad", cache_dir=tmp_path)
    err = client._api_error(INVALID_KEY_RESPONSE)
    assert "Search API" in err
    assert "Invalid" in err
