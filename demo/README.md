# Демо-данные пайплайна (синтетические)

Все данные выдуманы и не относятся ни к одному реальному клиенту.

- `input_demo.csv` — фрагмент выгрузки из 1С: позиции без изображений (колонки: sku, mpn, name, qty)
- `output_demo.csv` — пример итогового отчёта пайплайна (колонки: sku, mpn, image_path, source, confidence, status)

## Логика отчёта

- `mouser_api` → confidence 0.95, status `found` (доверенный источник)
- `web_search` → confidence 0.5, status `needs_review` (требуется ручная проверка)
- ничего не найдено → status `not_found`

Полный запуск пайплайна — в корневом README (раздел «Запуск»).
