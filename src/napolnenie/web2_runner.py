"""M5 v2 — оркестратор: trusted listings (Theretroweb, DFI, chipsetpro)."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from napolnenie.env import project_root
from napolnenie.query import shorten_group
from napolnenie.sources.chipsetpro import ChipsetproSource
from napolnenie.sources.dfi import DfiSource
from napolnenie.sources.listing_base import ListingSource, SourceContext, SourceMetrics
from napolnenie.sources.theretroweb import TheretrowebSource
from napolnenie.image_quality import (
    reject_cross_mpn_duplicate_file_hashes,
    reject_cross_mpn_duplicate_urls,
)
from napolnenie.storage import download_image, image_slug_for_row

WEB2_REPORT_COLUMNS = [
    "source_file",
    "row_num",
    "group",
    "series_raw",
    "query_sent",
    "engine_version",
    "source",
    "status",
    "confidence",
    "listing_url",
    "image_url",
    "local_path",
    "image_title",
    "error",
]

_REGISTRY: dict[str, type] = {
    "theretroweb": TheretrowebSource,
    "dfi": DfiSource,
    "chipsetpro": ChipsetproSource,
}


@dataclass
class Web2RowResult:
    source_file: str
    row_num: int
    group: str
    series_raw: str
    query_sent: str
    engine_version: str = "v2"
    source: str = ""
    status: str = "not_found"
    confidence: str = "0.7"
    listing_url: str = ""
    image_url: str = ""
    local_path: str = ""
    image_title: str = ""
    error: str = ""


def load_profile(name: str = "bga_laptop_ic") -> dict:
    cfg = project_root() / "config" / "sources" / f"{name}.yaml"
    if not cfg.is_file():
        raise FileNotFoundError(f"Профиль не найден: {cfg}")
    return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}


def build_context(profile: dict, out_dir: Path) -> SourceContext:
    http = profile.get("http", {}) or {}
    ddg = profile.get("ddgs_text", {}) or {}
    return SourceContext(
        trusted_domains=tuple(profile.get("trusted_domains", [])),
        skip_domains=tuple(profile.get("skip_domains", [])),
        bad_photo_patterns=tuple(profile.get("bad_photo_patterns", [])),
        product_photo_hints=tuple(profile.get("product_photo_hints", [])),
        http_timeout=float(http.get("timeout_sec", 10)),
        user_agent=str(http.get("user_agent", "napolnenie/0.2")),
        cache_listings_dir=out_dir / "_cache" / "listings",
        cache_ddg_text_dir=out_dir / "_cache" / "ddg_text",
        ddgs_results_per_query=int(ddg.get("results_per_query", 5)),
        ddgs_max_urls_per_source=int(ddg.get("max_urls_per_source", 8)),
        ddgs_min_interval_sec=float(ddg.get("min_interval_sec", 2.0)),
    )


def make_sources(profile: dict) -> list[ListingSource]:
    out: list[ListingSource] = []
    for name in profile.get("sources", []):
        cls = _REGISTRY.get(name)
        if cls is None:
            continue
        out.append(cls())
    return out


def load_parsed_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run_web2_search(
    parsed_rows: list[dict],
    *,
    out_dir: Path,
    images_dir: Path,
    profile: dict,
    sources: Iterable[ListingSource] | None = None,
    ctx: SourceContext | None = None,
    download: bool = True,
    verbose: bool = False,
) -> tuple[list[Web2RowResult], dict[str, SourceMetrics]]:
    ctx = ctx or build_context(profile, out_dir)
    sources = list(sources) if sources is not None else make_sources(profile)
    ctx.cache_listings_dir.mkdir(parents=True, exist_ok=True)
    ctx.cache_ddg_text_dir.mkdir(parents=True, exist_ok=True)

    results: list[Web2RowResult] = []
    total = len(parsed_rows)

    for idx, row in enumerate(parsed_rows, start=1):
        query_sent = (row.get("query_sent") or "").strip()
        series_raw = (row.get("series_raw") or "").strip()
        group = (row.get("group") or "").strip()
        group_short = shorten_group(group)
        row_num = int(row.get("row_num") or 0)
        wr = Web2RowResult(
            source_file=row.get("source_file", ""),
            row_num=row_num,
            group=group,
            series_raw=series_raw,
            query_sent=query_sent,
        )

        if verbose:
            print(f"[{idx}/{total}] row {row_num} | {query_sent}", flush=True)

        if not query_sent:
            wr.status = "error"
            wr.error = "пустой query_sent"
            results.append(wr)
            continue

        hit = None
        last_error = ""
        for src in sources:
            try:
                hit = src.find(ctx, query_sent, series_raw, group_short)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{src.name}: {exc}"
                hit = None
            if hit:
                break

        if hit is not None:
            wr.status = "needs_review"
            wr.source = hit.source
            wr.listing_url = hit.listing_url
            wr.image_url = hit.photo_url
            wr.image_title = hit.title
            if download:
                dest = images_dir / image_slug_for_row(row_num, query_sent)
                ok, msg, _ = download_image(hit.photo_url, dest)
                if ok:
                    wr.local_path = str(_find_image(dest))
                else:
                    wr.error = msg
        else:
            wr.status = "not_found"
            wr.error = last_error or "нет совпадений на trusted-доменах"

        results.append(wr)

    dup_url = reject_cross_mpn_duplicate_urls(results)
    dup_hash = reject_cross_mpn_duplicate_file_hashes(results)
    if verbose and (dup_url or dup_hash):
        print(
            f"\nweb2: отброшено generic-дублей — по URL: {dup_url}, по хэшу файла: {dup_hash}",
            flush=True,
        )

    return results, ctx.metrics


def _find_image(base: Path) -> Path:
    if base.is_file():
        return base
    for p in base.parent.glob(base.name + ".*"):
        if p.is_file():
            return p
    return base


def write_web2_report(results: list[Web2RowResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=WEB2_REPORT_COLUMNS)
        w.writeheader()
        for r in results:
            w.writerow(
                {
                    "source_file": r.source_file,
                    "row_num": r.row_num,
                    "group": r.group,
                    "series_raw": r.series_raw,
                    "query_sent": r.query_sent,
                    "engine_version": r.engine_version,
                    "source": r.source,
                    "status": r.status,
                    "confidence": r.confidence,
                    "listing_url": r.listing_url,
                    "image_url": r.image_url,
                    "local_path": r.local_path,
                    "image_title": r.image_title,
                    "error": r.error,
                }
            )


def write_stats(metrics: dict[str, SourceMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "hits", "miss", "error", "total_latency_ms", "avg_latency_ms"])
        for m in metrics.values():
            total = m.hits + m.miss + m.error
            avg = (m.total_latency_ms // total) if total else 0
            w.writerow([m.source, m.hits, m.miss, m.error, m.total_latency_ms, avg])
