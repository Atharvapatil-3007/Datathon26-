"""F-01: app-layer per-user data isolation.

Every read / write path accepts an optional ``user_id``. When present, a
caller must own the row or the API replies as if the row did not exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database.supabase import get_supabase_service
from app.ingestion.exceptions import DatasetNotFoundError
from app.ingestion.manager import get_ingestion_manager
from app.main import app


def _ingest(csv_path: Path, *, user_id: str | None = None) -> str:
    manager = get_ingestion_manager()
    result, _ = manager.ingest_file(
        temp_path=str(csv_path),
        filename=csv_path.name,
        mime_type="text/csv",
        user_id=user_id,
    )
    return result.dataset.dataset_id


def test_list_datasets_filters_by_user(csv_file: Path) -> None:
    alice_id = _ingest(csv_file, user_id="alice")
    bob_id = _ingest(csv_file, user_id="bob")
    manager = get_ingestion_manager()

    alice_view = {r["id"] for r in manager.list_datasets(user_id="alice")}
    bob_view = {r["id"] for r in manager.list_datasets(user_id="bob")}
    unscoped = {r["id"] for r in manager.list_datasets()}

    assert alice_view == {alice_id}
    assert bob_view == {bob_id}
    assert unscoped >= {alice_id, bob_id}


def test_get_dataset_denied_for_wrong_user(csv_file: Path) -> None:
    alice_id = _ingest(csv_file, user_id="alice")
    service = get_supabase_service()

    # Owner can read.
    assert service.get_dataset(alice_id, user_id="alice")["id"] == alice_id

    # Non-owner sees a 404-shaped response \u2014 existence is not leaked.
    with pytest.raises(DatasetNotFoundError):
        service.get_dataset(alice_id, user_id="bob")


def test_delete_dataset_denied_for_wrong_user(csv_file: Path) -> None:
    alice_id = _ingest(csv_file, user_id="alice")
    manager = get_ingestion_manager()

    with pytest.raises(DatasetNotFoundError):
        manager.delete_dataset(alice_id, user_id="bob")

    # Row must still be reachable by the real owner.
    assert manager.get_dataset_summary(alice_id, user_id="alice") is not None


def test_http_layer_threads_x_user_id_header(csv_file: Path) -> None:
    _ingest(csv_file, user_id="alice")
    _ingest(csv_file, user_id="bob")

    client = TestClient(app)
    r_alice = client.get("/api/v1/datasets", headers={"X-User-Id": "alice"})
    r_bob = client.get("/api/v1/datasets", headers={"X-User-Id": "bob"})
    r_unscoped = client.get("/api/v1/datasets")

    assert r_alice.status_code == 200
    assert r_bob.status_code == 200
    assert r_unscoped.status_code == 200

    alice_rows = r_alice.json()
    bob_rows = r_bob.json()
    unscoped_rows = r_unscoped.json()

    assert all(row["user_id"] == "alice" for row in alice_rows)
    assert all(row["user_id"] == "bob" for row in bob_rows)
    assert len(unscoped_rows) >= len(alice_rows) + len(bob_rows)
