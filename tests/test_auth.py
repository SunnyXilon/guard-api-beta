from app.models import Tenant


def test_missing_api_key_is_rejected(client) -> None:
    response = client.post("/moderate/text", json={"text": "Hello"})
    assert response.status_code == 401


def test_invalid_api_key_is_rejected(client) -> None:
    response = client.post(
        "/moderate/text",
        headers={"X-API-Key": "invalid-key"},
        json={"text": "Hello"},
    )
    assert response.status_code == 401


def test_policy_endpoint_is_tenant_scoped(client) -> None:
    response = client.get("/policies/me", headers={"X-API-Key": "rtcm_market_admin_key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "marketplace"
    assert "ugc-marketplace" in payload["labels"]


def test_moderation_key_cannot_access_dashboard(client) -> None:
    response = client.get("/dashboard", headers={"X-API-Key": "rtcm_market_live_key"})
    assert response.status_code == 403
    assert "moderation API key" in response.json()["detail"]


def test_admin_key_cannot_submit_moderation(client) -> None:
    response = client.post(
        "/moderate/text",
        headers={"X-API-Key": "rtcm_market_admin_key"},
        json={"text": "Hello"},
    )
    assert response.status_code == 403


def test_dashboard_session_token_can_access_dashboard(client) -> None:
    session_response = client.post("/dashboard/session", headers={"X-API-Key": "rtcm_market_admin_key"})
    assert session_response.status_code == 200
    token = session_response.json()["access_token"]

    response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["tenant"]["tenant_id"] == "marketplace"


def test_self_service_onboarding_creates_tenant_session_and_moderation_key(client) -> None:
    onboarding_response = client.post(
        "/onboarding/tenant",
        headers={"X-Clerk-User-Id": "user_acme"},
        json={"workspace_name": "Acme Trust"},
    )

    assert onboarding_response.status_code == 200
    payload = onboarding_response.json()
    assert payload["dashboard_session"]["tenant"]["tenant_id"] == "acme-trust"
    assert payload["moderation_key"]["api_key"].startswith("rtcm_")

    token = payload["dashboard_session"]["access_token"]
    dashboard_response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["tenant"]["tenant_id"] == "acme-trust"

    moderation_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": payload["moderation_key"]["api_key"]},
        json={"text": "I liked this discussion."},
    )
    assert moderation_response.status_code == 200
    assert moderation_response.json()["tenant_id"] == "acme-trust"


def test_clerk_session_reopens_existing_workspace(client) -> None:
    client.post(
        "/onboarding/tenant",
        headers={"X-Clerk-User-Id": "user_reopen"},
        json={"workspace_name": "Reopen Trust"},
    )

    session_response = client.post("/dashboard/session/clerk", headers={"X-Clerk-User-Id": "user_reopen"})

    assert session_response.status_code == 200
    token = session_response.json()["access_token"]
    dashboard_response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["tenant"]["tenant_id"] == "reopen-trust"


def test_clerk_session_returns_404_when_no_workspace_exists(client) -> None:
    response = client.post("/dashboard/session/clerk", headers={"X-Clerk-User-Id": "user_missing"})

    assert response.status_code == 404


def test_clerk_user_can_create_and_switch_multiple_workspaces(client) -> None:
    headers = {"X-Clerk-User-Id": "user_multi"}
    first_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "First Workspace"})
    assert first_response.status_code == 200

    second_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Second Workspace"})
    assert second_response.status_code == 200
    assert second_response.json()["dashboard_session"]["tenant"]["tenant_id"] == "second-workspace"

    workspaces_response = client.get("/workspaces/clerk", headers=headers)
    assert workspaces_response.status_code == 200
    workspace_ids = [workspace["tenant_id"] for workspace in workspaces_response.json()]
    assert workspace_ids == ["first-workspace", "second-workspace"]

    session_response = client.post("/dashboard/session/clerk?tenant_id=first-workspace", headers=headers)
    assert session_response.status_code == 200
    token = session_response.json()["access_token"]
    dashboard_response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["tenant"]["tenant_id"] == "first-workspace"


