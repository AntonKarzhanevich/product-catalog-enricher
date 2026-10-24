from pathlib import Path

from napolnenie.sources.listing_base import ListingHit, SourceContext
from napolnenie.web2_runner import run_web2_search


class _FakeSource:
    def __init__(self, name: str, hit: ListingHit | None):
        self.name = name
        self._hit = hit
        self.calls = 0

    def find(self, ctx, query_sent, series_raw, group_short):
        self.calls += 1
        return self._hit


def _ctx(tmp_path: Path) -> SourceContext:
    return SourceContext(
        trusted_domains=("theretroweb.com",),
        skip_domains=(),
        bad_photo_patterns=(),
        product_photo_hints=("/chip/image/",),
        http_timeout=5.0,
        user_agent="t",
        cache_listings_dir=tmp_path / "listings",
        cache_ddg_text_dir=tmp_path / "ddg_text",
    )


def test_each_row_searches_separately(tmp_path: Path, monkeypatch):
    rows = [
        {
            "source_file": "x.xlsx",
            "row_num": "1",
            "group": "BGA",
            "series_raw": "APW7120",
            "query_sent": "APW7120",
        },
        {
            "source_file": "x.xlsx",
            "row_num": "2",
            "group": "BGA",
            "series_raw": "APW7120 v2",
            "query_sent": "APW7120",
        },
    ]
    hit = ListingHit(
        source="theretroweb",
        listing_url="https://theretroweb.com/chips/6063",
        photo_url="https://theretroweb.com/chip/image/apw7120.jpg",
        title="APW7120",
        match="needs_review",
    )
    s1 = _FakeSource("theretroweb", hit)
    monkeypatch.setattr(
        "napolnenie.web2_runner.download_image", lambda url, dest: (True, "image/jpeg", 5000)
    )

    results, _ = run_web2_search(
        rows,
        out_dir=tmp_path,
        images_dir=tmp_path / "img",
        profile={"sources": []},
        sources=[s1],
        ctx=_ctx(tmp_path),
        download=True,
    )

    assert len(results) == 2
    assert s1.calls == 2
    assert results[0].local_path != results[1].local_path


def test_fallback_to_next_source_when_first_misses(tmp_path: Path, monkeypatch):
    rows = [
        {
            "source_file": "x.xlsx",
            "row_num": "1",
            "group": "BGA",
            "series_raw": "DFITEST",
            "query_sent": "DFITEST",
        }
    ]
    hit = ListingHit(
        source="dfi",
        listing_url="https://dfi.ua/x.html",
        photo_url="https://dfi.ua/image/cache/catalog/tovar/1-1500x1500.jpg",
        title="DFITEST",
    )
    s1 = _FakeSource("theretroweb", None)
    s2 = _FakeSource("dfi", hit)
    monkeypatch.setattr(
        "napolnenie.web2_runner.download_image", lambda url, dest: (True, "image/jpeg", 5000)
    )

    results, metrics = run_web2_search(
        rows,
        out_dir=tmp_path,
        images_dir=tmp_path / "img",
        profile={"sources": []},
        sources=[s1, s2],
        ctx=_ctx(tmp_path),
        download=True,
    )
    assert results[0].source == "dfi"
    assert s1.calls == 1
    assert s2.calls == 1


def test_not_found_when_all_sources_miss(tmp_path: Path):
    rows = [
        {
            "source_file": "x.xlsx",
            "row_num": "1",
            "group": "BGA",
            "series_raw": "X",
            "query_sent": "XYZ9999",
        }
    ]
    s1 = _FakeSource("theretroweb", None)
    s2 = _FakeSource("dfi", None)
    results, _ = run_web2_search(
        rows,
        out_dir=tmp_path,
        images_dir=tmp_path / "img",
        profile={"sources": []},
        sources=[s1, s2],
        ctx=_ctx(tmp_path),
        download=False,
    )
    assert results[0].status == "not_found"
