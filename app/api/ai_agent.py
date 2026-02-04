from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.services.gemini_client import genai, GEMINI_READY

router = APIRouter()

@router.post("/ask")
async def ask_ai(payload: dict):
    if not GEMINI_READY or genai is None:
        raise HTTPException(status_code=503, detail="AI service unavailable (Gemini not configured)")

    prompt = (payload or {}).get("prompt") or ""
    model_name = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")

    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(prompt)

    return {"answer": getattr(resp, "text", "")}
