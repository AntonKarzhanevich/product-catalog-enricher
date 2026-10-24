from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from napolnenie.sources.mouser import MouserClient
from napolnenie.storage import download_mouser_image, image_slug_for_row

MOUSER_REPORT_COLUMNS = [
    "source_file",
    "row_num",
    "group",
    "series_raw",
    "query_sent",
    "source",
    "status",
    "search_mode",
    "image_url",
    "local_path",
    "product_url",
    "mouser_part_number",
    "manufacturer_part_number",
    "manufacturer",
    "description",
    "raw_cache",
    "error",
]


@dataclass
class MouserRowResult:
    source_file: str = ""
    row_num: int = 0
    group: str = ""
    series_raw: str = ""
    query_sent: str = ""
    status: str = "not_found"
    search_mode: str = ""
    image_url: str = ""
    local_path: str = ""
    product_url: str = ""
    mouser_part_number: str = ""
    manufacturer_part_number: str = ""
    manufacturer: str = ""
    description: str = ""
    raw_cache: str = ""
    error: str = ""


def load_parsed_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _find_image(dest: Path) -> Path | None:
    if dest.is_file():
        return dest
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".img"):
        candidate = dest.with_suffix(ext)
        if candidate.is_file():
            return candidate
    return None


def run_mouser_search(
    parsed_rows: list[dict],
    *,
    client: MouserClient,
    images_dir: Path,
    download: bool = True,
    verbose: bool = True,
) -> list[MouserRowResult]:
    results: list[MouserRowResult] = []
    total = len(parsed_rows)

    for i, row in enumerate(parsed_rows, start=1):
        row_num = int(row["row_num"])
        query_sent = (row.get("query_sent") or "").strip()
        mr = MouserRowResult(
            source_file=row.get("source_file", ""),
            row_num=row_num,
            group=row.get("group", ""),
            series_raw=row.get("series_raw", ""),
            query_sent=query_sent,
        )

        if verbose:
            print(f"[{i}/{total}] row {row_num} | {query_sent}")

        if not query_sent:
            mr.status = "error"
            mr.error = "пустой query_sent"
            results.append(mr)
            continue

        result = client.search_part(query_sent)
        mr.search_mode = result.search_mode
        mr.raw_cache = result.raw_cache_path

        if result.error:
            mr.status = "error"
            mr.error = result.error
            results.append(mr)
            if verbose:
                print(f"  error: {result.error[:100]}")
            continue

        hit = result.hits[0] if result.hits else None
        if not hit:
            mr.status = "not_found"
            results.append(mr)
            if verbose:
                print("  not_found")
            continue

        mr.status = "found"
        mr.image_url = hit.image_url
        mr.product_url = hit.product_url
        mr.mouser_part_number = hit.mouser_part_number
        mr.manufacturer_part_number = hit.manufacturer_part_number
        mr.manufacturer = hit.manufacturer
        mr.description = hit.description

        if download and hit.image_url:
            dest = images_dir / image_slug_for_row(row_num, query_sent)
            ok, detail, _ = download_mouser_image(
                hit.image_url, dest, product_url=hit.product_url
            )
            if ok:
                found = _find_image(dest)
                if found:
                    mr.local_path = str(found)
            else:
                mr.error = f"download: {detail}"

        results.append(mr)
        if verbose:
            line = f"  found [{result.search_mode}]"
            if mr.local_path:
                line += f" → {Path(mr.local_path).name}"
            elif mr.image_url:
                line += f" → {mr.image_url[:55]}..."
            print(line)

    return results


