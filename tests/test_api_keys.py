ADMIN_HEADERS = {"X-API-Key": "rtcm_market_admin_key"}
MODERATION_HEADERS = {"X-API-Key": "rtcm_market_live_key"}


def test_admin_can_create_scoped_moderation_key(client) -> None:
    response = client.post(
        "/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "production-webhook", "scopes": ["moderation"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"].startswith("rtcm_")
    assert payload["scopes"] == ["moderation"]

    moderation_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": payload["api_key"]},
        json={"text": "Guaranteed profit investment, whatsapp me for deal."},
    )
    assert moderation_response.status_code == 200


def test_admin_can_deactivate_api_key(client) -> None:
    create_response = client.post(
        "/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "rotated-webhook", "scopes": ["moderation"]},
    )
    assert create_response.status_code == 200
    payload = create_response.json()

    delete_response = client.delete(f"/api-keys/{payload['id']}", headers=ADMIN_HEADERS)
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False

    moderation_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": payload["api_key"]},
        json={"text": "Guaranteed profit investment, whatsapp me for deal."},
    )
    assert moderation_response.status_code == 401


def test_admin_can_rotate_api_key(client) -> None:
    create_response = client.post(
        "/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "rotated-webhook", "scopes": ["moderation"]},
    )
    assert create_response.status_code == 200
    old_key = create_response.json()

    rotate_response = client.post(f"/api-keys/{old_key['id']}/rotate", headers=ADMIN_HEADERS)
    assert rotate_response.status_code == 200
    new_key = rotate_response.json()
    assert new_key["api_key"].startswith("rtcm_")
    assert new_key["api_key"] != old_key["api_key"]
    assert new_key["name"] == old_key["name"]
    assert new_key["scopes"] == ["moderation"]

    old_key_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": old_key["api_key"]},
        json={"text": "I liked this discussion."},
    )
    assert old_key_response.status_code == 401

    new_key_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": new_key["api_key"]},
        json={"text": "I liked this discussion."},
    )
    assert new_key_response.status_code == 200


def test_admin_cannot_deactivate_current_key(client) -> None:
    session_response = client.post("/dashboard/session", headers=ADMIN_HEADERS)
    assert session_response.status_code == 200
    api_key_id = session_response.json()["tenant"]["api_key_id"]

    response = client.delete(f"/api-keys/{api_key_id}", headers=ADMIN_HEADERS)
    assert response.status_code == 400


def test_admin_cannot_rotate_current_key(client) -> None:
    session_response = client.post("/dashboard/session", headers=ADMIN_HEADERS)
    assert session_response.status_code == 200
    api_key_id = session_response.json()["tenant"]["api_key_id"]

    response = client.post(f"/api-keys/{api_key_id}/rotate", headers=ADMIN_HEADERS)
    assert response.status_code == 400


def test_moderation_key_cannot_create_api_keys(client) -> None:
    response = client.post(
        "/api-keys",
        headers=MODERATION_HEADERS,
        json={"name": "bad", "scopes": ["moderation"]},
    )

    assert response.status_code == 403


def test_active_api_key_count_is_limited(client) -> None:
    client.app.state.settings.max_active_api_keys_per_workspace = 2

    response = client.post(
        "/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "one-too-many", "scopes": ["moderation"]},
    )

    assert response.status_code == 409
    assert "Deactivate an old key" in response.json()["detail"]


def test_policy_write_scope_requires_dashboard_scope(client) -> None:
    response = client.post(
        "/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "invalid", "scopes": ["policy:write"]},
    )

    assert response.status_code == 422


def test_api_key_usage_counts_moderation_requests(client) -> None:
    create_response = client.post(
        "/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "usage-webhook", "scopes": ["moderation"]},
    )
    assert create_response.status_code == 200
    key = create_response.json()

    moderation_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": key["api_key"]},
        json={"text": "I liked this discussion."},
    )
    assert moderation_response.status_code == 200

    usage_response = client.get("/api-keys/usage", headers=ADMIN_HEADERS)
    assert usage_response.status_code == 200
    usage_by_id = {entry["id"]: entry["total_requests"] for entry in usage_response.json()}
    assert usage_by_id[key["id"]] == 1
