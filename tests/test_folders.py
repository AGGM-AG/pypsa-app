"""Tests for in-place registration of result folders."""

import sys
from pathlib import Path

import pandas as pd
import pypsa
import pytest
from fastapi.testclient import TestClient

import pypsa_app.backend.services.views as views_module
from pypsa_app.backend.api.routes import folders as folders_routes
from pypsa_app.backend.api.routes import tasks as tasks_routes
from pypsa_app.backend.api.routes import views as views_routes
from pypsa_app.backend.settings import API_V1_PREFIX

sys.path.insert(0, str(Path(__file__).parent))


def _write(path: Path, year: str, run: str = "KN2040") -> Path:
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2013-01-01", periods=2, freq="h"))
    n.add("Bus", "b0", carrier="AC")
    n.meta = {"wildcards": {"planning_horizons": year, "run": run}}
    path.parent.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(path)
    return path


@pytest.fixture
def results_root(tmp_path: Path) -> Path:
    root = tmp_path / "results"
    run = root / "prefix" / "KN2040" / "networks"
    _write(run / "base_s_adm__none_2030.nc", "2030")
    _write(run / "base_s_adm__none_2040.nc", "2040")
    return root


@pytest.fixture
def client(app_factory, results_root: Path):
    views_module.reset_extensions()
    app = app_factory(
        (folders_routes.router, f"{API_V1_PREFIX}/folders"),
        (views_routes.router, f"{API_V1_PREFIX}/views"),
        (tasks_routes.router, f"{API_V1_PREFIX}/tasks"),
        network_roots=str(results_root),
        extensions="fake_extension",
    )
    yield TestClient(app)
    views_module.reset_extensions()


def test_register_folder(client: TestClient, results_root: Path):
    folder = results_root / "prefix" / "KN2040"
    r = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": str(folder)}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "KN2040"
    assert body["path"] == str(folder.resolve())
    assert [n["filename"] for n in body["networks"]] == ["KN2040 2030", "KN2040 2040"]

    # idempotent
    r2 = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": str(folder)}
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == body["id"]

    listed = client.get(f"{API_V1_PREFIX}/folders/").json()["data"]
    assert [f["id"] for f in listed] == [body["id"]]
    assert client.get(f"{API_V1_PREFIX}/folders/{body['id']}").status_code == 200


def test_register_outside_roots_is_forbidden(client: TestClient, tmp_path: Path):
    other = tmp_path / "elsewhere"
    _write(other / "a_2030.nc", "2030")
    r = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": str(other)}
    )
    assert r.status_code == 403


def test_register_requires_roots(app_factory, results_root: Path):
    app = app_factory((folders_routes.router, f"{API_V1_PREFIX}/folders"))
    client = TestClient(app)
    r = client.post(
        f"{API_V1_PREFIX}/folders/register",
        json={"absolute_path": str(results_root / "prefix" / "KN2040")},
    )
    assert r.status_code == 403
    assert "NETWORK_ROOTS" in r.json()["detail"]


def test_register_rejects_relative_and_empty(client: TestClient, results_root: Path):
    r = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": "relative/path"}
    )
    assert r.status_code == 400
    empty = results_root / "empty"
    empty.mkdir()
    r = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": str(empty)}
    )
    assert r.status_code == 400
    assert "No .nc files" in r.json()["detail"]


def test_generate_view_for_folder(client: TestClient, results_root: Path):
    folder = results_root / "prefix" / "KN2040"
    folder_id = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": str(folder)}
    ).json()["id"]
    r = client.post(
        f"{API_V1_PREFIX}/views/generate",
        json={"folder_id": folder_id, "view": "view_bus_count", "parameters": {}},
    )
    assert r.status_code == 200, r.text
    status_url = r.json()["status_url"]
    for _ in range(50):
        status = client.get(status_url).json()
        if status["state"] in ("SUCCESS", "FAILURE"):
            break
    assert status["result"]["status"] == "success", status
    assert status["result"]["data"]["data"][0]["y"] == [1, 1]


def test_delete_folder_keeps_files(client: TestClient, results_root: Path):
    folder = results_root / "prefix" / "KN2040"
    folder_id = client.post(
        f"{API_V1_PREFIX}/folders/register", json={"absolute_path": str(folder)}
    ).json()["id"]
    r = client.delete(f"{API_V1_PREFIX}/folders/{folder_id}")
    assert r.status_code == 200
    assert client.get(f"{API_V1_PREFIX}/folders/{folder_id}").status_code == 404
    assert len(list((folder / "networks").glob("*.nc"))) == 2
