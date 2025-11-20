from pathlib import Path

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
