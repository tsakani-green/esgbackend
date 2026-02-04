# backend/app/api/ai_agent.py

from fastapi import APIRouter, HTTPException
from app.services.gemini_client import GEMINI_READY, genai, get_gemini_model

router = APIRouter()

@router.post("/ask")
async def ask_ai(payload: dict):
    if not GEMINI_READY or genai is None:
        raise HTTPException(status_code=503, detail="AI service unavailable (Gemini not configured)")

    prompt = (payload or {}).get("prompt") or ""
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Missing 'prompt'")

    try:
        model = get_gemini_model()
        resp = model.generate_content(prompt)
        return {"answer": (getattr(resp, "text", "") or "").strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {str(e)}")
