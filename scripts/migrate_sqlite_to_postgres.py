from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import init_db
from app.models import (
    ApiKey,
    AuditEventRecord,
    ConnectedAccountRecord,
    ModerationRequestRecord,
    ModerationResultRecord,
    ReviewCaseRecord,
    SocialActionRecord,
    SocialEventRecord,
    Tenant,
    TenantPolicy,
)
from app.settings import Settings, get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "rtcm.db"


def row_data(row: Any, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    if overrides:
        data.update(overrides)
    return data


def exists_by_id(db: Session, model: Any, row_id: str) -> bool:
    return db.get(model, row_id) is not None


def add_row(db: Session, model: Any, row: Any, overrides: dict[str, Any] | None = None) -> bool:
    if exists_by_id(db, model, row.id):
        return False
    db.add(model(**row_data(row, overrides)))
    db.flush()
    return True


def count_rows(db: Session, models: Iterable[Any]) -> dict[str, int]:
    return {model.__tablename__: db.query(model).count() for model in models}


def migrate(source_db: Path, execute: bool) -> None:
    settings = get_settings()
    target_url = settings.database_url
    if target_url.startswith("sqlite"):
        raise SystemExit("Refusing to migrate into SQLite. Set RTCM_DATABASE_URL to PostgreSQL first.")
    if not source_db.exists():
        raise SystemExit(f"SQLite source database not found: {source_db}")

    source_engine = create_engine(f"sqlite:///{source_db}", future=True)
    target_engine = create_engine(target_url, future=True, pool_pre_ping=True)
    init_db(target_engine)

    SourceSession = sessionmaker(bind=source_engine, future=True)
    TargetSession = sessionmaker(bind=target_engine, future=True)
    models = [
        Tenant,
        ApiKey,
        TenantPolicy,
        ModerationRequestRecord,
        ModerationResultRecord,
        ReviewCaseRecord,
        ConnectedAccountRecord,
        SocialEventRecord,
        SocialActionRecord,
        AuditEventRecord,
    ]

    with SourceSession() as source, TargetSession() as target:
        before = count_rows(target, models)
        inserted = {model.__tablename__: 0 for model in models}
        tenant_id_map: dict[str, str] = {}
        request_id_map: dict[str, str] = {}
        connected_account_id_map: dict[str, str] = {}
        social_event_id_map: dict[str, str] = {}

        for tenant in source.query(Tenant).order_by(Tenant.created_at.asc()).all():
            existing = target.query(Tenant).filter(Tenant.slug == tenant.slug).one_or_none()
            if existing:
                tenant_id_map[tenant.id] = existing.id
                continue
            if add_row(target, Tenant, tenant):
                tenant_id_map[tenant.id] = tenant.id
                inserted["tenants"] += 1

        for key in source.query(ApiKey).order_by(ApiKey.created_at.asc()).all():
            tenant_id = tenant_id_map.get(key.tenant_id)
            if not tenant_id:
                continue
            if target.query(ApiKey).filter(ApiKey.key_hash == key.key_hash).one_or_none():
                continue
            if add_row(target, ApiKey, key, {"tenant_id": tenant_id}):
                inserted["api_keys"] += 1

        for policy in source.query(TenantPolicy).order_by(TenantPolicy.created_at.asc()).all():
            tenant_id = tenant_id_map.get(policy.tenant_id)
            if not tenant_id:
                continue
            if target.query(TenantPolicy).filter(TenantPolicy.tenant_id == tenant_id).one_or_none():
                continue
            if add_row(target, TenantPolicy, policy, {"tenant_id": tenant_id}):
                inserted["tenant_policies"] += 1

        for request in source.query(ModerationRequestRecord).order_by(ModerationRequestRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(request.tenant_id)
            if not tenant_id:
                continue
            if add_row(target, ModerationRequestRecord, request, {"tenant_id": tenant_id}):
                inserted["moderation_requests"] += 1
            request_id_map[request.id] = request.id

        for result in source.query(ModerationResultRecord).order_by(ModerationResultRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(result.tenant_id)
            request_id = request_id_map.get(result.request_id)
            if not tenant_id or not request_id:
                continue
            if target.query(ModerationResultRecord).filter(ModerationResultRecord.request_id == request_id).one_or_none():
                continue
            if add_row(target, ModerationResultRecord, result, {"tenant_id": tenant_id, "request_id": request_id}):
                inserted["moderation_results"] += 1

        for review_case in source.query(ReviewCaseRecord).order_by(ReviewCaseRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(review_case.tenant_id)
            request_id = request_id_map.get(review_case.request_id)
            if not tenant_id or not request_id:
                continue
            if target.query(ReviewCaseRecord).filter(ReviewCaseRecord.request_id == request_id).one_or_none():
                continue
            if add_row(target, ReviewCaseRecord, review_case, {"tenant_id": tenant_id, "request_id": request_id}):
                inserted["review_cases"] += 1

        for account in source.query(ConnectedAccountRecord).order_by(ConnectedAccountRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(account.tenant_id)
            if not tenant_id:
                continue
            if add_row(target, ConnectedAccountRecord, account, {"tenant_id": tenant_id}):
                inserted["connected_accounts"] += 1
            connected_account_id_map[account.id] = account.id

        for event in source.query(SocialEventRecord).order_by(SocialEventRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(event.tenant_id)
            connected_account_id = (
                connected_account_id_map.get(event.connected_account_id) if event.connected_account_id else None
            )
            moderation_request_id = request_id_map.get(event.moderation_request_id) if event.moderation_request_id else None
            if not tenant_id:
                continue
            if event.connected_account_id and not connected_account_id:
                continue
            if event.moderation_request_id and not moderation_request_id:
                continue
            if add_row(
                target,
                SocialEventRecord,
                event,
                {
                    "tenant_id": tenant_id,
                    "connected_account_id": connected_account_id,
                    "moderation_request_id": moderation_request_id,
                },
            ):
                inserted["social_events"] += 1
            social_event_id_map[event.id] = event.id

        for action in source.query(SocialActionRecord).order_by(SocialActionRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(action.tenant_id)
            social_event_id = social_event_id_map.get(action.social_event_id)
            if not tenant_id or not social_event_id:
                continue
            if add_row(target, SocialActionRecord, action, {"tenant_id": tenant_id, "social_event_id": social_event_id}):
                inserted["social_actions"] += 1

        for audit_event in source.query(AuditEventRecord).order_by(AuditEventRecord.created_at.asc()).all():
            tenant_id = tenant_id_map.get(audit_event.tenant_id)
            request_id = request_id_map.get(audit_event.request_id) if audit_event.request_id else None
            if not tenant_id:
                continue
            if audit_event.request_id and not request_id:
                continue
            if add_row(target, AuditEventRecord, audit_event, {"tenant_id": tenant_id, "request_id": request_id}):
                inserted["audit_events"] += 1

        after = count_rows(target, models)
        if execute:
            target.commit()
        else:
            target.rollback()

    mode = "executed" if execute else "dry-run"
    print(f"SQLite to PostgreSQL migration {mode}.")
    print(f"Source: {source_db}")
    print(f"Target: {target_url}")
    for table_name in before:
        print(f"{table_name}: before={before[table_name]} inserted={inserted[table_name]} after={after[table_name]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy missing local SQLite RTCM data into the configured PostgreSQL database.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Path to the SQLite rtcm.db file.")
    parser.add_argument("--execute", action="store_true", help="Commit the migration. Omit for a dry run.")
    args = parser.parse_args()
    migrate(args.source, execute=args.execute)


if __name__ == "__main__":
    main()
