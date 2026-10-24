from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductRow:
    source_file: str
    row_num: int
    group: str
    series_raw: str
    series_head: str
    art_e: str
    desc: str
    series_clean: str = ""
    query_sent: str = ""
    query_fallback: str = ""
    normalize_rule: str = ""
    verified: bool = False


@dataclass
class ParseResult:
    source_file: str
    group: str
    rows: list[ProductRow] = field(default_factory=list)
