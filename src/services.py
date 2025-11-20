import json
import re
import secrets
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import UploadFile, HTTPException, status

from .config import UPLOAD_DIR, MAX_UPLOAD_SIZE


class SessionManager:
    def __init__(self):
        self._manifests: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()
        UPLOAD_DIR.mkdir(exist_ok=True)

    def init_session(self) -> str:
        session_id = secrets.token_urlsafe(16)
        session_dir = UPLOAD_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._manifests[session_id] = {}
        return session_id

    def register_file(
        self, session_id: str, stored_name: str, original_name: str
    ) -> None:
        with self._lock:
            manifest = self._manifests.setdefault(session_id, {})
            manifest[stored_name] = original_name

    def get_manifest(self, session_id: str) -> Optional[Dict[str, str]]:
        with self._lock:
            manifest = self._manifests.get(session_id)
            if manifest is None:
                return None
            return dict(manifest)

    def cleanup_session(self, session_id: str) -> None:
        session_dir = UPLOAD_DIR / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        with self._lock:
            self._manifests.pop(session_id, None)

    def store_results(self, session_id: str, payload: Dict) -> None:
        session_dir = UPLOAD_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        target = session_dir / "results.json"
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def load_results(self, session_id: str) -> Optional[Dict]:
        session_dir = UPLOAD_DIR / session_id
        target = session_dir / "results.json"
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def resolve_path(self, session_id: str, filename: str) -> Path:
        session_dir = UPLOAD_DIR / session_id
        safe_name = Path(filename or "").name
        target = session_dir / safe_name
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(
                f"File {safe_name} not found in session {session_id}"
            )
        return target


session_manager = SessionManager()


def sanitize_filename(name: str) -> str:
    cleaned = (name or "file").strip() or "file"
    return re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)


def ensure_unique_filename(directory: Path, filename: str) -> str:
    candidate = filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while (directory / candidate).exists():
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def save_uploaded_file(
    upload: UploadFile, expected_suffix: str, session_id: str
) -> Optional[Dict[str, str]]:
    if not upload.filename or not upload.filename.lower().endswith(expected_suffix):
        return None

    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)

    if size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Файл {upload.filename} превышает лимит {MAX_UPLOAD_SIZE // 1024 // 1024}MB",
        )

    sanitized = sanitize_filename(upload.filename)
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    stored_name = ensure_unique_filename(session_dir, sanitized)
    target_path = session_dir / stored_name

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)

    session_manager.register_file(session_id, stored_name, upload.filename)
    return {"filename": stored_name, "label": upload.filename}


def _names_match(left: str, right: str) -> bool:
    """Return True when filenames match exactly by stem (case-insensitive)."""
    left_stem = Path(left).stem.lower()
    right_stem = Path(right).stem.lower()
    return left_stem == right_stem


def auto_pair_files(
    puml_files: List[Dict[str, str]],
    json_files: List[Dict[str, str]],
) -> Tuple[List[Dict[str, Optional[Dict[str, str]]]], List[Dict[str, str]]]:
    used_json = set()
    pairings = []
    for puml in puml_files:
        match = None
        for candidate in json_files:
            if candidate["filename"] in used_json:
                continue
            if _names_match(puml["label"], candidate["label"]):
                match = candidate
                used_json.add(candidate["filename"])
                break
        pairings.append({"puml": puml, "json": match})

    unmatched_json = [
        entry for entry in json_files if entry["filename"] not in used_json
    ]
    return pairings, unmatched_json


def normalize_attribute_scores(results: List[dict]) -> List[dict]:
    """Ensure empty attribute sets are treated as perfect matches for display."""
    for result in results:
        attrs = result.get("attributes")
        if not attrs:
            continue

        if attrs.get("etalon_count", 0) == 0 and attrs.get("student_count", 0) == 0:
            attrs["precision"] = 1.0
            attrs["recall"] = 1.0
            attrs["f1"] = 1.0

    return results
