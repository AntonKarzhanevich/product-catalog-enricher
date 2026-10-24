"""dfi.ua: DDGS text 'site:dfi.ua {q}' → fetch listing → extract photo."""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from napolnenie.sources.listing_base import (
    ListingHit,
    SourceContext,
    SourceMetrics,
    ddgs_text_urls,
    fetch_html,
    is_bad_photo_url,
    keys_match_text,
    match_keys,
)

_DOMAIN = "dfi.ua"
_SIZE_RE = re.compile(r"-(\d+)x(\d+)\.")
_CATALOG_HINTS = ("/image/cache/catalog/tovar/", "/image/cache/catalog/product/")


class DfiSource:
    name = "dfi"

    def find(
        self,
        ctx: SourceContext,
        query_sent: str,
        series_raw: str,
        group_short: str,
    ) -> ListingHit | None:
        metrics = ctx.metrics.setdefault(self.name, SourceMetrics(source=self.name))
        t0 = time.monotonic()
        try:
            hit = self._search(ctx, query_sent, series_raw)
        except Exception:
            metrics.record("error", int((time.monotonic() - t0) * 1000))
            raise
        metrics.record("hit" if hit else "miss", int((time.monotonic() - t0) * 1000))
        return hit

    def _search(self, ctx: SourceContext, query_sent: str, series_raw: str) -> ListingHit | None:
        keys = match_keys(query_sent, series_raw)
        queries = [f"site:{_DOMAIN} {query_sent}"]
        if series_raw and series_raw.strip() and series_raw.strip() != query_sent.strip():
            queries.append(f"site:{_DOMAIN} {series_raw}")

        seen_listings: set[str] = set()
        for q in queries:
            items = ddgs_text_urls(q, ctx, max_results=ctx.ddgs_results_per_query)
            for it in items[: ctx.ddgs_max_urls_per_source]:
                href = it.get("href", "")
                if _DOMAIN not in href.lower():
                    continue
                if href in seen_listings:
                    continue
                seen_listings.add(href)
                page = fetch_html(href, ctx)
                if not page:
                    continue
                blob = _page_blob(page) + " " + href + " " + it.get("title", "")
                if not keys_match_text(keys, blob):
                    continue
                photo = _extract_photo(page, href, ctx)
                if not photo:
                    continue
                return ListingHit(
                    source=self.name,
                    listing_url=href,
                    photo_url=photo,
                    title=it.get("title", "") or _page_title(page),
                    match="needs_review",
                    notes=f"dfi: {q}",
                )
        return None


def _collect_img_urls(html: str, base_url: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            raw = (img.get(attr) or "").strip()
            if not raw or raw.startswith("data:"):
                continue
            full = urljoin(base_url, raw)
            if full not in seen:
                seen.add(full)
                out.append(full)
    return out


def _extract_photo(html: str, listing_url: str, ctx: SourceContext) -> str | None:
    urls = _collect_img_urls(html, listing_url)
    best: str | None = None
    best_px = 0
    for u in urls:
        if not any(h in u for h in _CATALOG_HINTS):
            continue
        if is_bad_photo_url(u, ctx.bad_photo_patterns):
            continue
        m = _SIZE_RE.search(u)
        px = int(m.group(1)) * int(m.group(2)) if m else 1
        if px > best_px:
            best_px = px
            best = u
    if best:
        return best
    for u in urls:
        if any(h in u for h in _CATALOG_HINTS) and not is_bad_photo_url(u, ctx.bad_photo_patterns):
            return u
    return None


def _page_blob(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    if soup.title and soup.title.get_text():
        parts.append(soup.title.get_text())
    for h1 in soup.find_all("h1"):
        parts.append(h1.get_text())
    return " ".join(parts)


def _page_title(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return soup.title.get_text(strip=True) if soup.title else ""
