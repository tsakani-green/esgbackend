from fastapi import APIRouter, HTTPException
from app.services.gemini_client import genai, GEMINI_READY

router = APIRouter()

@router.post("/ask")
async def ask_ai(payload: dict):
    if not GEMINI_READY or genai is None:
        raise HTTPException(status_code=503, detail="AI service unavailable (Gemini not configured)")

    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(payload.get("prompt", ""))
    return {"answer": resp.text}
