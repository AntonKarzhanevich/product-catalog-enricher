from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from napolnenie.web2_runner import Web2RowResult, load_parsed_rows, write_web2_report
from napolnenie.web_runner import WebRowResult, write_web_report

CASCADE_REPORT_COLUMNS = [
    "source_file",
    "row_num",
    "group",
    "series_raw",
    "query_sent",
    "cascade_status",
    "primary_source",
    "image_url",
    "local_path",
    "listing_url",
    "image_title",
    "web2_status",
    "web2_source",
    "web2_local_path",
    "web2_error",
    "web1_status",
    "web1_local_path",
    "web1_error",
]


@dataclass
class CascadeRowResult:
    source_file: str = ""
    row_num: int = 0
    group: str = ""
    series_raw: str = ""
    query_sent: str = ""
    cascade_status: str = "not_found"
    primary_source: str = ""
    image_url: str = ""
    local_path: str = ""
    listing_url: str = ""
    image_title: str = ""
    web2_status: str = ""
    web2_source: str = ""
    web2_local_path: str = ""
    web2_error: str = ""
    web1_status: str = ""
    web1_local_path: str = ""
    web1_error: str = ""


def web2_has_image(r: Web2RowResult) -> bool:
    return r.status == "needs_review" and bool((r.local_path or "").strip())


def load_web2_report(path: Path) -> list[Web2RowResult]:
    rows = load_parsed_rows(path)
    out: list[Web2RowResult] = []
    for row in rows:
        out.append(
            Web2RowResult(
                source_file=row.get("source_file", ""),
                row_num=int(row["row_num"]),
                group=row.get("group", ""),
                series_raw=row.get("series_raw", ""),
                query_sent=row.get("query_sent", ""),
                engine_version=row.get("engine_version", "v2"),
                source=row.get("source", ""),
                status=row.get("status", ""),
                confidence=row.get("confidence", ""),
                listing_url=row.get("listing_url", ""),
                image_url=row.get("image_url", ""),
                local_path=row.get("local_path", ""),
                image_title=row.get("image_title", ""),
                error=row.get("error", ""),
            )
        )
    return out


def parsed_rows_for_v1_tail(
    parsed_rows: list[dict], web2_results: list[Web2RowResult]
) -> list[dict]:
    """Строки parsed.csv, где web2 не дал файл картинки."""
    ok = {r.row_num for r in web2_results if web2_has_image(r)}
    return [row for row in parsed_rows if int(row["row_num"]) not in ok]


def merge_cascade_report(
    web2_results: list[Web2RowResult],
    web1_results: list[WebRowResult],
) -> list[CascadeRowResult]:
    web2_by_row = {r.row_num: r for r in web2_results}
    web1_by_row = {r.row_num: r for r in web1_results}
    all_rows = sorted(set(web2_by_row) | set(web1_by_row))

    merged: list[CascadeRowResult] = []
    for row_num in all_rows:
        w2 = web2_by_row.get(row_num)
        w1 = web1_by_row.get(row_num)
        base = w2 or w1
        if base is None:
            continue

        cr = CascadeRowResult(
            source_file=w2.source_file if w2 else w1.source_file,  # type: ignore[union-attr]
            row_num=row_num,
            group=w2.group if w2 else w1.group,  # type: ignore[union-attr]
            series_raw=w2.series_raw if w2 else w1.series_raw,  # type: ignore[union-attr]
            query_sent=w2.query_sent if w2 else w1.query_sent,  # type: ignore[union-attr]
        )

        if w2:
            cr.web2_status = w2.status
            cr.web2_source = w2.source
            cr.web2_local_path = w2.local_path
            cr.web2_error = w2.error

        if w1:
            cr.web1_status = w1.status
            cr.web1_local_path = w1.local_path
            cr.web1_error = w1.error

        if w2 and web2_has_image(w2):
            cr.cascade_status = "found_web2"
            cr.primary_source = f"web2:{w2.source}"
            cr.image_url = w2.image_url
            cr.local_path = w2.local_path
            cr.listing_url = w2.listing_url
            cr.image_title = w2.image_title
        elif w1 and w1.status == "needs_review" and (w1.local_path or "").strip():
            cr.cascade_status = "found_web1"
            cr.primary_source = "web1:ddg"
            cr.image_url = w1.image_url
            cr.local_path = w1.local_path
            cr.image_title = w1.image_title
        elif w1 and w1.status == "needs_review":
            cr.cascade_status = "found_web1"
            cr.primary_source = "web1:ddg"
            cr.image_url = w1.image_url
            cr.image_title = w1.image_title
        else:
            cr.cascade_status = "not_found"

        merged.append(cr)
    return merged


def write_cascade_report(results: list[CascadeRowResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CASCADE_REPORT_COLUMNS)
        w.writeheader()
        for r in results:
            w.writerow(
                {
                    "source_file": r.source_file,
                    "row_num": r.row_num,
                    "group": r.group,
                    "series_raw": r.series_raw,
                    "query_sent": r.query_sent,
                    "cascade_status": r.cascade_status,
                    "primary_source": r.primary_source,
                    "image_url": r.image_url,
                    "local_path": r.local_path,
                    "listing_url": r.listing_url,
                    "image_title": r.image_title,
                    "web2_status": r.web2_status,
                    "web2_source": r.web2_source,
                    "web2_local_path": r.web2_local_path,
                    "web2_error": r.web2_error,
                    "web1_status": r.web1_status,
                    "web1_local_path": r.web1_local_path,
                    "web1_error": r.web1_error,
                }
            )


def rebuild_web2_results_from_parsed(
    parsed_rows: list[dict], web2_partial: list[Web2RowResult]
) -> list[Web2RowResult]:
    """Дополнить web2 not_found для строк без результата (после v1-only хвоста)."""
    by_row = {r.row_num: r for r in web2_partial}
    full: list[Web2RowResult] = []
    for row in parsed_rows:
        row_num = int(row["row_num"])
        if row_num in by_row:
            full.append(by_row[row_num])
        else:
            full.append(
                Web2RowResult(
                    source_file=row.get("source_file", ""),
                    row_num=row_num,
                    group=row.get("group", ""),
                    series_raw=row.get("series_raw", ""),
                    query_sent=(row.get("query_sent") or "").strip(),
                    status="not_found",
                )
            )
    return full