def test_clerk_user_can_rename_owned_workspace(client) -> None:
    headers = {"X-Clerk-User-Id": "user_rename"}
    create_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Original Name"})
    assert create_response.status_code == 200

    rename_response = client.patch(
        "/workspaces/clerk/original-name",
        headers=headers,
        json={"workspace_name": "Renamed Workspace"},
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["tenant_name"] == "Renamed Workspace"

    session_response = client.post("/dashboard/session/clerk?tenant_id=original-name", headers=headers)
    assert session_response.status_code == 200
    assert session_response.json()["tenant"]["tenant_name"] == "Renamed Workspace"


def test_clerk_workspace_quota_is_shared_across_account(client) -> None:
    headers = {"X-Clerk-User-Id": "user_shared_quota"}
    first_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Quota One"})
    second_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Quota Two"})
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    db = client.app.state.session_factory()
    try:
        tenants = db.query(Tenant).filter(Tenant.clerk_user_id == "user_shared_quota").all()
        for tenant in tenants:
            tenant.monthly_quota = 1
            db.add(tenant)
        db.commit()
    finally:
        db.close()

    first_key = first_response.json()["moderation_key"]["api_key"]
    second_key = second_response.json()["moderation_key"]["api_key"]
    first_moderation = client.post(
        "/moderate/text",
        headers={"X-API-Key": first_key},
        json={"text": "I liked this discussion."},
    )
    assert first_moderation.status_code == 200

    second_moderation = client.post(
        "/moderate/text",
        headers={"X-API-Key": second_key},
        json={"text": "This should hit the shared account quota."},
    )
    assert second_moderation.status_code == 402

    session_response = client.post("/dashboard/session/clerk?tenant_id=quota-two", headers=headers)
    token = session_response.json()["access_token"]
    dashboard_response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["usage"]["total_requests"] == 1
    assert dashboard_response.json()["usage"]["remaining_requests"] == 0


def test_workspace_billing_scope_uses_separate_quota(client) -> None:
    headers = {"X-Clerk-User-Id": "user_workspace_scope"}
    first_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Shared Scope"})
    second_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Separate Scope"})
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    second_token = second_response.json()["dashboard_session"]["access_token"]
    scope_response = client.patch(
        "/billing/scope",
        headers={"Authorization": f"Bearer {second_token}"},
        json={"billing_scope": "workspace"},
    )
    assert scope_response.status_code == 200
    assert scope_response.json()["billing_scope"] == "workspace"

    db = client.app.state.session_factory()
    try:
        tenants = db.query(Tenant).filter(Tenant.clerk_user_id == "user_workspace_scope").all()
        for tenant in tenants:
            tenant.monthly_quota = 1
            db.add(tenant)
        db.commit()
    finally:
        db.close()

    first_key = first_response.json()["moderation_key"]["api_key"]
    second_key = second_response.json()["moderation_key"]["api_key"]
    assert client.post(
        "/moderate/text",
        headers={"X-API-Key": first_key},
        json={"text": "First workspace request."},
    ).status_code == 200
    assert client.post(
        "/moderate/text",
        headers={"X-API-Key": second_key},
        json={"text": "Separate workspace request."},
    ).status_code == 200
    assert client.post(
        "/moderate/text",
        headers={"X-API-Key": first_key},
        json={"text": "Shared account quota should now be exhausted."},
    ).status_code == 402


def test_clerk_user_can_delete_workspace_without_multiplying_quota(client) -> None:
    headers = {"X-Clerk-User-Id": "user_delete_workspace"}
    first_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Delete One"})
    second_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Delete Two"})
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    db = client.app.state.session_factory()
    try:
        first = db.query(Tenant).filter(Tenant.slug == "delete-one").one()
        second = db.query(Tenant).filter(Tenant.slug == "delete-two").one()
        first.monthly_quota = 3000
        first.plan_name = "growth"
        second.monthly_quota = 1000
        second.plan_name = "starter"
        db.add(first)
        db.add(second)
        db.commit()
    finally:
        db.close()

    delete_response = client.delete("/workspaces/clerk/delete-one", headers=headers)
    assert delete_response.status_code == 200

    workspaces_response = client.get("/workspaces/clerk", headers=headers)
    assert workspaces_response.status_code == 200
    assert [workspace["tenant_id"] for workspace in workspaces_response.json()] == ["delete-two"]
    assert workspaces_response.json()[0]["monthly_quota"] == 3000
    assert workspaces_response.json()[0]["plan_name"] == "growth"

    old_key = first_response.json()["moderation_key"]["api_key"]
    old_workspace_response = client.post(
        "/moderate/text",
        headers={"X-API-Key": old_key},
        json={"text": "This old workspace should no longer accept traffic."},
    )
    assert old_workspace_response.status_code == 401

    session_response = client.post("/dashboard/session/clerk?tenant_id=delete-one", headers=headers)
    assert session_response.status_code == 404


def test_clerk_user_cannot_delete_last_workspace(client) -> None:
    headers = {"X-Clerk-User-Id": "user_delete_last_workspace"}
    create_response = client.post("/onboarding/tenant", headers=headers, json={"workspace_name": "Only Workspace"})
    assert create_response.status_code == 200

    delete_response = client.delete("/workspaces/clerk/only-workspace", headers=headers)
    assert delete_response.status_code == 409


def test_moderation_key_cannot_create_dashboard_session(client) -> None:
    response = client.post("/dashboard/session", headers={"X-API-Key": "rtcm_market_live_key"})
    assert response.status_code == 403
