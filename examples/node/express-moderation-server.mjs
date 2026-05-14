import "dotenv/config";
import express from "express";
import multer from "multer";
import { rm } from "node:fs/promises";
import {
  GuardApiClient,
  shouldBlock,
  shouldHoldForReview,
} from "./guard-api-client.mjs";

const app = express();
const upload = multer({ dest: "tmp_uploads/" });
const guard = new GuardApiClient();

app.use(express.json());

app.post("/messages", async (req, res, next) => {
  try {
    const moderation = await guard.moderateText({
      text: req.body.text,
      metadata: {
        content_id: req.body.messageId,
        user_id: req.body.userId,
        channel: "chat",
        region: req.body.region || "global",
      },
    });

    if (shouldBlock(moderation)) {
      return res.status(422).json({
        status: "blocked",
        request_id: moderation.request_id,
        reason: moderation.decision.explanation,
      });
    }

    // Replace this with your database write.
    const savedMessage = {
      id: req.body.messageId,
      text: req.body.text,
      moderation_request_id: moderation.request_id,
      moderation_action: moderation.decision.action,
      visible: !shouldHoldForReview(moderation),
    };

    return res.status(shouldHoldForReview(moderation) ? 202 : 201).json({
      status: moderation.decision.action,
      message: savedMessage,
      review_case_id: moderation.review_case_id,
    });
  } catch (error) {
    next(error);
  }
});

app.post("/voice-notes", upload.single("audio"), async (req, res, next) => {
  try {
    const moderation = await guard.moderateAudio({
      filePath: req.file.path,
      transcriptHint: req.body.transcript_hint || "",
      metadata: {
        content_id: req.body.voiceNoteId,
        user_id: req.body.userId,
        channel: "voice_message",
      },
    });

    if (shouldBlock(moderation)) {
      return res.status(422).json({
        status: "blocked",
        request_id: moderation.request_id,
        transcript: moderation.metadata.extracted_text,
      });
    }

    return res.status(shouldHoldForReview(moderation) ? 202 : 201).json({
      status: moderation.decision.action,
      transcript: moderation.metadata.extracted_text,
      request_id: moderation.request_id,
      review_case_id: moderation.review_case_id,
    });
  } catch (error) {
    next(error);
  } finally {
    if (req.file?.path) {
      await rm(req.file.path, { force: true });
    }
  }
});

app.post("/listing-images", upload.single("image"), async (req, res, next) => {
  try {
    const moderation = await guard.moderateImage({
      filePath: req.file.path,
      imageCaption: req.body.caption || "",
      detectedObjects: (req.body.detected_objects || "").split(",").filter(Boolean),
      ocrText: req.body.ocr_text || "",
      metadata: {
        content_id: req.body.imageId,
        user_id: req.body.userId,
        channel: "listing_image",
      },
    });

    if (shouldBlock(moderation)) {
      return res.status(422).json({
        status: "blocked",
        request_id: moderation.request_id,
        reason: moderation.decision.explanation,
      });
    }

    return res.status(shouldHoldForReview(moderation) ? 202 : 201).json({
      status: moderation.decision.action,
      request_id: moderation.request_id,
      review_case_id: moderation.review_case_id,
    });
  } catch (error) {
    next(error);
  } finally {
    if (req.file?.path) {
      await rm(req.file.path, { force: true });
    }
  }
});

app.use((error, _req, res, _next) => {
  console.error(error);
  res.status(500).json({ error: "Moderation integration failed." });
});

app.listen(9000, () => {
  console.log("Example customer backend running on http://127.0.0.1:9000");
});

