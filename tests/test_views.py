"""Tests for the view extension hook."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pypsa_app.backend.services.views as views_module
from pypsa_app.backend.api.routes import networks as networks_routes
from pypsa_app.backend.api.routes import tasks as tasks_routes
from pypsa_app.backend.api.routes import views as views_routes
from pypsa_app.backend.settings import API_V1_PREFIX

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def client(app_factory, monkeypatch: pytest.MonkeyPatch, nc_file: Path):
    views_module.reset_extensions()
    app = app_factory(
        (views_routes.router, f"{API_V1_PREFIX}/views"),
        (tasks_routes.router, f"{API_V1_PREFIX}/tasks"),
        (networks_routes.router, f"{API_V1_PREFIX}/networks"),
        extensions="fake_extension",
    )
    yield TestClient(app)
    views_module.reset_extensions()


def _register(client: TestClient, nc_file: Path, tmp_path: Path) -> str:
    """Create a network record for nc_file through the import service."""
    import uuid

    from pypsa_app.backend.models import User
    from pypsa_app.backend.services.network import import_network_file

    db = client.app.dependency_overrides[
        next(k for k in client.app.dependency_overrides if k.__name__ == "get_db")
    ]()
    session = next(db)
    user = session.query(User).first()
    copy = tmp_path / f"{uuid.uuid4()}.nc"
    copy.write_bytes(nc_file.read_bytes())
    network = import_network_file(copy, "sample.nc", user.id, session)
    session.commit()
    return str(network.id)


def _poll(client: TestClient, status_url: str) -> dict:
    for _ in range(50):
        status = client.get(status_url).json()
        if status["state"] in ("SUCCESS", "FAILURE"):
            return status
    msg = "task did not finish"
    raise AssertionError(msg)


def test_list_views(client: TestClient):
    r = client.get(f"{API_V1_PREFIX}/views/")
    assert r.status_code == 200
    body = r.json()
    assert body["extensions"] == ["fake_extension"]
    assert body["data"][0]["name"] == "view_bus_count"
    assert "location" in body["data"][0]["params_schema"]["properties"]


def test_generate_view(client: TestClient, nc_file: Path, tmp_path: Path):
    network_id = _register(client, nc_file, tmp_path)
    r = client.post(
        f"{API_V1_PREFIX}/views/generate",
        json={
            "network_ids": [network_id],
            "view": "view_bus_count",
            "parameters": {"location": "AT"},
        },
    )
    assert r.status_code == 200, r.text
    status = _poll(client, r.json()["status_url"])
    assert status["state"] == "SUCCESS"
    result = status["result"]
    assert result["status"] == "success", result
    assert result["data"]["data"][0]["y"] == [1]
    assert result["data"]["layout"]["title"]["text"] == "view_bus_count AT"


def test_generate_unknown_view(client: TestClient, nc_file: Path, tmp_path: Path):
    network_id = _register(client, nc_file, tmp_path)
    r = client.post(
        f"{API_V1_PREFIX}/views/generate",
        json={"network_ids": [network_id], "view": "nope", "parameters": {}},
    )
    assert r.status_code == 400


def test_view_selections(client: TestClient, nc_file: Path, tmp_path: Path):
    network_id = _register(client, nc_file, tmp_path)
    r = client.post(
        f"{API_V1_PREFIX}/views/selections",
        json={"network_ids": [network_id], "extension": "fake_extension"},
    )
    assert r.status_code == 200, r.text
    status = _poll(client, r.json()["status_url"])
    assert status["result"]["data"]["locations"] == ["AT"]


def test_extension_without_render_is_rejected(monkeypatch: pytest.MonkeyPatch):
    import types

    module = types.ModuleType("broken_extension")
    module.list_views = list
    monkeypatch.setitem(sys.modules, "broken_extension", module)
    monkeypatch.setattr(views_module.settings, "extensions", "broken_extension")
    views_module.reset_extensions()
    with pytest.raises(TypeError, match="lacks a callable"):
        views_module.get_extensions()
    views_module.reset_extensions()
