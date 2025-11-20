#!/usr/bin/env python3
"""
Точка входа для запуска веб-приложения PUML Comparator
"""

from __future__ import annotations
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы работал импорт пакета src
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


def main(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Запускает Uvicorn сервер для web-приложения.

    Используется как точка входа из setup-script `project.scripts`.
    """
    # Импортируем app явно из пакета src
    from src.main import app

    print("🚀 Запуск PUML vs JSON Comparator...")
    print(f"✨ Приложение доступно на http://{host}:{port}")
    print("Нажмите Ctrl+C для остановки\n")

    # Импортируем uvicorn локально, чтобы пакет можно было импортировать без него
    import uvicorn

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
