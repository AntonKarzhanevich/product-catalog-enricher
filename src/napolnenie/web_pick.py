from __future__ import annotations

from napolnenie.sources.base import ImageHit

# Типовые «учебные» картинки BGA без привязки к MPN
_GENERIC_MARKERS = (
    "new_bga_chip",
    "курс по пайке",
    "что такое bga",
    "замена bga",
    "bga_mask",
    "remove_bga",
    "bga_placement",
)


def _blob(hit: ImageHit) -> str:
    return " ".join((hit.description, hit.image_url, hit.product_url)).lower()


def hit_matches_mpn(mpn: str, hit: ImageHit) -> bool:
    if not mpn:
        return False
    text = _blob(hit).replace("-", "")
    key = mpn.lower().replace("-", "")
    return key in text


def is_generic_stock(hit: ImageHit) -> bool:
    blob = _blob(hit)
    return any(m in blob for m in _GENERIC_MARKERS)


def pick_best_hit(
    query_sent: str,
    hits: list[ImageHit],
    used_urls: set[str],
) -> ImageHit | None:
    """Выбрать картинку: MPN в тексте/URL, не дубль URL, без generic BGA stock."""
    mpn = query_sent.strip()
    if not mpn or not hits:
        return None

    strong: list[ImageHit] = []
    for hit in hits:
        if not hit.image_url or hit.image_url in used_urls:
            continue
        if is_generic_stock(hit) and not hit_matches_mpn(mpn, hit):
            continue
        if hit_matches_mpn(mpn, hit):
            strong.append(hit)

    if strong:
        return strong[0]

    return None
