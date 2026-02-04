# backend/app/api/ai_agent.py

from fastapi import APIRouter, HTTPException
from app.services.gemini import genai, GEMINI_READY

router = APIRouter()

@router.post("/ask")
async def ask_ai(payload: dict):
    if not GEMINI_READY or genai is None:
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable (Gemini not configured)",
        )

    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    return {
        "answer": response.text,
        "model": "gemini-1.5-flash",
    }
