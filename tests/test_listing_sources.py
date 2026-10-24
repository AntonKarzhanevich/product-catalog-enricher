from pathlib import Path
from unittest.mock import patch

import pytest

from napolnenie.sources.listing_base import (
    SourceContext,
    is_product_photo_url,
    keys_match_text,
    match_keys,
)
from napolnenie.sources.chipsetpro import ChipsetproSource
from napolnenie.sources.dfi import DfiSource
from napolnenie.sources.theretroweb import TheretrowebSource

FIXTURES = Path(__file__).parent / "fixtures"


def _ctx(tmp_path: Path) -> SourceContext:
    return SourceContext(
        trusted_domains=("theretroweb.com", "dfi.ua", "chipsetpro.com"),
        skip_domains=("ebay.com", "prom.ua", "alicdn.com"),
        bad_photo_patterns=("logo", "favicon", "placeholder"),
        product_photo_hints=("/chip/image/", "large_default", "cache/catalog"),
        http_timeout=5.0,
        user_agent="test/0.0",
        cache_listings_dir=tmp_path / "listings",
        cache_ddg_text_dir=tmp_path / "ddg_text",
    )


def test_match_keys_drops_short_tokens():
    keys = match_keys("APW7120", "APW 7120 chip ic")
    assert "apw7120" in keys
    assert all(len(k) >= 4 for k in keys)


def test_keys_match_text_normalizes():
    assert keys_match_text(["apw7120"], "Anpec APW-7120 datasheet")
    assert not keys_match_text(["apw7120"], "totally different text")


def test_is_product_photo_url():
    ctx = _ctx(Path("/tmp"))
    assert is_product_photo_url("https://x.com/chip/image/foo.jpg", ctx)
    assert is_product_photo_url("https://x.com/cache/catalog/product/a-1000x1000.jpg", ctx)
    assert not is_product_photo_url("https://x.com/static/logo.png", ctx)
    assert not is_product_photo_url("https://x.com/random.gif", ctx)


def test_theretroweb_parses_listing_and_photo(tmp_path: Path):
    ctx = _ctx(tmp_path)
    search_html = (FIXTURES / "theretroweb" / "search_apw7120.html").read_text(encoding="utf-8")
    chip_html = (FIXTURES / "theretroweb" / "chip_6063.html").read_text(encoding="utf-8")

    def fake_fetch(url, _ctx, **kwargs):
        if url.endswith("/chips") and kwargs.get("method") == "POST":
            return search_html
        if "/chips/6063" in url:
            return chip_html
        return None

    src = TheretrowebSource()
    with patch("napolnenie.sources.theretroweb.fetch_html", side_effect=fake_fetch):
        hit = src.find(ctx, "APW7120", "APW7120", "BGA чип")

    assert hit is not None
    assert hit.source == "theretroweb"
    assert "/chip/image/" in hit.photo_url
    assert "/media/cache/show_thumb/" not in hit.photo_url
    assert hit.listing_url.endswith("/chips/6063")


def test_dfi_picks_largest_catalog_image(tmp_path: Path):
    ctx = _ctx(tmp_path)
    html = (FIXTURES / "dfi" / "listing_n15e_gt_a2.html").read_text(encoding="utf-8")

    def fake_ddgs(query, _ctx, **kwargs):
        return [
            {
                "href": "https://dfi.ua/zapchasti-dlja-noutbukov/nvidia-n15e-gt-a2.html",
                "title": "Микросхема NVIDIA N15E-GT-A2",
            }
        ]

    def fake_fetch(url, _ctx, **kwargs):
        return html if "dfi.ua" in url else None

    src = DfiSource()
    with patch("napolnenie.sources.dfi.ddgs_text_urls", side_effect=fake_ddgs), patch(
        "napolnenie.sources.dfi.fetch_html", side_effect=fake_fetch
    ):
        hit = src.find(ctx, "N15E-GT-A2", "NVIDIA N15E-GT-A2", "BGA чип")

    assert hit is not None
    assert hit.source == "dfi"
    assert "1500x1500" in hit.photo_url
    assert "logo" not in hit.photo_url


def test_chipsetpro_prefers_large_default(tmp_path: Path):
    ctx = _ctx(tmp_path)
    html = (FIXTURES / "chipsetpro" / "listing_apw7120.html").read_text(encoding="utf-8")

    def fake_ddgs(query, _ctx, **kwargs):
        return [
            {
                "href": "https://chipsetpro.com/products/apw7120",
                "title": "APW7120 power IC",
            }
        ]

    def fake_fetch(url, _ctx, **kwargs):
        return html if "chipsetpro.com" in url else None

    src = ChipsetproSource()
    with patch("napolnenie.sources.chipsetpro.ddgs_text_urls", side_effect=fake_ddgs), patch(
        "napolnenie.sources.chipsetpro.fetch_html", side_effect=fake_fetch
    ):
        hit = src.find(ctx, "APW7120", "APW7120", "BGA чип")

    assert hit is not None
    assert hit.source == "chipsetpro"
    assert "large_default" in hit.photo_url


def test_dfi_skips_when_keys_dont_match(tmp_path: Path):
    ctx = _ctx(tmp_path)
    html = (FIXTURES / "dfi" / "listing_n15e_gt_a2.html").read_text(encoding="utf-8")

    def fake_ddgs(query, _ctx, **kwargs):
        return [{"href": "https://dfi.ua/n15e-gt-a2.html", "title": "N15E-GT-A2"}]

    def fake_fetch(url, _ctx, **kwargs):
        return html

    src = DfiSource()
    with patch("napolnenie.sources.dfi.ddgs_text_urls", side_effect=fake_ddgs), patch(
        "napolnenie.sources.dfi.fetch_html", side_effect=fake_fetch
    ):
        hit = src.find(ctx, "XYZ9999", "XYZ9999", "")
    assert hit is None


def test_theretroweb_returns_none_when_keys_dont_match(tmp_path: Path):
    ctx = _ctx(tmp_path)
    search_html = (FIXTURES / "theretroweb" / "search_apw7120.html").read_text(encoding="utf-8")
    chip_html = (FIXTURES / "theretroweb" / "chip_6063.html").read_text(encoding="utf-8")

    def fake_fetch(url, _ctx, **kwargs):
        if url.endswith("/chips") and kwargs.get("method") == "POST":
            return search_html
        if "/chips/6063" in url:
            return chip_html
        return None

    src = TheretrowebSource()
    with patch("napolnenie.sources.theretroweb.fetch_html", side_effect=fake_fetch):
        hit = src.find(ctx, "XYZ9999", "XYZ9999", "BGA")
    assert hit is None
