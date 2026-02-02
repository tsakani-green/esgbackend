# backend/app/api/gemini_ai.py
# Gemini AI API Endpoints for ESG Analysis (uses gemini_esg_service from services/gemini_esg.py)

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
import logging
from pydantic import BaseModel

from app.services.gemini_esg import gemini_esg_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gemini", tags=["Gemini AI"])


class ESGPredictionRequest(BaseModel):
    clientId: str
    timeHorizon: str = "12months"
    companyData: Optional[Dict] = None


class RiskAssessmentRequest(BaseModel):
    portfolioId: str
    portfolioData: Optional[Dict] = None


class CarbonForecastRequest(BaseModel):
    clientId: str
    historicalData: Optional[Dict] = None


class RecommendationsRequest(BaseModel):
    clientId: str
    companyProfile: Optional[Dict] = None


class AIReportRequest(BaseModel):
    clientId: str
    reportType: str = "comprehensive"
    companyData: Optional[Dict] = None


class ChatRequest(BaseModel):
    question: str
    context: str = ""


@router.post("/energy-trends")
async def energy_trends(payload: Dict):
    """
    Expected payload:
      { "energy_data": [ { "energy": 123, ... }, ... ], "live_data": {...optional...} }
    """
    try:
        energy_data = payload.get("energy_data") or []
        live_data = payload.get("live_data")
        result = await gemini_esg_service.analyze_energy_trends(energy_data, live_data=live_data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception(f"energy-trends error: {e}")
        raise HTTPException(status_code=500, detail="Energy trend analysis failed")


@router.post("/carbon-footprint")
async def carbon_footprint(payload: Dict):
    """
    Expected payload:
      { "energy_data": [ ... ], "carbon_factor": 0.95(optional) }
    """
    try:
        energy_data = payload.get("energy_data") or []
        carbon_factor = float(payload.get("carbon_factor", 0.95))
        result = await gemini_esg_service.analyze_carbon_footprint(energy_data, carbon_factor=carbon_factor)
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception(f"carbon-footprint error: {e}")
        raise HTTPException(status_code=500, detail="Carbon footprint analysis failed")


@router.post("/generate-report")
async def generate_report(payload: Dict):
    """
    Expected payload:
      { "energy_data": [...], "carbon_data": {...}, "water_data": [...] }
    """
    try:
        energy_data = payload.get("energy_data") or []
        carbon_data = payload.get("carbon_data") or {}
        water_data = payload.get("water_data") or []
        result = await gemini_esg_service.generate_esg_report(energy_data, carbon_data, water_data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception(f"generate-report error: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")


@router.post("/refresh")
async def refresh_gemini_service():
    """Refresh Gemini service to pick up new environment variables."""
    try:
        gemini_esg_service.refresh_service()
        return JSONResponse(
            content={
                "message": "Gemini service refreshed",
                "mock_mode": gemini_esg_service.mock_mode,
                "model": gemini_esg_service.model_name if not gemini_esg_service.mock_mode else "fallback",
                "api_key_configured": not gemini_esg_service.mock_mode,
            }
        )
    except Exception as e:
        logger.exception(f"refresh error: {e}")
        raise HTTPException(status_code=500, detail="Refresh failed")


@router.get("/status")
async def get_gemini_status():
    try:
        status = {
            "service": "Gemini AI",
            "status": "active",
            "model": gemini_esg_service.model_name if not gemini_esg_service.mock_mode else "fallback",
            "mock_mode": gemini_esg_service.mock_mode,
            "api_key_configured": not gemini_esg_service.mock_mode,
            "capabilities": [
                "Energy trend analytics",
                "Carbon footprint analytics",
                "ESG report generation",
            ],
        }
        return JSONResponse(content=status)
    except Exception as e:
        logger.exception(f"status error: {e}")
        raise HTTPException(status_code=500, detail="Status check failed")
