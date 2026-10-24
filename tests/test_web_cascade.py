from napolnenie.web_cascade_runner import (
    merge_cascade_report,
    parsed_rows_for_v1_tail,
    web2_has_image,
)
from napolnenie.web2_runner import Web2RowResult
from napolnenie.web_runner import WebRowResult


def _w2(row_num: int, query_sent: str = "Q", **kw) -> Web2RowResult:
    return Web2RowResult(
        source_file="t.xlsx",
        row_num=row_num,
        group="g",
        series_raw="s",
        query_sent=query_sent,
        **kw,
    )


def test_web2_has_image_requires_local_path():
    assert web2_has_image(_w2(1, status="needs_review", local_path="/x.jpg"))
    assert not web2_has_image(_w2(1, status="needs_review", local_path=""))
    assert not web2_has_image(_w2(1, status="not_found"))


def test_parsed_rows_for_v1_tail():
    parsed = [{"row_num": "1", "query_sent": "A"}, {"row_num": "2", "query_sent": "B"}]
    web2 = [
        _w2(1, status="needs_review", local_path="/a.jpg"),
        _w2(2, status="not_found"),
    ]
    tail = parsed_rows_for_v1_tail(parsed, web2)
    assert len(tail) == 1
    assert tail[0]["query_sent"] == "B"


def test_merge_cascade_report():
    web2 = [_w2(1, query_sent="A", status="needs_review", local_path="/a.jpg", source="dfi")]
    web1 = [
        WebRowResult(
            source_file="t.xlsx",
            row_num=2,
            group="g",
            series_raw="s",
            query_sent="B",
            web_query="B q",
            status="needs_review",
            local_path="/b.jpg",
            image_url="http://x/b.jpg",
        )
    ]
    merged = merge_cascade_report(web2, web1)
    assert merged[0].cascade_status == "found_web2"
    assert merged[1].cascade_status == "found_web1"
