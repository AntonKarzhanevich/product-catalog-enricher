from pathlib import Path
from unittest.mock import MagicMock, patch

from napolnenie.storage import download_mouser_image, mouser_referer_for


def test_mouser_referer_from_product_url():
    ref = mouser_referer_for(
        "https://www.mouser.de/ProductDetail/TI/CSD97374Q4M",
        "https://www.mouser.com/images/ti.jpg",
    )
    assert ref == "https://www.mouser.de/"


def test_download_mouser_image_passes_referer(tmp_path: Path):
    dest = tmp_path / "r1_TEST.jpg"
    fake = b"\xff\xd8\xff\xe0" + b"x" * 3000

    resp = MagicMock()
    resp.read.return_value = fake
    resp.headers = {"Content-Type": "image/jpeg"}
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    mock_opener = MagicMock()
    mock_opener.open.return_value = resp

    with patch("urllib.request.build_opener", return_value=mock_opener):
        ok, mime, nbytes = download_mouser_image(
            "https://www.mouser.com/images/test.jpg",
            dest,
            product_url="https://www.mouser.de/ProductDetail/x",
        )

    assert ok is True
    assert mime == "image/jpeg"
    assert nbytes >= 400
    assert dest.is_file()
    img_req = mock_opener.open.call_args_list[-1][0][0]
    assert img_req.get_full_url() == "https://www.mouser.com/images/test.jpg"
