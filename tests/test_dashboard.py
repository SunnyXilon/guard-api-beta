from app.taxonomy import DecisionAction
from app.taxonomy import ModerationCategory
from app.models import AuditEventRecord


MARKET_HEADERS = {"X-API-Key": "rtcm_market_live_key"}
MARKET_ADMIN_HEADERS = {"X-API-Key": "rtcm_market_admin_key"}


def test_dashboard_shows_usage_recent_decisions_and_policy(client) -> None:
    client.post(
        "/moderate/text",
        headers=MARKET_HEADERS,
        json={"text": "Guaranteed profit investment, whatsapp me for deal."},
    )

    response = client.get("/dashboard", headers=MARKET_ADMIN_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant"]["tenant_id"] == "marketplace"
    assert payload["usage"]["monthly_quota"] == 1000
    assert payload["usage"]["remaining_requests"] + payload["usage"]["total_requests"] == 1000
    assert payload["usage"]["total_requests"] >= 1
    assert payload["usage"]["block"] >= 1
    assert payload["recent_decisions"]
    assert payload["recent_decisions"][0]["action"] == DecisionAction.BLOCK
    assert payload["policy"]["tenant_id"] == "marketplace"
    assert set(payload["policy"]["thresholds"]) == {category.value for category in ModerationCategory}


def test_policy_thresholds_can_be_updated(client) -> None:
    response = client.put(
        "/policies/me",
        headers=MARKET_ADMIN_HEADERS,
        json={
            "thresholds": {
                "spam_scam": {
                    "review": 0.25,
                    "block": 0.5,
                }
            },
            "review_enabled": True,
            "protected_mode": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["thresholds"]["spam_scam"]["review"] == 0.25
    assert payload["thresholds"]["spam_scam"]["block"] == 0.5
    assert payload["protected_mode"] is True

    db = client.app.state.session_factory()
    try:
        audit = (
            db.query(AuditEventRecord)
            .filter(AuditEventRecord.event_type == "policy.updated")
            .order_by(AuditEventRecord.created_at.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_type == "tenant_admin"
    finally:
        db.close()


def test_invalid_policy_thresholds_are_rejected(client) -> None:
    response = client.put(
        "/policies/me",
        headers=MARKET_ADMIN_HEADERS,
        json={
            "thresholds": {
                "spam_scam": {
                    "review": 0.9,
                    "block": 0.5,
                }
            }
        },
    )

    assert response.status_code == 422


def test_near_zero_policy_thresholds_are_rejected(client) -> None:
    response = client.put(
        "/policies/me",
        headers=MARKET_ADMIN_HEADERS,
        json={
            "thresholds": {
                "illegal_activity": {
                    "review": 0.0,
                    "block": 0.15,
                }
            }
        },
    )

    assert response.status_code == 422
