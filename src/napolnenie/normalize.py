from __future__ import annotations

import re
from pathlib import Path

import yaml

_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "normalize_rules.yaml"
_TAIL_1C_RE = re.compile(r",\s*\d{6,}\s*$")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁёІі]")


def load_rules(path: Path | None = None) -> dict:
    p = path or _RULES_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def strip_1c_tail(series_raw: str) -> str:
    return _TAIL_1C_RE.sub("", series_raw).strip()


def split_series_head(series_raw: str) -> str:
    s = strip_1c_tail(series_raw)
    if "," in s:
        head, _ = s.split(",", 1)
        return head.strip().rstrip(",").strip()
    return s.strip().rstrip(",").strip()


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text))


def fix_homoglyphs(text: str, mapping: dict[str, str]) -> str:
    return "".join(mapping.get(ch, ch) for ch in text)


def collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def remove_consecutive_dup_tokens(text: str) -> str:
    tokens = text.split()
    out: list[str] = []
    for tok in tokens:
        if not out or out[-1].lower() != tok.lower():
            out.append(tok)
    return " ".join(out)


def remove_cyrillic_tokens(text: str) -> str:
    return " ".join(t for t in text.split() if not has_cyrillic(t))


def strip_mfr_prefix(text: str, whitelist: set[str]) -> str:
    tokens = text.split()
    if tokens and tokens[0].upper() in whitelist:
        return " ".join(tokens[1:])
    return text


def is_verified(art_e: str, series_head: str) -> bool:
    if not art_e:
        return False
    if art_e == series_head:
        return True
    if art_e in series_head:
        return True
    return art_e in series_head.split()


def normalize_g_head(g_head: str, rules: dict | None = None) -> tuple[str, list[str], str]:
    """Возвращает (primary_query, fallback_queries, rule_name)."""
    rules = rules or load_rules()
    homo: dict[str, str] = rules.get("omoglif_map", {})
    mfr: set[str] = {x.upper() for x in rules.get("mfr_whitelist", [])}

    h = collapse_spaces(fix_homoglyphs(g_head, homo))
    h = remove_consecutive_dup_tokens(h)
    fallbacks: list[str] = []

    tokens = h.split()
    if not tokens:
        return "", fallbacks, "empty"

    if len(tokens) == 1:
        return tokens[0], fallbacks, "A_single"

    if (
        len(tokens) == 3
        and tokens[2].replace(" ", "").lower()
        == (tokens[0] + tokens[1]).replace(" ", "").lower()
    ):
        return tokens[2].upper(), [tokens[0]], "B_join_3tok"

    if has_cyrillic(h):
        cleaned = remove_cyrillic_tokens(h)
        if cleaned:
            h = cleaned
            tokens = h.split()
            if len(tokens) == 1:
                return tokens[0], fallbacks, "D_cyr_noise"

    h_mfr = strip_mfr_prefix(h, mfr)
    if h_mfr != h:
        h = h_mfr
        tokens = h.split()
        if len(tokens) == 1:
            return tokens[0], fallbacks, "mfr_whitelist"

    tokens = h.split()
    if len(tokens) == 1:
        return tokens[0], fallbacks, "A_single"

    if len(tokens) == 2 and len(tokens[1]) == 1 and tokens[1].isalpha():
        primary = f"{tokens[0]}-{tokens[1].upper()}"
        return primary, [tokens[0]], "dash_2tok"

    if len(tokens) == 2 and tokens[1].lower().startswith(tokens[0].lower()):
        suffix = tokens[1][len(tokens[0]) :]
        primary = (tokens[0] + suffix).upper()
        return primary, [tokens[0]], "LTC_like"

    if len(tokens) == 2:
        primary = (tokens[0] + tokens[1]).upper()
        return primary, [tokens[0]], "C_join_2tok"

    if len(tokens) >= 2:
        primary = "".join(tokens).upper()
        return primary, [tokens[0]], "Z_multi_join"

    return h.replace(" ", "").upper(), fallbacks, "Z_fallback"
