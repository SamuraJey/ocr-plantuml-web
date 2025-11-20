import io
from types import SimpleNamespace
from pathlib import Path

import pytest

from src import main
from src.services import session_manager


def test_normalize_attribute_scores_sets_neutral_metrics():
    results = [
        {
            "attributes": {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "etalon_count": 0,
                "student_count": 0,
                "matched": 0,
            }
        }
    ]

    normalized = main.normalize_attribute_scores(results)
    attrs = normalized[0]["attributes"]

    assert attrs["precision"] == 1.0
    assert attrs["recall"] == 1.0
    assert attrs["f1"] == 1.0


def test_normalize_attribute_scores_leaves_real_counts():
    results = [
        {
            "attributes": {
                "precision": 0.5,
                "recall": 0.25,
                "f1": 0.333,
                "etalon_count": 4,
                "student_count": 2,
                "matched": 1,
            }
        }
    ]

    normalized = main.normalize_attribute_scores(results)
    attrs = normalized[0]["attributes"]

    assert attrs["precision"] == 0.5
    assert attrs["recall"] == 0.25
    assert attrs["f1"] == 0.333


def test_auto_pair_files_matches_by_stem():
    puml = [{"filename": "Foo.puml", "label": "Foo"}]
    json = [{"filename": "foo.json", "label": "foo"}]

    pairings, unmatched = main.auto_pair_files(puml, json)

    assert pairings[0]["json"]["filename"] == "foo.json"
    assert unmatched == []


def test_auto_pair_files_marks_unmatched():
    puml = [{"filename": "Bar.puml", "label": "Bar"}]
    json = [{"filename": "Baz.json", "label": "Baz"}]

    pairings, unmatched = main.auto_pair_files(puml, json)

    assert pairings[0]["json"] is None
    assert unmatched[0]["filename"] == "Baz.json"


def test_auto_pair_files_requires_exact_match():
    puml = [{"filename": "2_4.puml", "label": "2_4"}]
    json = [{"filename": "2_4_detected.json", "label": "2_4_detected"}]

    pairings, unmatched = main.auto_pair_files(puml, json)

    assert pairings[0]["json"] is None
    assert unmatched[0]["filename"] == "2_4_detected.json"


def test_upload_sessions_are_isolated(tmp_path, monkeypatch):
    # Patch UPLOAD_DIR in services module where it is used
    monkeypatch.setattr("src.services.UPLOAD_DIR", tmp_path)

    # Create new session manager instances to avoid shared state or just use the global one
    # Since session_manager is global in services, we need to ensure it uses the patched dir
    # The SessionManager uses UPLOAD_DIR from config imported into services.
    # We patched src.services.UPLOAD_DIR.

    # We also need to reset the manifests for the test
    session_manager._manifests = {}

    session_a = session_manager.init_session()
    session_b = session_manager.init_session()

    assert session_a != session_b

    upload = SimpleNamespace(filename="diagram.puml", file=io.BytesIO(b"class Foo {}"))
    stored = main.save_uploaded_file(upload, ".puml", session_a)
    assert stored is not None

    manifest_a = session_manager.get_manifest(session_a)
    manifest_b = session_manager.get_manifest(session_b)

    assert stored["filename"] in manifest_a
    assert manifest_b == {}

    session_dir_a = tmp_path / session_a
    session_dir_b = tmp_path / session_b

    resolved = session_manager.resolve_path(session_a, stored["filename"])
    assert resolved.read_bytes() == b"class Foo {}"

    with pytest.raises(FileNotFoundError):
        session_manager.resolve_path(session_b, stored["filename"])

    session_manager.cleanup_session(session_a)
    session_manager.cleanup_session(session_b)


def test_store_and_load_results_payload(tmp_path, monkeypatch):
    monkeypatch.setattr("src.services.UPLOAD_DIR", tmp_path)
    session_manager._manifests = {}

    session_id = session_manager.init_session()

    payload = {
        "results": [
            {
                "etalon_file": "Foo.puml",
                "student_file": "Foo.json",
                "score": 95.0,
            }
        ],
        "stats": {"total_comparisons": 1, "avg_score": 95.0},
        "chart_labels": ["Foo"],
        "chart_scores": [95.0],
    }

    session_manager.store_results(session_id, payload)
    loaded = session_manager.load_results(session_id)

    assert loaded == payload

    session_manager.cleanup_session(session_id)
