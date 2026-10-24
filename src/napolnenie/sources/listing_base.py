"""Базовые типы и эвристики для источников-листингов (M5 v2)."""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ListingHit:
    """Найденная страница товара + извлечённое фото."""

    source: str
    listing_url: str
    photo_url: str
    title: str = ""
    match: str = "needs_review"
    notes: str = ""


@dataclass
class SourceMetrics:
    source: str
    hits: int = 0
    miss: int = 0
    error: int = 0
    total_latency_ms: int = 0

    def record(self, status: str, latency_ms: int) -> None:
        self.total_latency_ms += latency_ms
        if status == "hit":
            self.hits += 1
        elif status == "miss":
            self.miss += 1
        else:
            self.error += 1


@dataclass
class SourceContext:
    """Конфиг профиля группы, нужный источникам."""

    trusted_domains: tuple[str, ...]
    skip_domains: tuple[str, ...]
    bad_photo_patterns: tuple[str, ...]
    product_photo_hints: tuple[str, ...]
    http_timeout: float
    user_agent: str
    cache_listings_dir: Path
    cache_ddg_text_dir: Path
    ddgs_results_per_query: int = 5
    ddgs_max_urls_per_source: int = 8
    ddgs_min_interval_sec: float = 2.0
    metrics: dict[str, SourceMetrics] = field(default_factory=dict)


class ListingSource(Protocol):
    name: str

    def find(self, ctx: SourceContext, query_sent: str, series_raw: str, group_short: str) -> ListingHit | None: ...


def norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def match_keys(query_sent: str, series_raw: str) -> list[str]:
    """Ключи для проверки «фото про этот MPN». Длиннее = надёжнее."""
    keys: list[str] = []
    for raw in (query_sent, series_raw):
        if not raw:
            continue
        n = norm_key(raw)
        if len(n) >= 4:
            keys.append(n)
        for tok in re.split(r"[\s,;/]+", raw):
            t = norm_key(tok)
            if len(t) >= 4:
                keys.append(t)
    seen: set[str] = set()
    out: list[str] = []
    for k in sorted(set(keys), key=len, reverse=True):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def keys_match_text(keys: list[str], blob: str) -> bool:
    if not keys or not blob:
        return False
    n = norm_key(blob)
    return any(k in n for k in keys)


def is_trusted_url(url: str, trusted: tuple[str, ...]) -> bool:
    low = url.lower()
    return any(d in low for d in trusted)


def is_skip_url(url: str, skip: tuple[str, ...]) -> bool:
    low = url.lower()
    return any(s in low for s in skip)


def is_bad_photo_url(url: str, bad_patterns: tuple[str, ...]) -> bool:
    low = url.lower()
    return any(p in low for p in bad_patterns)


def is_product_photo_url(url: str, ctx: SourceContext) -> bool:
    if not url:
        return False
    low = url.lower()
    if is_bad_photo_url(low, ctx.bad_photo_patterns):
        return False
    return any(h in low for h in ctx.product_photo_hints)


def cache_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def fetch_html(url: str, ctx: SourceContext, *, method: str = "GET", data: dict | None = None) -> str | None:
    """HTTP GET/POST + кэш HTML на диск."""
    import requests

    cache_path = ctx.cache_listings_dir / (cache_key(f"{method}:{url}:{data or ''}") + ".html")
    if method == "GET" and cache_path.is_file():
        try:
            return cache_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    headers = {"User-Agent": ctx.user_agent, "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"}
    try:
        if method == "POST":
            r = requests.post(url, data=data or {}, headers=headers, timeout=ctx.http_timeout)
        else:
            r = requests.get(url, headers=headers, timeout=ctx.http_timeout)
        r.raise_for_status()
    except Exception:
        return None
    text = r.text
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8", errors="ignore")
    except OSError:
        pass
    return text


_DDGS_LAST_AT = 0.0


def ddgs_text_urls(query: str, ctx: SourceContext, *, max_results: int | None = None) -> list[dict]:
    """DDGS text-поиск листингов. Возвращает [{href, title}, ...] из trusted доменов, не skip."""
    global _DDGS_LAST_AT
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    elapsed = time.monotonic() - _DDGS_LAST_AT
    if elapsed < ctx.ddgs_min_interval_sec:
        time.sleep(ctx.ddgs_min_interval_sec - elapsed)

    n = max_results or ctx.ddgs_results_per_query
    out: list[dict] = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=n):
                href = (item.get("href") or item.get("url") or "").strip()
                title = (item.get("title") or "").strip()
                if not href.startswith("http"):
                    continue
                if is_skip_url(href, ctx.skip_domains):
                    continue
                out.append({"href": href, "title": title})
    except Exception:
        pass
    _DDGS_LAST_AT = time.monotonic()
    return out


def first_trusted_url(items: list[dict], domain: str) -> tuple[str, str] | None:
    """Найти первый URL конкретного домена."""
    for it in items:
        href = it.get("href", "")
        if domain in href.lower():
            return href, it.get("title", "")
    return None


__all__ = [
    "ListingHit",
    "ListingSource",
    "SourceContext",
    "SourceMetrics",
    "cache_key",
    "ddgs_text_urls",
    "fetch_html",
    "first_trusted_url",
    "is_bad_photo_url",
    "is_product_photo_url",
    "is_skip_url",
    "is_trusted_url",
    "keys_match_text",
    "match_keys",
    "norm_key",
]
