ADMIN_HEADERS = {"X-API-Key": "rtcm_market_admin_key"}


def test_checkout_requires_stripe_configuration(client) -> None:
    response = client.post(
        "/billing/checkout",
        headers=ADMIN_HEADERS,
        json={"plan_name": "growth"},
    )

    assert response.status_code == 503


def test_billing_portal_requires_stripe_configuration(client) -> None:
    response = client.post("/billing/portal", headers=ADMIN_HEADERS)

    assert response.status_code == 503


def test_billing_webhook_updates_tenant_plan_in_development(client) -> None:
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "marketplace",
                "customer": "cus_test",
                "subscription": "sub_test",
                "metadata": {
                    "tenant_slug": "marketplace",
                    "plan_name": "growth",
                },
            }
        },
    }

    response = client.post("/billing/webhook", json=event)

    assert response.status_code == 200
    status_response = client.get("/billing/status", headers=ADMIN_HEADERS)
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["plan_name"] == "growth"
    assert payload["monthly_quota"] == 3000
    assert payload["subscription_status"] == "active"
