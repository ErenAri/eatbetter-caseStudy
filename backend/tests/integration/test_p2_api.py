from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.config import AppEnvironment, Settings
from app.main import create_app


USER_A = UUID("11111111-1111-4111-8111-111111111111")
USER_B = UUID("22222222-2222-4222-8222-222222222222")


def auth(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer dev-{user_id}"}


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None, app_env=AppEnvironment.TEST))) as value:
        yield value


def create_payload(request_id=None):
    return {
        "meal_request_id": str(request_id or uuid4()),
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "user_context": "Chicken was cooked with olive oil.",
    }


def test_create_is_idempotent_and_replay_returns_200(client):
    payload = create_payload()
    first = client.post("/api/v1/meals", headers=auth(USER_A), json=payload)
    replay = client.post("/api/v1/meals", headers=auth(USER_A), json=payload)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["meal"]["id"] == replay.json()["meal"]["id"]
    assert replay.json()["meal"]["status"] == "UPLOADED"


def test_retrieve_is_scoped_to_authenticated_owner(client):
    created = client.post("/api/v1/meals", headers=auth(USER_A), json=create_payload()).json()
    meal_id = created["meal"]["id"]
    own = client.get(f"/api/v1/meals/{meal_id}", headers=auth(USER_A))
    other = client.get(f"/api/v1/meals/{meal_id}", headers=auth(USER_B))
    assert own.status_code == 200
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "MEAL_NOT_FOUND"


def test_upload_validation_and_analysis_state_semantics(client):
    meal = client.post("/api/v1/meals", headers=auth(USER_A), json=create_payload()).json()["meal"]
    without_image = client.post(
        f"/api/v1/meals/{meal['id']}/analysis", headers=auth(USER_A)
    )
    assert without_image.status_code == 422
    spoofed = client.post(
        f"/api/v1/meals/{meal['id']}/image",
        headers=auth(USER_A),
        files={"image": ("meal.jpg", b"not-an-image", "image/jpeg")},
    )
    assert spoofed.status_code == 422
    assert spoofed.json()["error"]["code"] == "UNSUPPORTED_IMAGE"
    uploaded = client.post(
        f"/api/v1/meals/{meal['id']}/image",
        headers=auth(USER_A),
        files={"image": ("ignored-name.jpg", b"\xff\xd8\xffphoto", "image/jpeg")},
    )
    assert uploaded.status_code == 200
    first = client.post(f"/api/v1/meals/{meal['id']}/analysis", headers=auth(USER_A))
    duplicate = client.post(f"/api/v1/meals/{meal['id']}/analysis", headers=auth(USER_A))
    assert first.json()["meal"]["status"] == "NEEDS_REVIEW"
    assert len(first.json()["meal"]["items"]) == 3
    assert all(item["canonical"] is not None for item in first.json()["meal"]["items"])
    assert all(len(item["candidates"]) >= 1 for item in first.json()["meal"]["items"])
    assert all(item["nutrition"] is None for item in first.json()["meal"]["items"])
    assert duplicate.json()["meal"] == first.json()["meal"]
    assert client.app.state.vision_provider.call_count == 1
    stored = client.app.state.meal_repository._meals[UUID(meal["id"])]
    assert len(stored.ai_runs) == 4
    assert stored.ai_runs[0].status == "SUCCEEDED"
    assert stored.ai_runs[0].request_id is not None
    assert all(item.nutrition_snapshot is not None for item in stored.items)
    assert all(item.confirmed_portion_g is None for item in stored.items)
    assert all(item.final_nutrition is None for item in stored.items)
    assert all(item.canonical_confidence is None for item in stored.items)


def test_correction_preserves_prediction_and_recalculates(client):
    fixture = client.post("/api/v1/dev/fixtures/review-meal", headers=auth(USER_A)).json()["meal"]
    chicken = fixture["items"][0]
    corrected = client.patch(
        f"/api/v1/meals/{fixture['id']}/items/{chicken['id']}",
        headers=auth(USER_A),
        json={"portion_g": 100, "preparation_method": "roasted"},
    )
    assert corrected.status_code == 200
    body = corrected.json()["meal"]
    item = body["items"][0]
    assert item["observed_name"] == "chicken breast"
    assert item["preparation_method"] == "roasted"
    assert item["nutrition"]["calories_kcal"] == 165
    correction_fields = {value["field_name"] for value in body["corrections"]}
    assert {"portion_g", "preparation_method"}.issubset(correction_fields)


def test_unresolved_clarification_blocks_then_answer_allows_confirmation(client):
    fixture = client.post("/api/v1/dev/fixtures/review-meal", headers=auth(USER_A)).json()["meal"]
    blocked = client.post(f"/api/v1/meals/{fixture['id']}/confirm", headers=auth(USER_A))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "UNRESOLVED_CLARIFICATIONS"
    clarification = fixture["clarifications"][0]
    answered = client.post(
        f"/api/v1/meals/{fixture['id']}/clarifications/{clarification['id']}/answer",
        headers=auth(USER_A),
        json={"option_id": "one-tablespoon"},
    )
    assert answered.status_code == 200
    confirmed = client.post(f"/api/v1/meals/{fixture['id']}/confirm", headers=auth(USER_A))
    assert confirmed.status_code == 200
    meal = confirmed.json()["meal"]
    assert meal["status"] == "CONFIRMED"
    assert meal["totals"]["calories_kcal"] == 624.09


def test_invalid_candidate_rank_and_invalid_state_return_stable_errors(client):
    fixture = client.post("/api/v1/dev/fixtures/review-meal", headers=auth(USER_A)).json()["meal"]
    item = fixture["items"][0]
    invalid = client.patch(
        f"/api/v1/meals/{fixture['id']}/items/{item['id']}",
        headers=auth(USER_A),
        json={"candidate_rank": 99},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "CANONICAL_FOOD_NOT_FOUND"


def test_logical_item_removal_preserves_evidence_and_delete_removes_aggregate(client):
    fixture = client.post("/api/v1/dev/fixtures/review-meal", headers=auth(USER_A)).json()["meal"]
    broccoli = fixture["items"][2]
    removed = client.delete(
        f"/api/v1/meals/{fixture['id']}/items/{broccoli['id']}", headers=auth(USER_A)
    ).json()["meal"]
    item = next(value for value in removed["items"] if value["id"] == broccoli["id"])
    assert item["is_removed"] is True
    assert any(value["field_name"] == "removed_item" for value in removed["corrections"])
    deleted = client.delete(f"/api/v1/meals/{fixture['id']}", headers=auth(USER_A))
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/meals/{fixture['id']}", headers=auth(USER_A)).status_code == 404


def test_openapi_contains_authoritative_versioned_contract(client):
    schema = client.get("/openapi.json").json()
    expected = {
        "/api/v1/meals",
        "/api/v1/meals/{meal_id}",
        "/api/v1/meals/{meal_id}/image",
        "/api/v1/meals/{meal_id}/analysis",
        "/api/v1/meals/{meal_id}/confirm",
        "/api/v1/daily-summary",
    }
    assert expected.issubset(schema["paths"])


def test_daily_summary_accepts_mobile_iana_timezone_on_windows(client):
    response = client.get(
        "/api/v1/daily-summary",
        headers=auth(USER_A),
        params={"date": "2026-08-18", "timezone": "Europe/Istanbul"},
    )

    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Istanbul"
