from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app())


def test_health_contract_and_request_correlation():
    request_id = str(uuid4())
    response = client.get("/health", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] in {"demo", "live", "unconfigured"}
    assert set(body["providers"]) == {"vision", "canonicalization", "nutrition"}
    assert response.headers["X-Request-ID"] == request_id


def test_invalid_correlation_id_is_replaced_and_errors_are_consistent():
    response = client.get("/api/v1/meals", headers={"X-Request-ID": "not-a-uuid"})
    generated = response.headers["X-Request-ID"]
    assert generated != "not-a-uuid"
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Authentication is required.",
            "request_id": generated,
            "details": None,
        }
    }
