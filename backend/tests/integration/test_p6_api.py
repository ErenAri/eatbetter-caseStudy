from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.infrastructure.config import AppEnvironment, Settings


USER = UUID("00000000-0000-0000-0000-000000000006")


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer dev-{USER}"}


def test_portion_answer_is_idempotent_and_conflicting_replay_is_409():
    with TestClient(create_app(Settings(app_env=AppEnvironment.TEST))) as client:
        meal = client.post("/api/v1/dev/fixtures/review-meal", headers=auth()).json()["meal"]
        clarification = meal["clarifications"][0]
        url = f"/api/v1/meals/{meal['id']}/clarifications/{clarification['id']}/answer"
        first = client.post(url, headers=auth(), json={"option_id": "one-tablespoon"})
        replay = client.post(url, headers=auth(), json={"option_id": "one-tablespoon"})
        conflict = client.post(url, headers=auth(), json={"option_id": "none"})
        assert first.status_code == replay.status_code == 200
        assert len(replay.json()["meal"]["corrections"]) == 1
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "CLARIFICATION_ALREADY_ANSWERED"


def test_portion_answer_exposes_resolution_source_and_validates_stored_options():
    with TestClient(create_app(Settings(app_env=AppEnvironment.TEST))) as client:
        meal = client.post("/api/v1/dev/fixtures/review-meal", headers=auth()).json()["meal"]
        clarification = meal["clarifications"][0]
        url = f"/api/v1/meals/{meal['id']}/clarifications/{clarification['id']}/answer"
        invalid = client.post(url, headers=auth(), json={"option_id": "invented-client-option"})
        assert invalid.status_code == 422
        answered = client.post(url, headers=auth(), json={"option_id": "one-teaspoon"})
        oil = answered.json()["meal"]["items"][-1]
        assert oil["portion"]["resolution_source"] == "USER_HOUSEHOLD_UNIT"
        assert oil["review_status"] == "READY"
        clarification_body = answered.json()["meal"]["clarifications"][0]
        assert clarification_body["blocking"] is True
        assert clarification_body["resolution_satisfied"] is True


def test_canonical_ambiguity_demo_grounds_a_stored_candidate_then_requests_portion():
    with TestClient(create_app(Settings(app_env=AppEnvironment.TEST))) as client:
        meal = client.post(
            "/api/v1/dev/fixtures/canonical-review-meal", headers=auth()
        ).json()["meal"]
        clarification = meal["clarifications"][0]
        assert clarification["type"] == "CANONICAL_SELECTION"
        assert [option["label"] for option in clarification["options"]] == [
            "Cream sauce", "Cheese sauce"
        ]
        answered = client.post(
            f"/api/v1/meals/{meal['id']}/clarifications/{clarification['id']}/answer",
            headers=auth(),
            json={"option_id": "candidate-1"},
        )
        assert answered.status_code == 200
        body = answered.json()["meal"]
        assert body["items"][0]["canonical"]["name"] == "Cream sauce"
        assert any(value["type"] == "PORTION" for value in body["clarifications"])
