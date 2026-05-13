from __future__ import annotations


def test_dashboard_playground_moderates_without_raw_moderation_key(client) -> None:
    create_response = client.post(
        "/onboarding/tenant",
        headers={"X-Clerk-User-Id": "user_playground"},
        json={"workspace_name": "Playground Workspace"},
    )
    assert create_response.status_code == 200
    dashboard_token = create_response.json()["dashboard_session"]["access_token"]

    response = client.post(
        "/playground/moderate/text",
        headers={"Authorization": f"Bearer {dashboard_token}"},
        json={
            "text": "Send nude pics right now.",
            "metadata": {"channel": "dashboard_playground"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["action"] in {"review", "block"}
    assert payload["request_id"]

    cases_response = client.get("/cases", headers={"Authorization": f"Bearer {dashboard_token}"})
    assert cases_response.status_code == 200
    cases = cases_response.json()["cases"]
    assert any(review_case["request_id"] == payload["request_id"] for review_case in cases)


def test_dashboard_inference_status_requires_dashboard_session(client) -> None:
    create_response = client.post(
        "/onboarding/tenant",
        headers={"X-Clerk-User-Id": "user_inference_status"},
        json={"workspace_name": "Inference Workspace"},
    )
    assert create_response.status_code == 200
    dashboard_token = create_response.json()["dashboard_session"]["access_token"]

    response = client.get("/dashboard/inference-status", headers={"Authorization": f"Bearer {dashboard_token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "online"
    assert "model_loaded" in payload
    assert payload["model"]
