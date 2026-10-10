import pytest
from fastapi.testclient import TestClient

from backend.app.main import COOKIE_NAME, create_app


@pytest.fixture
def app(books):
    return create_app(books)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def multipart(files):
    return [
        (
            "files",
            (
                name,
                content,
                "application/json" if name.endswith(".json") else "text/csv",
            ),
        )
        for name, content in files.items()
    ]


def test_live_report_purchase_and_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/report")
    assert response.status_code == 200
    report = response.json()
    assert report["monthly_summary"]["profit"] == -7830
    assert report["is_sample"] is True and report["dataset_revision"] == "sample"
    assert (
        client.get("/api/report", params={"month": "2026-08"}).json()[
            "monthly_summary"
        ]["profit"]
        == 15000
    )
    purchase = client.get("/api/affordability", params={"amount": "15000"}).json()
    assert purchase["can_afford_now"] is False
    assert purchase["collection_scenario"]["can_afford"] is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/report?month=2026-07",
        "/api/report?month=bad",
        "/api/affordability?amount=abc",
        "/api/affordability?amount=-10",
        "/api/affordability?amount=15.001",
        "/api/affordability",
    ],
)
def test_invalid_request_returns_422(client, path):
    assert client.get(path).status_code == 422


def test_upload_recalculates_report_and_purchase_atomically(client, sample_files):
    changed = sample_files | {
        "transactions.csv": sample_files["transactions.csv"].replace(
            "insurance,-1260,", "insurance,-1500,"
        )
    }
    response = client.post("/api/upload", files=multipart(changed))
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    uploaded = response.json()
    assert uploaded["is_sample"] is False
    assert uploaded["monthly_summary"]["expenses"] == 53140
    assert uploaded["monthly_summary"]["profit"] == -8070
    assert client.get("/api/report").json() == uploaded
    purchase = client.get("/api/affordability?amount=15000").json()
    assert purchase["reserve_required"] == 53140
    assert purchase["shortfall"] == 16903
    invalid = changed | {"invoices.csv": "invoice_id\n"}
    rejection = client.post("/api/upload", files=multipart(invalid))
    assert rejection.status_code == 422
    assert "invoices.csv: missing columns" in rejection.json()["detail"]
    assert client.get("/api/report").json() == uploaded


def test_browser_sessions_are_isolated_and_can_reset(app, sample_files):
    with TestClient(app) as first, TestClient(app) as second:
        changed = sample_files | {
            "transactions.csv": sample_files["transactions.csv"].replace(
                "insurance,-1260,", "insurance,-1500,"
            )
        }
        first.post("/api/upload", files=multipart(changed)).raise_for_status()
        assert first.get("/api/report").json()["monthly_summary"]["expenses"] == 53140
        assert second.get("/api/report").json()["monthly_summary"]["expenses"] == 52900
        reset = first.post("/api/reset")
        assert reset.status_code == 200 and reset.json()["is_sample"] is True
        assert COOKIE_NAME not in first.cookies
        assert first.get("/api/report").json()["monthly_summary"]["expenses"] == 52900


def test_duplicate_missing_and_unexpected_files_are_rejected(client, sample_files):
    payload = multipart(sample_files)
    for files in [
        payload[:-1],
        payload + [payload[0]],
        payload[:-1] + [("files", ("other.json", "{}", "application/json"))],
    ]:
        response = client.post("/api/upload", files=files)
        assert response.status_code == 422
        assert client.get("/api/report").json()["is_sample"] is True


def test_upload_size_limits_preserve_books(client, sample_files, monkeypatch):
    too_big = client.post(
        "/api/upload", headers={"content-length": str(4 * 10 * 1024 * 1024 + 65537)}
    )
    assert too_big.status_code == 413
    monkeypatch.setattr("backend.app.main.MAX_FILE_BYTES", 20)
    assert client.post("/api/upload", files=multipart(sample_files)).status_code == 413
    assert client.get("/api/report").json()["is_sample"] is True


def test_built_frontend_served_without_masking_api_errors(books, tmp_path):
    (tmp_path / "index.html").write_text("<html><body>Toolbelt CFO</body></html>")
    with TestClient(create_app(books, frontend_directory=tmp_path)) as client:
        assert "Toolbelt CFO" in client.get("/").text
        assert (
            client.get("/api/report")
            .headers["content-type"]
            .startswith("application/json")
        )
        assert client.get("/api/unknown").status_code == 404
