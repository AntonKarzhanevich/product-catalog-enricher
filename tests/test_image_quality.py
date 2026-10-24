from napolnenie.image_quality import reject_cross_mpn_duplicate_urls
from napolnenie.web2_runner import Web2RowResult

_BASE = dict(source_file="t.xlsx", group="g", series_raw="s")


def test_reject_cross_mpn_duplicate_urls():
    rows = [
        Web2RowResult(**_BASE, row_num=69, query_sent="IT8511TE", status="needs_review", image_url="https://x/a.jpg"),
        Web2RowResult(**_BASE, row_num=88, query_sent="IT8987E", status="needs_review", image_url="https://x/a.jpg"),
        Web2RowResult(**_BASE, row_num=10, query_sent="IT8511TE", status="needs_review", image_url="https://x/a.jpg"),
    ]
    n = reject_cross_mpn_duplicate_urls(rows, remove_files=False)
    assert n == 3
    assert all(r.status == "not_found" for r in rows)
    assert rows[0].error == "generic_duplicate_image_url"


def test_same_mpn_same_url_kept():
    rows = [
        Web2RowResult(**_BASE, row_num=10, query_sent="ALC3248", status="needs_review", image_url="https://x/b.jpg"),
        Web2RowResult(**_BASE, row_num=11, query_sent="ALC3248", status="needs_review", image_url="https://x/b.jpg"),
    ]
    n = reject_cross_mpn_duplicate_urls(rows, remove_files=False)
    assert n == 0
    assert rows[0].status == "needs_review"
