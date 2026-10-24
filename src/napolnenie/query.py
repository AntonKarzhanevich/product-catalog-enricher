from __future__ import annotations

import re

from napolnenie.models import ProductRow
from napolnenie.normalize import is_verified, load_rules, normalize_g_head

_GROUP_STOP = frozenset({"для", "и", "в", "на", "по", "из", "the", "a"})


def shorten_group(group: str, max_words: int = 4) -> str:
    words = [w for w in re.split(r"\s+", group.strip()) if w and w.lower() not in _GROUP_STOP]
    return " ".join(words[:max_words])


def build_web_query(query_sent: str, group: str, max_group_words: int = 4) -> str:
    """Запрос для веб-поиска: MPN + сжатый контекст группы."""
    q = query_sent.strip()
    g = shorten_group(group, max_group_words)
    if not g:
        return q
    return f"{q} {g}"


def apply_queries(row: ProductRow, rules: dict | None = None) -> ProductRow:
    rules = rules or load_rules()

    if row.art_e:
        row.query_sent = row.art_e.strip()
        row.query_fallback = ""
        row.normalize_rule = "E_filled"
        row.verified = is_verified(row.art_e, row.series_head)
        row.series_clean = row.query_sent
        return row

    primary, fallbacks, rule = normalize_g_head(row.series_head, rules)
    row.series_clean = primary
    row.query_sent = primary
    row.query_fallback = ";".join(fallbacks)
    row.normalize_rule = rule
    row.verified = False
    return row


def apply_queries_all(rows: list[ProductRow], rules: dict | None = None) -> list[ProductRow]:
    return [apply_queries(r, rules) for r in rows]
