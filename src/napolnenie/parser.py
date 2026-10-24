from __future__ import annotations

import re
from pathlib import Path

import openpyxl

from napolnenie.models import ParseResult, ProductRow

OTBOR_LABEL = "отбор:"
SERIES_HEADER = "номенклатура, серия"
ART_HEADER = "артикул"
GROUP_RE = re.compile(r'В группе\s*["«]([^"»]+)["»]', re.IGNORECASE)


def _cell_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _find_group(rows: list[tuple]) -> str:
    for row in rows[:15]:
        if not row:
            continue
        label = _cell_str(row[0]).lower()
        if label.startswith(OTBOR_LABEL):
            text = _cell_str(row[2]) if len(row) > 2 else ""
            if not text:
                for cell in row[1:]:
                    text = _cell_str(cell)
                    if text:
                        break
            m = GROUP_RE.search(text.replace("\n", " "))
            if m:
                return m.group(1).strip()
    return ""


def _find_header_row(rows: list[tuple]) -> tuple[int, dict[str, int]]:
    for idx, row in enumerate(rows[:20]):
        cols: dict[str, int] = {}
        for col_idx, cell in enumerate(row):
            name = _cell_str(cell).lower()
            if not name:
                continue
            if SERIES_HEADER in name:
                cols["series"] = col_idx
            if name == ART_HEADER:
                cols["art"] = col_idx
            if "текстовое описание" in name:
                cols["desc"] = col_idx
        if "series" in cols:
            return idx, cols
    raise ValueError('Не найдена строка шапки с колонкой "Номенклатура, Серия"')


def parse_xlsx(path: Path) -> ParseResult:
    path = Path(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    group = _find_group(rows)
    header_idx, cols = _find_header_row(rows)
    data_start = header_idx + 2

    series_col = cols["series"]
    art_col = cols.get("art")
    desc_col = cols.get("desc")

    products: list[ProductRow] = []
    for row_idx, row in enumerate(rows[data_start:], start=data_start + 1):
        if not row or not any(row):
            continue
        series_raw = _cell_str(row[series_col]) if series_col < len(row) else ""
        if not series_raw or series_raw.lower() in ("итого", "всего"):
            continue

        art_e = _cell_str(row[art_col]) if art_col is not None and art_col < len(row) else ""
        desc = _cell_str(row[desc_col]) if desc_col is not None and desc_col < len(row) else ""

        from napolnenie.normalize import split_series_head

        products.append(
            ProductRow(
                source_file=path.name,
                row_num=row_idx,
                group=group,
                series_raw=series_raw,
                series_head=split_series_head(series_raw),
                art_e=art_e,
                desc=desc,
            )
        )

    return ParseResult(source_file=path.name, group=group, rows=products)
