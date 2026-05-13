from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import AuditEventRecord, ModerationRequestRecord, ReviewCaseRecord


def test_moderation_persists_audit_and_review_case(client) -> None:
    response = client.post(
        "/moderate/text",
        headers={"X-API-Key": "rtcm_kids_live_key"},
        json={"text": "Send nude pics right now."},
    )
    assert response.status_code == 200
    payload = response.json()

    db_url = client.app.state.settings.database_url
    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    with Session(engine) as db:
        request_row = db.query(ModerationRequestRecord).filter_by(id=payload["request_id"]).one_or_none()
        review_row = db.query(ReviewCaseRecord).filter_by(request_id=payload["request_id"]).one_or_none()
        audit_rows = db.query(AuditEventRecord).filter_by(request_id=payload["request_id"]).all()

        assert request_row is not None
        assert review_row is not None
        assert audit_rows
        assert audit_rows[0].event_type == "moderation.completed"
