"""Фильтры качества скачанных картинок (заглушки, generic URL)."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def _row_val(row: object, name: str, default: str = "") -> str:
    if isinstance(row, dict):
        return str(row.get(name, default) or default)
    return str(getattr(row, name, default) or default)


def _set_not_found(row: object, error: str, *, clear_url: bool = False) -> None:
    if isinstance(row, dict):
        row["status"] = "not_found"
        row["local_path"] = ""
        if clear_url:
            row["image_url"] = ""
        row["error"] = error
        return
    row.status = "not_found"
    row.local_path = ""
    if clear_url:
        row.image_url = ""
    row.error = error


def normalize_image_url(url: str) -> str:
    """Нормализация URL для сравнения (без query/fragment)."""
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def reject_cross_mpn_duplicate_urls(
    rows: list,
    *,
    remove_files: bool = True,
) -> int:
    """
    Один и тот же image_url на разных query_sent (MPN) в одном прогоне = generic-заглушка.
    Все такие строки сбрасываются в not_found (чтобы v1 мог догнать).
    """
    by_url: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        status = _row_val(row, "status")
        image_url = _row_val(row, "image_url")
        if status != "needs_review" or not image_url:
            continue
        key = normalize_image_url(image_url)
        if key:
            by_url[key].append(i)

    rejected = 0
    for _url, indices in by_url.items():
        queries = {_row_val(rows[i], "query_sent").strip().upper() for i in indices}
        if len(queries) < 2:
            continue

        for i in indices:
            row = rows[i]
            if remove_files:
                local = _row_val(row, "local_path")
                if local:
                    p = Path(local)
                    if p.is_file():
                        p.unlink()
            _set_not_found(row, "generic_duplicate_image_url", clear_url=True)
            rejected += 1

    return rejected


def reject_cross_mpn_duplicate_file_hashes(
    rows: list,
    *,
    remove_files: bool = True,
) -> int:
    """Тот же файл (sha256) у разных MPN — тоже generic."""
    by_hash: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        status = _row_val(row, "status")
        local = _row_val(row, "local_path")
        if status != "needs_review" or not local:
            continue
        p = Path(local)
        if not p.is_file():
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        by_hash[digest].append(i)

    rejected = 0
    for _digest, indices in by_hash.items():
        queries = {_row_val(rows[i], "query_sent").strip().upper() for i in indices}
        if len(queries) < 2:
            continue

        for i in indices:
            row = rows[i]
            if remove_files:
                local = _row_val(row, "local_path")
                if local:
                    p = Path(local)
                    if p.is_file():
                        p.unlink()
            _set_not_found(row, "generic_duplicate_file_hash")
            rejected += 1

    return rejected
