# Блок-схема проекта (источник)



**Смотреть картинку:** двойной щелчок `docs/block-scheme.html` (браузер).



Обновлять при **новых идеях** — **и** этот файл, **и** `block-scheme.html` (одинаковый mermaid).



**Детали** — в `docs/ARCHITECTURE.md`.



## Легенда



| Статус | В подписи узла |

|--------|----------------|

| Идея / позже | `(planned)` |

| В работе | `(in_progress)` |

| Заблокирован | `(blocked)` |

| Готово | `(done)` |



## Поток поиска картинок



```mermaid

flowchart TB

  subgraph input [Вход done]

    XLSX["1C xlsx data/raw"]

    Parse["parser + parse CLI"]

  end

  subgraph norm [Нормализация done]

    Echk{E zapolnena?}

    UseE["query_sent = E"]

    Norm["normalize G-head"]

    UseG["query_sent = series_clean"]

  end

  subgraph search [Poisk]

    Mouser["Mouser API blocked"]

    DK["Digi-Key API planned"]

    Web["DDG + gruppa in_progress"]

  end

  subgraph out [Vyhod in_progress]

    Save["web_report + images/web"]

    NF["web_not_found"]

    Review["needs_review"]

  end

  XLSX --> Parse --> Echk

  Echk -->|da| UseE

  Echk -->|net| Norm --> UseG

  UseE --> Mouser

  UseG --> Mouser

  Mouser -->|hit| Save

  Mouser -->|miss| DK

  DK -->|hit| Save

  DK -->|miss| Web

  Web -->|MPN match| Review

  Web -->|no match| NF

  Review --> Save

```



## Этапы реализации



```mermaid

flowchart LR

  M0["M0 docs done"]

  M1["M1 parser done"]

  M2["M2 Mouser blocked"]

  M3["M3 DigiKey planned"]

  M4["M4 pipeline planned"]

  M5["M5 web in_progress"]

  M0 --> M1 --> M2 --> M3 --> M4 --> M5

```



## История схемы



| Дата | Что изменили |

|------|----------------|

| 2026-05-26 | Поток поиска картинок, этапы M0–M5 |

| 2026-05-26 | Статусы: M1 done, M2 blocked, M5 in_progress; веб-выход `images/web` |
| 2026-05-26 | M5 v2: trusted listings (Theretroweb/dfi/chipsetpro) поверх v1; сравнение покрытия |


