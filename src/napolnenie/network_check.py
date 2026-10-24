from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class EndpointCheck:
    name: str
    url: str
    ok: bool
    status: str
    hint: str = ""


def _probe(url: str, timeout: float = 12.0) -> tuple[bool, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) napolnenie/0.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, str(resp.status)
    except urllib.error.HTTPError as e:
        body = e.read(200).decode("utf-8", errors="replace")
        if e.code == 403 and "Access Denied" in body:
            return False, "403 Akamai (гео/бот)"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__


def run_connectivity_checks() -> list[EndpointCheck]:
    probes = [
        ("Mouser API docs", "https://api.mouser.com/api/docs/ui/index", "VPN EU/US или HTTPS_PROXY в .env"),
        ("Digi-Key portal", "https://developer.digikey.com/", "то же"),
        ("DuckDuckGo", "https://duckduckgo.com/", "веб-фолбэк картинок (M5)"),
    ]
    out: list[EndpointCheck] = []
    for name, url, hint in probes:
        ok, status = _probe(url)
        out.append(EndpointCheck(name=name, url=url, ok=ok, status=status, hint=hint if not ok else ""))
    return out
