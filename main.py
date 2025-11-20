#!/usr/bin/env python3
"""
Точка входа для запуска веб-приложения PUML Comparator
"""

import uvicorn
from src.main import app


def main(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Запускает Uvicorn сервер для web-приложения."""
    print("🚀 Запуск PUML vs JSON Comparator...")
    print(f"✨ Приложение доступно на http://{host}:{port}")
    print("Нажмите Ctrl+C для остановки\n")

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
