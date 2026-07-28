"""
Screen / whiteboard VLM evaluator — Phase 6.

Mount point: backend/app/services/screen_evaluator.py

Sends a user-captured screenshot (whiteboard sketch, IDE screen-share
frame, etc.) to the vision-capable model role for analysis.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from app.schemas.coding import ScreenEvaluation

logger = logging.getLogger("poise.screen_evaluator")

SCREEN_EVAL_SYSTEM_PROMPT = """You are a technical interviewer looking at a candidate's whiteboard \
sketch or shared screen during a system design / coding explanation. Assess what you see and \
respond with STRICT JSON ONLY:

{
  "description": string (what you observe, 2-4 sentences),
  "diagram_quality": float 0-100 (clarity, correct notation, legibility),
  "completeness": float 0-100 (does it address the stated context/problem),
  "feedback": [string, ...] (specific, actionable notes)
}
"""

MAX_IMAGE_BYTES = 8_000_000  # 8MB guard before we even attempt to encode/send


class ScreenEvaluator:
    """Evaluates screenshots of whiteboard/screen-share via the VLM role."""

    def __init__(self, provider):
        self.provider = provider

    async def evaluate_screenshot(self, image_path: Path, context: str) -> ScreenEvaluation:
        image_bytes = _read_and_validate(image_path)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        media_type = _guess_media_type(image_path)

        from app.services.provider import ModelRole  # noqa: PLC0415

        messages = [
            {"role": "system", "content": SCREEN_EVAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Context for this screenshot: {context or 'general whiteboard/coding round'}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                ],
            },
        ]

        response = await self.provider.chat(
            messages=messages,
            model_role=ModelRole.VISION,
            stream=False,
        )

        text = _extract_text(response)
        return self._parse(text)

    def _parse(self, text: str) -> ScreenEvaluation:
        cleaned = _strip_code_fence(text)
        try:
            data = json.loads(cleaned)
            return ScreenEvaluation.model_validate(data)
        except Exception:
            logger.exception("Failed to parse screen evaluation response, using fallback")
            return ScreenEvaluation(
                description="Automated analysis unavailable for this screenshot.",
                diagram_quality=0,
                completeness=0,
                feedback=[],
            )


def _read_and_validate(image_path: Path) -> bytes:
    if not image_path.exists():
        raise FileNotFoundError(f"Screenshot not found: {image_path}")
    size = image_path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"Screenshot too large ({size} bytes, max {MAX_IMAGE_BYTES})")
    return image_path.read_bytes()


def _guess_media_type(image_path: Path) -> str:
    ext = image_path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "image/png")


def _extract_text(response) -> str:
    if isinstance(response, str):
        return response
    try:
        return response.choices[0].message.content
    except AttributeError:
        pass
    if isinstance(response, dict):
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            pass
    return str(response)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)
        t = t[1] if len(t) > 1 else t[0]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()
