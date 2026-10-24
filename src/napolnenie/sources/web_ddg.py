from __future__ import annotations

import json
import time
from pathlib import Path

from napolnenie.sources.base import ImageHit, SearchResult


def _load_ddgs_class():
    try:
        from ddgs import DDGS

        return DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # noqa: F401 — устаревший пакет

            return DDGS
        except ImportError:
            return None


DDGS = _load_ddgs_class()


class DuckDuckGoImages:
    def __init__(
        self,
        cache_dir: Path,
        max_results: int = 8,
        min_interval: float = 1.5,
    ) -> None:
        self.cache_dir = cache_dir
        self.max_results = max_results
        self.min_interval = min_interval
        self._last_at = 0.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _cache_path(self, query: str) -> Path:
        return self.cache_dir / f"{_safe(query)}.json"

    def _from_cache(self, query: str) -> SearchResult | None:
        path = self._cache_path(query)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        items = data.get("items") or []
        if not items:
            return None
        hits = _hits_from_items(query, items)
        return SearchResult(
            query=query,
            hits=hits,
            raw_cache_path=str(path),
            search_mode="ddg_cache",
        )

    def search(self, query: str) -> SearchResult:
        if DDGS is None:
            return SearchResult(
                query=query,
                error="Установите пакет: pip install ddgs",
                search_mode="error",
            )

        self._throttle()
        hits: list[ImageHit] = []
        raw_items: list[dict] = []
        last_err: Exception | None = None
        for attempt in range(2):
            hits.clear()
            raw_items.clear()
            try:
                with DDGS() as ddgs:
                    for item in ddgs.images(query, max_results=self.max_results):
                        raw_items.append(dict(item))
                last_err = None
                break
            except Exception as e:
                last_err = e
                msg = str(e)
                if attempt == 0 and ("403" in msg or "Ratelimit" in msg):
                    time.sleep(12)
                    continue
                break

        if last_err is not None:
            cached = self._from_cache(query)
            if cached and cached.hits:
                self._last_at = time.monotonic()
                return cached
            self._last_at = time.monotonic()
            hint = "DDG rate limit — подождите 30–60 мин или увеличьте min_interval_sec в config/sources.yaml"
            return SearchResult(
                query=query,
                error=f"{last_err} ({hint})",
                search_mode="error",
            )

        hits = _hits_from_items(query, raw_items)
        self._last_at = time.monotonic()
        cache_path = self._cache_path(query)
        cache_path.write_text(
            json.dumps({"query": query, "items": raw_items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return SearchResult(
            query=query,
            hits=hits,
            raw_cache_path=str(cache_path),
            search_mode="ddg_images",
        )


def _hits_from_items(query: str, items: list[dict]) -> list[ImageHit]:
    hits: list[ImageHit] = []
    for item in items:
        url = (item.get("image") or item.get("thumbnail") or "").strip()
        if not url:
            continue
        hits.append(
            ImageHit(
                query=query,
                image_url=url,
                product_url=(item.get("url") or "").strip(),
                description=(item.get("title") or "").strip(),
            )
        )
    return hits


def _safe(text: str) -> str:
    import re

    return re.sub(r"[^\w\-.]+", "_", text)[:80]
