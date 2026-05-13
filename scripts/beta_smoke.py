from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx


API_BASE = os.getenv("BETA_SMOKE_API_BASE", "http://127.0.0.1:8100").rstrip("/")
CLERK_USER_ID = os.getenv("BETA_SMOKE_CLERK_USER_ID", "beta_smoke_user")
WORKSPACE_NAME = os.getenv("BETA_SMOKE_WORKSPACE_NAME", "Beta Smoke Workspace")
RISKY_TEXT = os.getenv("BETA_SMOKE_TEXT", "Send nude pics right now.")


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
    response = client.request(method, f"{API_BASE}{path}", timeout=20, **kwargs)
    if response.status_code >= 400:
        fail(f"{method} {path} returned {response.status_code}: {response.text}")
    return response


def main() -> None:
    print(f"Running beta smoke flow against {API_BASE}")
    clerk_headers = {"X-Clerk-User-Id": CLERK_USER_ID}

    with httpx.Client() as client:
        health = request(client, "GET", "/health").json()
        print(f"health: {health}")

        workspaces = request(client, "GET", "/workspaces/clerk", headers=clerk_headers).json()
        if workspaces:
            workspace = workspaces[0]
            print(f"workspace: reopened {workspace['tenant_id']}")
        else:
            onboarding = request(
                client,
                "POST",
                "/onboarding/tenant",
                headers=clerk_headers,
                json={"workspace_name": WORKSPACE_NAME},
            ).json()
            workspace = {
                "tenant_id": onboarding["dashboard_session"]["tenant"]["tenant_id"],
                "tenant_name": onboarding["dashboard_session"]["tenant"]["tenant_name"],
            }
            print(f"workspace: created {workspace['tenant_id']}")

        session = request(
            client,
            "POST",
            f"/dashboard/session/clerk?tenant_id={workspace['tenant_id']}",
            headers=clerk_headers,
        ).json()
        dashboard_token = session["access_token"]
        dashboard_headers = {"Authorization": f"Bearer {dashboard_token}"}

        dashboard = request(client, "GET", "/dashboard", headers=dashboard_headers).json()
        if dashboard["tenant"]["tenant_id"] != workspace["tenant_id"]:
            fail("dashboard opened the wrong workspace")
        print(f"dashboard: {dashboard['tenant']['tenant_name']} quota={dashboard['usage']['monthly_quota']}")

        playground = request(
            client,
            "POST",
            "/playground/moderate/text",
            headers=dashboard_headers,
            json={
                "text": RISKY_TEXT,
                "metadata": {
                    "channel": "beta_playground",
                    "source": "scripts/beta_smoke.py",
                },
            },
        ).json()
        if playground["decision"]["action"] not in {"review", "block"}:
            fail(f"expected playground review/block decision, got {playground['decision']['action']}")
        print(f"playground: {playground['decision']['action']} request_id={playground['request_id']}")

        key_name = f"beta-smoke-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        key_payload = request(
            client,
            "POST",
            "/api-keys",
            headers=dashboard_headers,
            json={"name": key_name, "scopes": ["moderation"]},
        ).json()
        moderation_key = key_payload["api_key"]
        moderation_headers = {"X-API-Key": moderation_key}
        print(f"api-key: created {key_payload['key_prefix']}...")

        moderation = request(
            client,
            "POST",
            "/moderate/text",
            headers=moderation_headers,
            json={
                "text": RISKY_TEXT,
                "metadata": {
                    "channel": "beta_smoke",
                    "source": "scripts/beta_smoke.py",
                },
            },
        ).json()
        action = moderation["decision"]["action"]
        if action not in {"review", "block"}:
            fail(f"expected review/block decision for risky text, got {action}")
        print(f"moderation: {action} request_id={moderation['request_id']}")

        updated_dashboard = request(client, "GET", "/dashboard", headers=dashboard_headers).json()
        recent_ids = {item["request_id"] for item in updated_dashboard["recent_decisions"]}
        if moderation["request_id"] not in recent_ids:
            fail("moderation request did not appear in recent dashboard decisions")
        print("dashboard: recent decision verified")

        cases = request(client, "GET", "/cases", headers=dashboard_headers).json()["cases"]
        review_case = next((case for case in cases if case["request_id"] == moderation["request_id"]), None)
        if not review_case:
            fail("review case was not created for risky content")

        started_case = request(
            client,
            "PATCH",
            f"/cases/{review_case['case_id']}",
            headers=dashboard_headers,
            json={"status": "in_review", "assignee": "beta-reviewer"},
        ).json()
        if started_case["status"] != "in_review":
            fail("review case did not move to in_review")

        resolved_case = request(
            client,
            "PATCH",
            f"/cases/{review_case['case_id']}",
            headers=dashboard_headers,
            json={"status": "resolved", "note": "Beta smoke review completed."},
        ).json()
        if resolved_case["status"] != "resolved":
            fail("review case did not resolve")
        print(f"review: resolved case {review_case['case_id']}")

        social_event = request(
            client,
            "POST",
            "/connectors/webhook/events",
            headers={**dashboard_headers, "Content-Type": "application/json"},
            json={
                "platform": "webhook",
                "source_type": "form",
                "actor_handle": "beta-user",
                "external_event_id": key_name,
                "content_text": RISKY_TEXT,
                "raw_payload": {"source": "beta_smoke"},
            },
        ).json()
        inbox = request(client, "GET", "/social-inbox", headers=dashboard_headers).json()
        if not any(event["id"] == social_event["id"] for event in inbox):
            fail("social event did not appear in social inbox")
        social_action = request(
            client,
            "POST",
            f"/social-actions/{social_event['id']}/mark-reviewed",
            headers=dashboard_headers,
            json={},
        ).json()
        if social_action["status"] not in {"completed", "recorded"}:
            fail(f"social action did not complete or record: {social_action['status']}")
        updated_inbox = request(client, "GET", "/social-inbox", headers=dashboard_headers).json()
        reviewed_event = next((event for event in updated_inbox if event["id"] == social_event["id"]), None)
        if not reviewed_event or reviewed_event["status"] != "reviewed":
            fail("social event did not move to reviewed")
        print(f"social: reviewed event {social_event['id']}")

        print("PASS: beta smoke flow completed end to end")


if __name__ == "__main__":
    main()
