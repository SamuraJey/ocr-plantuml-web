# Web Application

Веб-приложение для сравнения PUML диаграмм с JSON результатами OCR.
Может быть установлено как отдельный микросервис.

## Установка

### Как отдельный пакет

```bash
cd web
pip install .
```

### В составе основного проекта

Проект `ocr-plantuml-3` автоматически включает этот веб-компонент.

## Запуск

После установки пакета:

```bash
puml-comparator-web
```

Или через `uv` из директории `web/`:

```bash
uv run puml-comparator-web
```

## Разработка

Структура проекта:

```
web/
├── pyproject.toml       # Конфигурация пакета
├── src/
│   └── web/
│       ├── run_app.py   # Точка входа
│       ├── main.py      # FastAPI приложение
│       ├── comparator.py # Логика сравнения
│       ├── static/      # Статика
│       └── templates/   # Шаблоны
```

Для запуска в режиме разработки (из корня `web/`):

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python -m web.run_app
```
