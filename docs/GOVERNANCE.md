# Правила ведения проекта

**Канон для всех агентов:** `C:\Users\karzh\ai-playbook\`

**Git:** не используется (пока не зафиксировано иное в логе ниже).

## Карта артефактов

| Артефакт | Когда обновлять |
|----------|-----------------|
| `docs/TASKS.md` | Закрыли подзадачу, добавили этап |
| `docs/ARCHITECTURE.md` | Новый компонент, смена потока данных |
| `docs/DIAGRAM.md` | Новая идея/фича, смена статуса на схеме |
| `docs/GOVERNANCE.md` | Изменили правила или лог решений |
| `.cursor/rules/*.mdc` | Новое правило для агента |
| `notes/SESSION.md` | Конец сессии — заметки на следующий раз |

## Лог решений

| Дата | Решение | Затронутые файлы |
|------|---------|------------------|
| 2026-03 | Старт проекта из `ai-playbook` skeleton | `AGENTS.md`, `docs/*` |
| 2026-05-26 | v0 только **поиск картинок**; описания — позже | `ARCHITECTURE.md`, план |
| 2026-05-26 | Первичный столбец **G** (`Номенклатура, Серия`); **E** (`Артикул`) = query, если заполнен | `normalize.py`, план |
| 2026-05-26 | Группа из `Отбор:` — в API не передаём; в веб-фолбэке — да | `query.py` |
| 2026-05-26 | Пустая E: нормализация G-head (правила 0–9, join_all + фолбэк для 2-токенных) | `config/normalize_rules.yaml` |
| 2026-05-26 | Источники: Mouser → Digi-Key → DuckDuckGo (`needs_review`) | `sources/*` |
| 2026-05-26 | example.com — не источник MPN/картинок; опционально `site_url_guess` в отчёте | `storage.py` |
| 2026-05-26 | Приоритет: покрытие > точность > скорость | план, pipeline |
| 2026-05-26 | Mouser API 403 Akamai с IP BY — не ошибка ключа; VPN/HTTPS_PROXY или M5 | `doctor` |
| 2026-05-26 | Рабочий режим: **VPN (EU/US)** для Mouser/Digi-Key; без VPN — только M5 (DDG) | решение пользователя |
| 2026-05-26 | M2 отложен (Search API Pending); до Enabled — рабочий канал **M5** (временно) | M5 |
| 2026-05-26 | **Каждая строка** parsed.csv (`row_num`) → отдельный поиск и файл `r{row_num}_{MPN}.jpg` (v1 и v2); дубли MPN не схлопываются | `web_runner.py`, `web2_runner.py` |
| 2026-05-26 | **M5 фильтры заморожены** до данных M2/M3; whitelist/blacklist/второй движок — после полного прогона Mouser и оценки веб-хвоста | `web_pick.py`, план |
| 2026-05-26 | **M4 на паузе**; M5 — полный `web-run`, доработки фильтров после картины покрытия | TASKS |
| 2026-05-26 | M5 v1 (DDG Images) даёт мусор (Prom.ua и пр.). Решение: **M5 v2** — trusted listings (Theretroweb/dfi/chipsetpro) параллельно v1, выбор после сравнения. | `web2_runner.py`, `config/sources/bga_laptop_ic.yaml` |
| 2026-05-26 | После замены `MOUSER_API_KEY` ключ читается, но `doctor`/`mouser-probe` всё ещё дают 403 Akamai (сетевой блок). Решение: M5 (v1/v2) поставить на паузу, фокус на доступе к Mouser через VPN/HTTPS_PROXY. | `docs/TASKS.md`, `notes/SESSION.md`, `data/out/mouser_probe.csv` |
| 2026-05-26 | С VPN: Mouser API OK. `mouser-run` по 203 строкам: **32 found** (~16%), probe 5/5 = 0 (ноутбучные BGA в каталоге Mouser редки). Скачивание с `ImagePath` — HTML без Referer (доработать). | `mouser_runner.py`, `mouser_report.csv` |
| 2026-05-26 | Сравнение веба v1 vs v2 (203): v2 **138** файлов (только dfi.ua), v1 **122** (много Prom.ua); пересечение **94**. **Режим поиска:** Mouser → Digi-Key → **web2** → **web1 только на хвост web2** (не параллельно, не два полных прогона). M5 на паузе до API/каскада. | `web_report.csv`, `web2_report.csv` |
| 2026-05-27 | Добавлен фильтр “package icon collages” (заглушки-коллажи) при сохранении картинок: `storage.py` определяет такие изображения по эвристикам (800×800, доля не-белых пикселей и кол-во связных тёмных областей) и не сохраняет файл (`placeholder_collage`). | `src/napolnenie/storage.py` |
| 2026-05-26 | Качество картинок Mouser (generic package) — **отложено**: сначала доделать поиск/покрытие (M3, каскад веб), ревью пригодности для 1С — после полной картины. | решение пользователя |
| 2026-05-26 | Заявка **Unikeyic API** отправлена; ожидание ответа на почту **1–2 рабочих дня** (ключ + техдок). До ответа — не блокировать M3/веб-каскад. | `https://www.unikeyic.com/solutionapi` |
| 2026-05-27 | **web-cascade** `--skip-web2`: web2=138, web1 хвост 65→36 файлов, итого **174/203** с файлом, 24 not_found. | `web_cascade_report.csv` |
| 2026-05-27 | **Generic URL/файл:** один `image_url` или sha256 на разных MPN в прогоне web2 → все строки `not_found` (`generic_duplicate_*`), хвост в web1. | `image_quality.py`, `web2_runner.py` |
| 2026-05-27 | Чистый каскад: `web-cascade --clean --out-dir data/out/cascade_final`. | `cascade_final/` |
| 2026-05-28 | Чистый каскад завершён: **172/203** с файлом (web2=142, web1 fallback=30, not_found=31); срабатываний `generic_duplicate_*` и `placeholder_collage` в этом прогоне не зафиксировано. | `data/out/cascade_final/*` |
| 2026-05-28 | **Пауза разработки API:** ждём подтверждение Digi-Key developer portal + ответ Unikeyic; веб-каскад закрыт, M3/M2-download — после ключей. | решение пользователя |
