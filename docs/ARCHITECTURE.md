# Архитектура



Обновлено: 2026-05-26 (синхронизация с кодом M1 + M2-код + M5).



## Назначение



Скрипт читает выгрузку 1С (xlsx без картинок), для каждой строки строит поисковый запрос по номенклатуре, находит URL/файл изображения во внешних источниках и формирует отчёт для ручной загрузки в каталог. **Описания товаров — вне v0.**



## Вход



| Источник | Поле | Роль |

|----------|------|------|

| Строка `Отбор:` | группа | В отчёт; в веб-поиске — контекст; в API — нет |

| Колонка **G** | `Номенклатура, Серия` | Первичные данные; `series_raw`; до запятой = G-head |

| Колонка **E** | `Артикул` | Если заполнен — **поисковый query**; иначе normalize(G-head) |

| Описание | лог только | `desc_log` |



Образец: `data/raw/ведомость по товарам без картинок чипы.xlsx` — 203 строки товаров, группа «BGA чип и микросхема для ноутбуков».



## Построение query



1. **E заполнена** → `query_sent = trim(E)`.

2. **E пустая** → `query_sent = normalize(G-head)` по `config/normalize_rules.yaml`.

3. **API** (Mouser, Digi-Key): в запрос уходит только `query_sent`, без группы.

4. **Веб** (DDG): `build_web_query(query_sent, group)` → MPN + до 4 слов группы.



## Модули (факт)



| Модуль | Статус | Назначение |

|--------|--------|------------|

| `parser.py` | done | Разбор xlsx, `Отбор:`, колонки G/E |

| `normalize.py` | done | Правила очистки G-head |

| `query.py` | done | `apply_queries`, `build_web_query`, `shorten_group` |

| `sources/mouser.py` | done | Mouser Search API, кэш JSON |

| `sources/web_ddg.py` | done | DuckDuckGo Images через пакет `ddgs` |

| `web_pick.py` | done | Выбор hit: MPN в title/URL, отсев generic BGA |

| `web_runner.py` | done | Прогон веба, один MPN → одна картинка на все строки 1С |

| `storage.py` | done | Скачивание, `clean_web_artifacts`, `safe_slug` |

| `network_check.py` | done | `doctor` — доступность источников |

| `cli.py` | done | `parse`, `doctor`, `mouser-probe`, `web-probe`, `web-run` |

| `sources/digikey.py` | planned | Digi-Key API (M3) |

| `pipeline.py` | planned | Единый `run`: Mouser → Digi-Key → web (M4) |



## CLI



```bash

python -m napolnenie parse "data/raw/<файл>.xlsx"   # → parsed.csv

python -m napolnenie doctor

python -m napolnenie mouser-probe                   # 5 MPN из config (M2)

python -m napolnenie web-probe --clean              # первые 30 строк parsed.csv (M5)

python -m napolnenie web-run [--limit N] [--clean]  # весь или часть каталога (M5)

```



## Выход (факт)



| Артефакт | Путь |

|----------|------|

| Разбор без сети | `data/out/parsed.csv` |

| Mouser probe | `data/out/mouser_probe.csv`, `data/out/_cache/mouser/` |

| Веб probe / run | `data/out/web_probe.csv` / `web_report.csv`, `web_not_found.csv` |

| Картинки веба | `data/out/images/web/{MPN}.jpg` (через `safe_slug(query_sent)`) |

| Кэш DDG | `data/out/_cache/ddg/*.json` |



**M4 (planned):** `data/out/report.csv`, `data/out/not_found.csv`, общий пайплайн по всем источникам.



Правило: несколько строк 1С с одним `query_sent` → одна картинка (совместимые номенклатуры).



## Внешние источники (приоритет)



1. Mouser Search API (~1000 req/день) — **ждём Enabled в Hub**

2. Digi-Key API (резерв, M3)

3. M5 v2: trusted listings (Theretroweb → dfi → chipsetpro), `needs_review` 0.7
4. M5 v1: DuckDuckGo Images (черновик, много мусора) — только для сравнения



Исследование: `research/cl.md`, `research/ds.md`. example.com — не источник MPN/картинок.



## Данные и секреты



- `.env`: `MOUSER_API_KEY`, `DIGIKEY_*` (позже)

- Шаблон: `.env.example`

- Git: не используется (`GOVERNANCE.md`)


