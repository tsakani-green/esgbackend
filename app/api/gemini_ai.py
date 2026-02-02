# backend/app/api/gemini_ai.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
import logging
from pydantic import BaseModel
import io

from app.services.gemini_esg import get_gemini_esg_service

router = APIRouter(prefix="/api/gemini", tags=["Gemini AI"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
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

def _svc():
    return get_gemini_esg_service()

@router.post("/predict-esg-scores")
async def gemini_predict_esg_scores(request: ESGPredictionRequest):
    try:
        logger.info(f"Gemini ESG prediction for client: {request.clientId}")
        company_data = request.companyData or {
            "industry": "Technology",
            "size": "Medium",
            "region": "North America",
            "current_esg_score": 75,
            "emissions": {"scope1": 500, "scope2": 300, "scope3": 200},
            "energy_consumption": 10000,
            "renewable_percentage": 25
        }
        result = await _svc().predict_esg_scores(company_data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini ESG prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.post("/assess-risks")
async def gemini_assess_risks(request: RiskAssessmentRequest):
    try:
        logger.info(f"Gemini risk assessment for portfolio: {request.portfolioId}")
        portfolio_data = request.portfolioData or {
            "assets": [
                {"name": "Office Building", "type": "Real Estate", "emissions": 150},
                {"name": "Manufacturing Plant", "type": "Industrial", "emissions": 800},
            ],
            "total_emissions": 950,
            "industry": "Mixed",
        }
        result = await _svc().assess_esg_risks(portfolio_data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini risk assessment error: {e}")
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {str(e)}")

@router.post("/forecast-carbon")
async def gemini_forecast_carbon(request: CarbonForecastRequest):
    try:
        logger.info(f"Gemini carbon forecast for client: {request.clientId}")
        historical_data = request.historicalData or {
            "monthly_emissions": [1200, 1150, 1180, 1220, 1190, 1160],
            "energy_consumption": [8000, 7800, 8100, 8300, 8200, 7900],
            "production_volume": [100, 95, 98, 102, 99, 96],
        }
        result = await _svc().forecast_carbon_emissions(historical_data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini carbon forecast error: {e}")
        raise HTTPException(status_code=500, detail=f"Carbon forecast failed: {str(e)}")

@router.post("/recommendations")
async def gemini_generate_recommendations(request: RecommendationsRequest):
    try:
        logger.info(f"Gemini recommendations for client: {request.clientId}")
        company_profile = request.companyProfile or {
            "industry": "Technology",
            "size": "Medium",
            "current_esg_score": 75,
            "budget": 100000,
            "priorities": ["energy", "emissions", "water"],
        }
        result = await _svc().generate_recommendations(company_profile)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini recommendations error: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendations failed: {str(e)}")

@router.post("/analyze-document")
async def gemini_analyze_document(document: UploadFile = File(...), analysis_type: str = Form("comprehensive")):
    try:
        logger.info(f"Gemini document analysis for: {document.filename}")
        content = await document.read()
        text = content.decode("utf-8", errors="ignore")

        # If PDF, attempt to extract text (optional)
        if document.filename.lower().endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                extracted = ""
                for page in reader.pages:
                    extracted += page.extract_text() or ""
                text = extracted or text
            except Exception:
                pass

        result = await _svc().analyze_document(text, document.filename)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini document analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Document analysis failed: {str(e)}")

@router.post("/generate-report")
async def gemini_generate_report(request: AIReportRequest):
    try:
        logger.info(f"Gemini report generation for client: {request.clientId}")
        company_data = request.companyData or {
            "name": "Sample Company",
            "industry": "Technology",
            "esg_scores": {"environmental": 76, "social": 82, "governance": 79},
            "initiatives": ["Solar panels", "Employee wellness", "Board training"],
        }
        result = await _svc().generate_ai_report(company_data, request.reportType)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini report generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.post("/refresh")
async def refresh_gemini_service():
    try:
        svc = _svc()
        svc.refresh_service()
        return JSONResponse(
            content={
                "message": "Gemini service refreshed",
                "mock_mode": getattr(svc, "mock_mode", True),
                "model": getattr(svc, "model_name", "gemini-pro-mock"),
                "api_key_configured": not getattr(svc, "mock_mode", True),
            }
        )
    except Exception as e:
        logger.error(f"Gemini refresh error: {e}")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")

@router.get("/status")
async def get_gemini_status():
    try:
        svc = _svc()
        status = {
            "service": "Gemini AI",
            "status": "active",
            "model": getattr(svc, "model_name", "gemini-pro-mock"),
            "mock_mode": getattr(svc, "mock_mode", True),
            "api_key_configured": not getattr(svc, "mock_mode", True),
            "capabilities": [
                "ESG score predictions",
                "Risk assessment",
                "Carbon forecasting",
                "Sustainability recommendations",
                "Document analysis",
                "AI report generation",
            ],
        }
        return JSONResponse(content=status)
    except Exception as e:
        logger.error(f"Gemini status error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/chat")
async def gemini_esg_chat(payload: ChatRequest):
    try:
        logger.info(f"Gemini ESG chat: {payload.question[:50]}...")
        svc = _svc()

        if getattr(svc, "mock_mode", True):
            q = payload.question.lower()
            if "report" in q:
                answer = "I can help generate ESG reports. Tell me your company name, sector, and reporting standard (GRI/ISSB/CSRD)."
            elif "recommend" in q or "improve" in q:
                answer = "Top actions: energy audit, LED + sensors, HVAC scheduling, and renewable feasibility study."
            elif "score" in q or "rating" in q:
                answer = "Estimated ESG: 7.8/10 (mock). Provide real KPIs for a better assessment."
            else:
                answer = f"As an ESG assistant, here’s a practical response (mock): {payload.question}"
            return JSONResponse(content={"answer": answer, "model": "gemini-pro-mock", "confidence": 0.85})

        prompt = f"""
You are an ESG expert assistant.
Question: {payload.question}

Context: {payload.context}

Return a helpful, practical answer.
"""
        result = await svc.chat(prompt)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
