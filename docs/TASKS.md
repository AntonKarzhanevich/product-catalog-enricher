# Задачи (горизонт 3–7 дней)

Детальный план: `.cursor/plans/image_search_pipeline_9ff6f702.plan.md` (или копия в workspace plans).

## Этап 0 — каркас и план (M0)

- [x] Папка проекта и docs из skeleton
- [x] Цель в `AGENTS.md` / `README.md`
- [x] План v0: поиск картинок (нормализация G/E, Mouser → Digi-Key → веб)
- [x] `ARCHITECTURE.md`, `DIAGRAM.md`, `GOVERNANCE.md` под план
- [x] **Приёмка M0** — 2026-05-26

## Этап 1 — парсер и нормализация (M1)

- [x] `parser.py`: xlsx, строка `Отбор:`, колонки G и E
- [x] `normalize.py` + `config/normalize_rules.yaml` (правила 0–9)
- [x] `query.py`: E → query; иначе normalize(G-head)
- [x] CLI `parse` → `data/out/parsed.csv` (203 строки образца)
- [x] **Приёмка M1** — 2026-05-26

## Этап 2 — Mouser API (M2) — **в работе** (VPN + ключ OK)

- [x] Клиент `sources/mouser.py` + rate limit + кэш JSON
- [x] CLI `mouser-probe`, `mouser-run`, `.env.example`
- [x] VPN + ключ: `doctor` OK, API отвечает
- [x] `mouser-run` по 203 → **32/203 found** (`mouser_report.csv`)
- [ ] Скачивание картинок с Mouser (`ImagePath` → Referer/cookies)
- [ ] **Приёмка M2** (критерий: стабильный API + отчёт; не «5/5 probe» — probe-набор не в каталоге Mouser)

## Этап 3 — Digi-Key API (M3) — после Mouser или параллельно

- [ ] OAuth2, клиент `ImageSource`
- [ ] Прогон 5 позиций (miss Mouser)
- [ ] **Приёмка M3**

## Этап 4 — пайплайн и полный прогон (M4) — **на паузе**

- [ ] `pipeline.py`, `storage.py`, CLI `run`
- [ ] `report.csv`, `not_found.csv`, `data/images/`
- [ ] Полный прогон образца
- [ ] **Приёмка M4**

## Этап 5 v1 — веб-поиск через DDG Images — **в работе (fallback)**

- [x] `sources/web_ddg.py` + `web_runner.py` + `storage.py`
- [x] CLI `web-probe` / `web-run`
- [x] Прогон `web-probe --clean` (30 позиций)
- [x] Прогон `web-run --clean` (203) — 83/203 needs_review, маркетплейсы (Prom.ua и т.п.) → много мусора

## Этап 5 v2 — trusted listings (Theretroweb + dfi + chipsetpro) — **в работе**

- [x] `sources/listing_base.py` + `theretroweb.py` + `dfi.py` + `chipsetpro.py`
- [x] `web2_runner.py`: оркестратор, one-MPN-one-image, метрики per-source
- [x] CLI `web2-probe` / `web2-run` (`--clean`, `--profile`)
- [x] `config/sources/bga_laptop_ic.yaml` — профиль группы 1С
- [x] Фильтр “package icon collages” при сохранении картинок (`placeholder_collage`) в `storage.py`
- [x] Фикстуры HTML + snapshot-тесты парсеров (pytest 29/29)
- [x] Прогон `web2-run --clean` (203) — 138/203 с файлом (dfi.ua)
- [x] Прогон `web-run --clean` (203) — 122/203 с файлом; сравнение с v2
- [x] Решение: **v2 основной**, v1 — fallback на хвост v2 (каскад, не два полных прогона)
- [x] CLI `web-cascade` (web2 → web1 только на miss v2)
- [x] Прогон `web-cascade --skip-web2` (хвост v1 по готовому web2_report)
- [x] Чистый прогон `web-cascade --clean --out-dir data/out/cascade_final` после фикса фильтра (`image_quality.py`) — 172/203 с файлом
- [ ] Починить theretroweb/chipsetpro (0 hits в последнем прогоне)
- [ ] **Приёмка M5** — после каскада и M3

---

## Следующая сессия

**Статус: ждём API** (Digi-Key developer registration, Unikeyic). Не гонять повторные веб-прогоны.

После ключей:
1. **M3** Digi-Key — OAuth, `digikey-probe`, прогон miss после Mouser (~171).
2. **M2** — download Mouser для 32 found.
3. **M4** — единый `run` после M2+M3+веб.
