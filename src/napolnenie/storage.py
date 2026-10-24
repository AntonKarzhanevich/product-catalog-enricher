from __future__ import annotations

import io
import http.cookiejar
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

MIN_IMAGE_BYTES = 2048
ALLOWED_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def safe_slug(text: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", text)[:80] or "unknown"


def image_slug_for_row(row_num: int, query_sent: str) -> str:
    """Уникальное имя файла: одна строка 1С (row_num) → один файл картинки."""
    base = safe_slug(query_sent) if query_sent else "unknown"
    return f"r{row_num}_{base}"[:80]


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _image_ext_from_bytes(data: bytes, ctype: str) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(ctype, ".img")


def download_image(
    url: str,
    dest_path: Path,
    timeout: float = 30.0,
    *,
    referer: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[bool, str, int]:
    """Скачать картинку. Возвращает (ok, mime_or_error, bytes)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except urllib.error.URLError as e:
        return False, str(e.reason), 0

    if not ctype.startswith("image/"):
        ext = _image_ext_from_bytes(data, ctype)
        if ext == ".img":
            return False, f"не image/*: {ctype or 'unknown'}", len(data)
        ctype = {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(ext, ctype)
    elif ctype not in ALLOWED_PREFIXES and not ctype.startswith("image/"):
        pass  # allow other image/* subtypes
    if len(data) < MIN_IMAGE_BYTES:
        return False, f"слишком мало байт: {len(data)}", len(data)

    return _save_image_bytes(data, dest_path, ctype)


def mouser_referer_for(product_url: str, image_url: str) -> str:
    """Referer для hotlink-защиты Mouser (same registrable domain)."""
    from urllib.parse import urlparse

    for candidate in (product_url, image_url):
        if not candidate:
            continue
        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/"
    return "https://www.mouser.com/"


def _mouser_browser_headers(*, referer: str, for_image: bool) -> dict[str, str]:
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
    }
    if for_image:
        headers.update(
            {
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "same-site",
            }
        )
    else:
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            }
        )
    return headers


def _save_image_bytes(data: bytes, dest_path: Path, ctype: str) -> tuple[bool, str, int]:
    if len(data) < 400:
        return False, f"слишком мало байт: {len(data)}", len(data)
    if not ctype.startswith("image/"):
        ext = _image_ext_from_bytes(data, ctype)
        if ext == ".img":
            return False, f"не image/*: {ctype or 'unknown'}", len(data)
        ctype = {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(ext, ctype)
    ext = _image_ext_from_bytes(data, ctype)
    if dest_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        dest_path = dest_path.with_suffix(ext)

    # Не сохраняем очевидные "заглушки" (коллажи нескольких корпусов на белом фоне),
    # даже если картинка формально скачалась.
    try:
        # Дешёвый предфильтр: анализируем только типовой диапазон размеров
        # (у наших заглушек это порядка ~33KB) и только растровые форматы.
        if (
            ctype in {"image/jpeg", "image/png"}
            and 20000 <= len(data) <= 50000
            and _looks_like_placeholder_collage(data)
        ):
            return False, "placeholder_collage", len(data)
    except Exception:  # noqa: BLE001
        pass

    dest_path.write_bytes(data)
    return True, ctype, len(data)


def _looks_like_placeholder_collage(data: bytes) -> bool:
    """
    Heuristics for "package icon collages":
    несколько корпусов на белом фоне, низкая вариативность и "типовой" рисунок.
    """
    # Быстрые отсеивания: если Pillow не откроет — не считаем заглушкой.
    if len(data) < 15000:
        return False
    img = Image.open(io.BytesIO(data))
    # Известный шаблон заглушек: коллажи пакетов на 800×800.
    if img.size != (800, 800):
        return False
    img = img.convert("L").resize((96, 96))
    px = list(img.getdata())
    n = len(px)

    # Непрозрачность/фон: заглушки обычно имеют умеренную долю не-белых пикселей.
    frac_nonwhite = sum(1 for v in px if v < 245) / n
    dark_frac = sum(1 for v in px if v < 80) / n

    # Узкие интервалы вокруг реальных примеров пользователя.
    if not (0.10 <= frac_nonwhite <= 0.14 and 0.03 <= dark_frac <= 0.08):
        return False

    # Connected components on "dark" mask.
    mask = [v < 210 for v in px]
    w = h = 96
    visited = bytearray(n)
    comps = 0
    large = 0

    for i in range(n):
        if not mask[i] or visited[i]:
            continue
        comps += 1
        visited[i] = 1
        stack = [i]
        size = 0
        while stack:
            j = stack.pop()
            size += 1
            x = j % w
            y = j // w

            # 4-neighborhood
            if x > 0:
                ni = j - 1
                if mask[ni] and not visited[ni]:
                    visited[ni] = 1
                    stack.append(ni)
            if x + 1 < w:
                ni = j + 1
                if mask[ni] and not visited[ni]:
                    visited[ni] = 1
                    stack.append(ni)
            if y > 0:
                ni = j - w
                if mask[ni] and not visited[ni]:
                    visited[ni] = 1
                    stack.append(ni)
            if y + 1 < h:
                ni = j + w
                if mask[ni] and not visited[ni]:
                    visited[ni] = 1
                    stack.append(ni)

        if size >= 30:
            large += 1

    # "Иконка-коллаж": примерно 11 компонент и около 9 крупных.
    return (10 <= comps <= 12) and (large >= 8)


def download_mouser_image(
    image_url: str,
    dest_path: Path,
    *,
    product_url: str = "",
    timeout: float = 30.0,
) -> tuple[bool, str, int]:
    """Скачать ImagePath с сайта Mouser (нужен VPN EU/US)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    referer = product_url or mouser_referer_for(product_url, image_url)
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    if product_url:
        try:
            req_page = urllib.request.Request(
                product_url, headers=_mouser_browser_headers(referer=mouser_referer_for("", image_url), for_image=False)
            )
            opener.open(req_page, timeout=timeout).read(65536)
            referer = product_url
        except urllib.error.URLError:
            pass

    req = urllib.request.Request(
        image_url, headers=_mouser_browser_headers(referer=referer, for_image=True)
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except urllib.error.URLError as e:
        return False, str(e.reason), 0

    ok, detail, nbytes = _save_image_bytes(data, dest_path, ctype)
    if ok:
        return ok, detail, nbytes

    # Повтор: только домен в Referer
    referer2 = mouser_referer_for(product_url, image_url)
    if referer2 != referer:
        req2 = urllib.request.Request(
            image_url, headers=_mouser_browser_headers(referer=referer2, for_image=True)
        )
        try:
            with opener.open(req2, timeout=timeout) as resp:
                data = resp.read()
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            return _save_image_bytes(data, dest_path, ctype)
        except urllib.error.URLError as e:
            return False, str(e.reason), 0
    return False, detail, nbytes


def clean_web_artifacts(out_dir: Path) -> list[str]:
    """Удалить отчёты, кэш DDG и скачанные web-картинки. Возвращает список действий."""
    removed: list[str] = []
    for name in ("web_probe.csv", "web_report.csv", "web_not_found.csv"):
        p = out_dir / name
        if p.is_file():
            p.unlink()
            removed.append(str(p))
    for rel in ("images/web", "_cache/ddg"):
        d = out_dir / rel
        if d.is_dir():
            shutil.rmtree(d)
            removed.append(str(d) + "/")
    return removed


def clean_mouser_artifacts(out_dir: Path) -> list[str]:
    """Удалить отчёты Mouser, кэш API и скачанные mouser-картинки."""
    removed: list[str] = []
    for name in ("mouser_probe.csv", "mouser_report.csv", "mouser_not_found.csv"):
        p = out_dir / name
        if p.is_file():
            p.unlink()
            removed.append(str(p))
    for rel in ("images/mouser", "_cache/mouser"):
        d = out_dir / rel
        if d.is_dir():
            shutil.rmtree(d)
            removed.append(str(d) + "/")
    return removed


def clean_web_cascade_artifacts(out_dir: Path) -> list[str]:
    removed = clean_web_artifacts(out_dir)
    removed.extend(clean_web2_artifacts(out_dir))
    for name in ("web_cascade_report.csv", "web_cascade_not_found.csv", "web_v1_fallback.csv"):
        p = out_dir / name
        if p.is_file():
            p.unlink()
            removed.append(str(p))
    return removed


def clean_web2_artifacts(out_dir: Path) -> list[str]:
    """Удалить отчёты v2, кэш листингов/DDGS text и скачанные web2-картинки."""
    removed: list[str] = []
    for name in (
        "web2_probe.csv",
        "web2_report.csv",
        "web2_not_found.csv",
        "web2_stats.csv",
    ):
        p = out_dir / name
        if p.is_file():
            p.unlink()
            removed.append(str(p))
    for rel in ("images/web2", "_cache/listings", "_cache/ddg_text"):
        d = out_dir / rel
        if d.is_dir():
            shutil.rmtree(d)
            removed.append(str(d) + "/")
    return removed
