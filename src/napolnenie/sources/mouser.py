from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from napolnenie.sources.base import ImageHit, SearchResult

MOUSER_PART_URL = "https://api.mouser.com/api/v1/search/partnumber"
DEFAULT_MIN_INTERVAL = 2.0  # ~30 req/min
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) napolnenie/0.1",
}

AKAMAI_HINT = (
    "Mouser API недоступен с вашего IP (403 Access Denied / Akamai). "
    "Частая причина — регион BY/RU. Варианты: VPN (EU/US), HTTPS_PROXY в .env, "
    "или веб-фолбэк (M5). Проверка: python -m napolnenie doctor"
)


def _safe_filename(query: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", query)[:80]


class MouserClient:
    def __init__(
        self,
        api_key: str,
        cache_dir: Path,
        min_interval: float = DEFAULT_MIN_INTERVAL,
    ) -> None:
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.min_interval = min_interval
        self._last_request_at = 0.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _build_opener(self) -> urllib.request.OpenerDirector:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            return urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy}))
        return urllib.request.build_opener()

    def _post(self, part_number: str, exact: bool) -> dict:
        self._throttle()
        body = {
            "SearchByPartRequest": {
                "mouserPartNumber": part_number,
                "partSearchOptions": "Exact" if exact else "None",
            }
        }
        data = json.dumps(body).encode("utf-8")
        opener = self._build_opener()
        last_error: RuntimeError | None = None

        for qparam in ("apiKey", "apikey"):
            url = f"{MOUSER_PART_URL}?{qparam}={self.api_key}"
            req = urllib.request.Request(url, data=data, headers=DEFAULT_HEADERS, method="POST")
            try:
                with opener.open(req, timeout=30) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="replace")
                if e.code == 403 and "Access Denied" in detail:
                    last_error = RuntimeError(AKAMAI_HINT)
                    continue
                last_error = RuntimeError(f"Mouser HTTP {e.code}: {detail[:300]}")
            except urllib.error.URLError as e:
                last_error = RuntimeError(f"Mouser сеть: {e.reason}")
        else:
            self._last_request_at = time.monotonic()
            raise last_error or RuntimeError("Mouser: не удалось выполнить запрос")

        self._last_request_at = time.monotonic()

        cache_name = f"{_safe_filename(part_number)}_{'exact' if exact else 'broad'}.json"
        cache_path = self.cache_dir / cache_name
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["_cache_path"] = str(cache_path)
        return payload

    def _api_error(self, payload: dict) -> str:
        errors = payload.get("Errors") or []
        if not errors:
            return ""
        for e in errors:
            prop = (e.get("PropertyName") or "").strip()
            msg = (e.get("Message") or "").strip()
            code = (e.get("Code") or "").strip()
            if prop == "API Key" or code == "Invalid":
                return (
                    "Неверный MOUSER_API_KEY. Нужен ключ Search API "
                    "(https://www.mouser.com/api-hub/), не Order API. "
                    f"Mouser: {msg}"
                )
        return "; ".join(f"{e.get('PropertyName', '')}: {e.get('Message', e)}" for e in errors)

    def _parse_hits(self, query: str, payload: dict) -> list[ImageHit]:
        search = payload.get("SearchResults") or {}
        parts = search.get("Parts") or []
        hits: list[ImageHit] = []
        for part in parts:
            image = (part.get("ImagePath") or "").strip()
            if not image:
                continue
            hits.append(
                ImageHit(
                    query=query,
                    image_url=image,
                    product_url=(part.get("ProductDetailUrl") or "").strip(),
                    mouser_part_number=(part.get("MouserPartNumber") or "").strip(),
                    manufacturer_part_number=(part.get("ManufacturerPartNumber") or "").strip(),
                    manufacturer=(part.get("Manufacturer") or "").strip(),
                    description=(part.get("Description") or "").strip(),
                )
            )
        return hits

    def search_part(self, part_number: str) -> SearchResult:
        part_number = part_number.strip()
        if not part_number:
            return SearchResult(query=part_number, error="пустой query")

        last_payload: dict | None = None
        for exact in (True, False):
            try:
                payload = self._post(part_number, exact=exact)
            except RuntimeError as e:
                return SearchResult(query=part_number, error=str(e))

            last_payload = payload
            api_err = self._api_error(payload)
            if api_err:
                return SearchResult(
                    query=part_number,
                    error=api_err,
                    raw_cache_path=payload.get("_cache_path", ""),
                    search_mode="api_error",
                )

            hits = self._parse_hits(part_number, payload)
            if hits:
                return SearchResult(
                    query=part_number,
                    hits=hits,
                    raw_cache_path=payload.get("_cache_path", ""),
                    search_mode="Exact" if exact else "None",
                )

        return SearchResult(
            query=part_number,
            hits=[],
            raw_cache_path=(last_payload or {}).get("_cache_path", ""),
            search_mode="not_found",
        )
