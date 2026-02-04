# backend/app/api/analytics.py

from fastapi import APIRouter, HTTPException
from app.services.gemini import genai, GEMINI_READY

router = APIRouter()

@router.get("/ai-summary")
async def ai_summary(prompt: str):
    if not GEMINI_READY or genai is None:
        raise HTTPException(status_code=503, detail="Gemini AI not available")

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    return {
        "summary": response.text,
        "model": "gemini-1.5-flash",
    }
