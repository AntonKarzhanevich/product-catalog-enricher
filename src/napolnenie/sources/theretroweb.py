"""Theretroweb: POST /chips → /chips/<id> → парсинг /chip/image/* (M5 v2)."""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from napolnenie.sources.listing_base import (
    ListingHit,
    SourceContext,
    fetch_html,
    is_bad_photo_url,
    keys_match_text,
    match_keys,
)

_BASE = "https://theretroweb.com"
_SEARCH_URL = f"{_BASE}/chips"
_CHIP_HREF_RE = re.compile(r"^/chips/\d+$")


class TheretrowebSource:
    name = "theretroweb"

    def find(
        self,
        ctx: SourceContext,
        query_sent: str,
        series_raw: str,
        group_short: str,
    ) -> ListingHit | None:
        candidates: list[str] = [query_sent.strip()]
        if series_raw and series_raw.strip() and series_raw.strip() not in candidates:
            candidates.append(series_raw.strip())

        keys = match_keys(query_sent, series_raw)
        metrics = ctx.metrics.setdefault(self.name, _new_metrics(self.name))

        for name in candidates:
            t0 = time.monotonic()
            hit = self._search_one(ctx, name, keys)
            metrics.record("hit" if hit else "miss", int((time.monotonic() - t0) * 1000))
            if hit:
                return hit
        return None

    def _search_one(self, ctx: SourceContext, name: str, keys: list[str]) -> ListingHit | None:
        html = fetch_html(_SEARCH_URL, ctx, method="POST", data={"search[name]": name, "items_per_page": "8"})
        if not html:
            return None
        listings = _extract_chip_listings(html)
        for listing_url in listings:
            page = fetch_html(listing_url, ctx)
            if not page:
                continue
            blob = _page_text_blob(page) + " " + listing_url
            if not keys_match_text(keys, blob):
                continue
            photo = _extract_chip_photo(page, listing_url, ctx)
            if not photo:
                continue
            title = _extract_title(page)
            return ListingHit(
                source=self.name,
                listing_url=listing_url,
                photo_url=photo,
                title=title,
                match="needs_review",
                notes=f"theretroweb: {name}",
            )
        return None


def _new_metrics(name: str):
    from napolnenie.sources.listing_base import SourceMetrics

    return SourceMetrics(source=name)


def _extract_chip_listings(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if _CHIP_HREF_RE.match(href):
            full = urljoin(_BASE + "/", href.lstrip("/"))
            if full not in seen:
                seen.add(full)
                out.append(full)
    return out


def _extract_chip_photo(html: str, listing_url: str, ctx: SourceContext) -> str | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img", src=True):
        src = (img.get("src") or "").strip()
        if not src or "/chip/image/" not in src:
            continue
        src = src.replace("/media/cache/show_thumb/", "/")
        full = urljoin(listing_url, src)
        if is_bad_photo_url(full, ctx.bad_photo_patterns):
            continue
        return full
    return None


def _extract_title(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    t = soup.find("title")
    return t.get_text(strip=True) if t else ""


def _page_text_blob(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    if soup.title and soup.title.get_text():
        parts.append(soup.title.get_text())
    for h1 in soup.find_all("h1"):
        parts.append(h1.get_text())
    return " ".join(parts)
