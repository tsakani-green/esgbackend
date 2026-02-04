from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.gemini_client import GEMINI_READY, get_gemini_model

router = APIRouter()


class AskAIRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt to send to Gemini")
    model: str | None = Field(default=None, description="Optional Gemini model override (e.g. gemini-1.5-flash)")


class AskAIResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=AskAIResponse)
async def ask_ai(payload: AskAIRequest):
    """
    Client endpoint:
      POST /api/ai/ask
      { "prompt": "...", "model": "gemini-1.5-flash" }
    """
    if not GEMINI_READY:
        raise HTTPException(status_code=503, detail="AI service unavailable (Gemini not configured)")

    try:
        model = get_gemini_model(payload.model)
        resp = model.generate_content(payload.prompt)
        text = getattr(resp, "text", None) or ""
        return {"answer": text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {str(e)}")
