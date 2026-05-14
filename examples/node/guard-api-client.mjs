import { readFile } from "node:fs/promises";
import path from "node:path";

const DEFAULT_TIMEOUT_MS = 30_000;

const MIME_BY_EXTENSION = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
  ".mp3": "audio/mpeg",
  ".m4a": "audio/mp4",
  ".mp4": "video/mp4",
  ".wav": "audio/wav",
  ".webm": "audio/webm",
  ".mov": "video/quicktime",
};

export class GuardApiClient {
  constructor({
    baseUrl = process.env.GUARD_API_URL,
    apiKey = process.env.GUARD_API_KEY,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = {}) {
    if (!baseUrl) {
      throw new Error("GUARD_API_URL is required.");
    }
    if (!apiKey) {
      throw new Error("GUARD_API_KEY is required.");
    }
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.timeoutMs = timeoutMs;
  }

  async moderateText({ text, metadata = {} }) {
    return this.#postJson("/moderate/text", { text, metadata });
  }

  async moderateImage({ filePath, imageCaption = "", detectedObjects = [], ocrText = "", metadata = {} }) {
    const form = await this.#fileForm("image", filePath);
    form.set("image_caption", imageCaption);
    form.set("detected_objects", detectedObjects.join(","));
    form.set("ocr_text", ocrText);
    this.#appendMetadata(form, metadata);
    return this.#postForm("/moderate/image", form);
  }

  async moderateAudio({ filePath, transcriptHint = "", metadata = {} }) {
    const form = await this.#fileForm("audio", filePath);
    form.set("transcript_hint", transcriptHint);
    this.#appendMetadata(form, metadata);
    return this.#postForm("/moderate/audio", form);
  }

  async moderateVideo({ filePath, transcriptHint = "", frames = [], metadata = {} }) {
    const form = await this.#fileForm("video", filePath);
    form.set("transcript_hint", transcriptHint);
    form.set("frames", JSON.stringify(frames));
    this.#appendMetadata(form, metadata);
    return this.#postForm("/moderate/video", form);
  }

  async #postJson(route, body) {
    return this.#request(route, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
      },
      body: JSON.stringify(body),
    });
  }

  async #postForm(route, form) {
    return this.#request(route, {
      method: "POST",
      headers: {
        "X-API-Key": this.apiKey,
      },
      body: form,
    });
  }

  async #request(route, init) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${route}`, {
        ...init,
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `Guard API returned ${response.status}`);
      }
      return payload;
    } finally {
      clearTimeout(timeout);
    }
  }

  async #fileForm(fieldName, filePath) {
    const absolutePath = path.resolve(filePath);
    const fileName = path.basename(absolutePath);
    const mimeType = MIME_BY_EXTENSION[path.extname(fileName).toLowerCase()] || "application/octet-stream";
    const bytes = await readFile(absolutePath);
    const blob = new Blob([bytes], { type: mimeType });
    const form = new FormData();
    form.set(fieldName, blob, fileName);
    return form;
  }

  #appendMetadata(form, metadata) {
    for (const [key, value] of Object.entries(metadata)) {
      if (value !== undefined && value !== null) {
        form.set(key, String(value));
      }
    }
  }
}

export function actionForDecision(moderation) {
  return moderation?.decision?.action || "review";
}

export function shouldPublish(moderation) {
  return actionForDecision(moderation) === "allow";
}

export function shouldHoldForReview(moderation) {
  return actionForDecision(moderation) === "review";
}

export function shouldBlock(moderation) {
  return actionForDecision(moderation) === "block";
}

