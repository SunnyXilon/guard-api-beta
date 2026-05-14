from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from guard_api_client import GuardApiClient, should_block, should_hold_for_review

app = FastAPI()
guard = GuardApiClient()


@app.post("/messages")
def create_message(payload: dict):
    moderation = guard.moderate_text(
        payload["text"],
        metadata={
            "content_id": payload.get("message_id"),
            "user_id": payload.get("user_id"),
            "channel": "chat",
            "region": payload.get("region", "global"),
        },
    )

    if should_block(moderation):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "blocked",
                "request_id": moderation["request_id"],
                "reason": moderation["decision"]["explanation"],
            },
        )

    # Replace this with your database write.
    saved_message = {
        "id": payload.get("message_id"),
        "text": payload["text"],
        "moderation_request_id": moderation["request_id"],
        "moderation_action": moderation["decision"]["action"],
        "visible": not should_hold_for_review(moderation),
    }

    return JSONResponse(
        status_code=202 if should_hold_for_review(moderation) else 201,
        content={
            "status": moderation["decision"]["action"],
            "message": saved_message,
            "review_case_id": moderation.get("review_case_id"),
        },
    )


@app.post("/voice-notes")
async def create_voice_note(
    audio: UploadFile = File(...),
    voice_note_id: str = Form(""),
    user_id: str = Form(""),
    transcript_hint: str = Form(""),
):
    temp_path = await _save_upload(audio)
    try:
        moderation = guard.moderate_audio(
            temp_path,
            transcript_hint=transcript_hint,
            metadata={
                "content_id": voice_note_id,
                "user_id": user_id,
                "channel": "voice_message",
            },
        )
    finally:
        temp_path.unlink(missing_ok=True)

    if should_block(moderation):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "blocked",
                "request_id": moderation["request_id"],
                "transcript": moderation["metadata"].get("extracted_text"),
            },
        )

    return JSONResponse(
        status_code=202 if should_hold_for_review(moderation) else 201,
        content={
            "status": moderation["decision"]["action"],
            "request_id": moderation["request_id"],
            "transcript": moderation["metadata"].get("extracted_text"),
            "review_case_id": moderation.get("review_case_id"),
        },
    )


@app.post("/listing-images")
async def create_listing_image(
    image: UploadFile = File(...),
    image_id: str = Form(""),
    user_id: str = Form(""),
    caption: str = Form(""),
    detected_objects: str = Form(""),
    ocr_text: str = Form(""),
):
    temp_path = await _save_upload(image)
    try:
        moderation = guard.moderate_image(
            temp_path,
            image_caption=caption,
            detected_objects=[item.strip() for item in detected_objects.split(",") if item.strip()],
            ocr_text=ocr_text,
            metadata={
                "content_id": image_id,
                "user_id": user_id,
                "channel": "listing_image",
            },
        )
    finally:
        temp_path.unlink(missing_ok=True)

    if should_block(moderation):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "blocked",
                "request_id": moderation["request_id"],
                "reason": moderation["decision"]["explanation"],
            },
        )

    return JSONResponse(
        status_code=202 if should_hold_for_review(moderation) else 201,
        content={
            "status": moderation["decision"]["action"],
            "request_id": moderation["request_id"],
            "review_case_id": moderation.get("review_case_id"),
        },
    )


async def _save_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(await upload.read())
        return Path(handle.name)