def download_mouser_images_from_report(
    report_path: Path,
    images_dir: Path,
    *,
    verbose: bool = True,
) -> tuple[int, int, list[MouserRowResult]]:
    """Скачать картинки для строк status=found в существующем mouser_report.csv."""
    rows = load_parsed_rows(report_path)
    results: list[MouserRowResult] = []
    ok_count = 0
    todo = [r for r in rows if (r.get("status") or "") == "found" and (r.get("image_url") or "").strip()]
    total = len(todo)

    for i, row in enumerate(todo, start=1):
        row_num = int(row["row_num"])
        query_sent = (row.get("query_sent") or "").strip()
        image_url = (row.get("image_url") or "").strip()
        product_url = (row.get("product_url") or "").strip()

        mr = MouserRowResult(
            source_file=row.get("source_file", ""),
            row_num=row_num,
            group=row.get("group", ""),
            series_raw=row.get("series_raw", ""),
            query_sent=query_sent,
            status="found",
            search_mode=row.get("search_mode", ""),
            image_url=image_url,
            product_url=product_url,
            mouser_part_number=row.get("mouser_part_number", ""),
            manufacturer_part_number=row.get("manufacturer_part_number", ""),
            manufacturer=row.get("manufacturer", ""),
            description=row.get("description", ""),
            raw_cache=row.get("raw_cache", ""),
        )

        if verbose:
            print(f"[{i}/{total}] row {row_num} | {query_sent}")

        dest = images_dir / image_slug_for_row(row_num, query_sent)
        ok, detail, _ = download_mouser_image(image_url, dest, product_url=product_url)
        if ok:
            found = _find_image(dest)
            if found:
                mr.local_path = str(found)
                ok_count += 1
                if verbose:
                    print(f"  ok → {found.name}")
        else:
            mr.error = f"download: {detail}"
            if verbose:
                print(f"  fail: {detail[:100]}")

        results.append(mr)

    return ok_count, total, results


def merge_download_paths_into_report(report_path: Path, downloaded: list[MouserRowResult]) -> None:
    """Обновить local_path и error в полном отчёте по row_num."""
    by_row = {r.row_num: r for r in downloaded}
    rows = load_parsed_rows(report_path)
    merged: list[MouserRowResult] = []

    for row in rows:
        row_num = int(row["row_num"])
        if row_num in by_row:
            d = by_row[row_num]
            merged.append(
                MouserRowResult(
                    source_file=row.get("source_file", ""),
                    row_num=row_num,
                    group=row.get("group", ""),
                    series_raw=row.get("series_raw", ""),
                    query_sent=row.get("query_sent", ""),
                    status=row.get("status", ""),
                    search_mode=row.get("search_mode", ""),
                    image_url=row.get("image_url", ""),
                    local_path=d.local_path or row.get("local_path", ""),
                    product_url=row.get("product_url", ""),
                    mouser_part_number=row.get("mouser_part_number", ""),
                    manufacturer_part_number=row.get("manufacturer_part_number", ""),
                    manufacturer=row.get("manufacturer", ""),
                    description=row.get("description", ""),
                    raw_cache=row.get("raw_cache", ""),
                    error=d.error or row.get("error", ""),
                )
            )
        else:
            merged.append(
                MouserRowResult(
                    source_file=row.get("source_file", ""),
                    row_num=row_num,
                    group=row.get("group", ""),
                    series_raw=row.get("series_raw", ""),
                    query_sent=row.get("query_sent", ""),
                    status=row.get("status", ""),
                    search_mode=row.get("search_mode", ""),
                    image_url=row.get("image_url", ""),
                    local_path=row.get("local_path", ""),
                    product_url=row.get("product_url", ""),
                    mouser_part_number=row.get("mouser_part_number", ""),
                    manufacturer_part_number=row.get("manufacturer_part_number", ""),
                    manufacturer=row.get("manufacturer", ""),
                    description=row.get("description", ""),
                    raw_cache=row.get("raw_cache", ""),
                    error=row.get("error", ""),
                )
            )

    write_mouser_report(merged, report_path)


def write_mouser_report(results: list[MouserRowResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MOUSER_REPORT_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "source_file": r.source_file,
                    "row_num": r.row_num,
                    "group": r.group,
                    "series_raw": r.series_raw,
                    "query_sent": r.query_sent,
                    "source": "mouser",
                    "status": r.status,
                    "search_mode": r.search_mode,
                    "image_url": r.image_url,
                    "local_path": r.local_path,
                    "product_url": r.product_url,
                    "mouser_part_number": r.mouser_part_number,
                    "manufacturer_part_number": r.manufacturer_part_number,
                    "manufacturer": r.manufacturer,
                    "description": r.description,
                    "raw_cache": r.raw_cache,
                    "error": r.error,
                }
            )
