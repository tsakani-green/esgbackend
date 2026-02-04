# backend/app/api/ai_agent.py

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.gemini_client import genai, GEMINI_READY

logger = logging.getLogger(__name__)

router = APIRouter()


class AskPayload(BaseModel):
    prompt: str = Field(..., min_length=1)
    # optional extras if you want later
    context: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = Field(default=0.4, ge=0.0, le=1.0)
    max_output_tokens: Optional[int] = Field(default=1024, ge=64, le=8192)


@router.post("/ask")
async def ask_ai(payload: AskPayload):
    """
    POST /api/ai/ask   (because main.py includes prefix="/api/ai")
    Body: { "prompt": "...", ... }
    Response: { "answer": "..." }
    """
    if not GEMINI_READY or genai is None:
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable (Gemini not configured)",
        )

    try:
        model_name = getattr(settings, "GEMINI_MODEL", None) or "gemini-1.5-flash"
        model = genai.GenerativeModel(model_name)

        # Build prompt with optional context (safe/simple)
        final_prompt = payload.prompt.strip()
        if payload.context:
            final_prompt = (
                "You are an ESG analytics assistant.\n\n"
                f"CONTEXT:\n{payload.context}\n\n"
                f"USER PROMPT:\n{payload.prompt.strip()}\n"
            )

        generation_config = {
            "temperature": payload.temperature if payload.temperature is not None else 0.4,
            "max_output_tokens": payload.max_output_tokens if payload.max_output_tokens is not None else 1024,
        }

        resp = model.generate_content(final_prompt, generation_config=generation_config)

        # Defensive extraction
        answer = getattr(resp, "text", None)
        if not answer:
            answer = str(resp) if resp is not None else ""

        return {"answer": answer}

    except Exception as e:
        logger.exception(f"Gemini AI failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI request failed: {str(e)}")
