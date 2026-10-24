from pathlib import Path

import pytest

from napolnenie.parser import parse_xlsx
from napolnenie.query import apply_queries_all

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
SAMPLE = list(RAW.glob("*.xlsx"))


@pytest.mark.skipif(not SAMPLE, reason="нет xlsx в data/raw")
def test_parse_sample_row_count():
    result = parse_xlsx(SAMPLE[0])
    rows = apply_queries_all(result.rows)
    assert result.group == "BGA чип и микросхема для ноутбуков"
    assert len(rows) == 203  # без строки «Итого»
    empty_e = [r for r in rows if not r.art_e]
    assert 55 <= len(empty_e) <= 58
    assert any(r.query_sent == "NB669AEVD" for r in empty_e)
