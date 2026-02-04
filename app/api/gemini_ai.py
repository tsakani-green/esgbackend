# backend/app/api/gemini_ai.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Dict, Optional
import logging
import io

from pydantic import BaseModel

from app.services.gemini_esg import get_gemini_esg_service

router = APIRouter(prefix="/api/gemini", tags=["Gemini AI"])

logger = logging.getLogger(__name__)


# -----------------------------
# Models
# -----------------------------
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


def _ask(prompt: str) -> str:
    """
    Wrapper: gemini_esg provides a callable(prompt)->text
    """
    svc = get_gemini_esg_service()
    return svc(prompt)


# -----------------------------
# Endpoints
# -----------------------------
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
            "renewable_percentage": 25,
        }

        prompt = f"""
You are an ESG analyst. Predict ESG scores for the company.
Return STRICT JSON with fields:
environmental_score (0-100), social_score (0-100), governance_score (0-100), overall_score (0-100), key_drivers (list), risks (list), recommendations (list).

Time horizon: {request.timeHorizon}

Company data:
{company_data}
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
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

        prompt = f"""
You are an ESG risk officer. Assess ESG risks for this portfolio.
Return STRICT JSON with fields:
top_risks (list), severity_by_risk (object), mitigations (list), quick_wins (list).

Portfolio ID: {request.portfolioId}

Portfolio data:
{portfolio_data}
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
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

        prompt = f"""
You are a carbon accounting specialist. Forecast carbon emissions.
Return STRICT JSON with fields:
forecast_monthly_emissions (list), assumptions (list), risk_factors (list), reduction_opportunities (list).

Client: {request.clientId}

Historical data:
{historical_data}
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
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

        prompt = f"""
You are a sustainability consultant. Generate ESG improvement recommendations.
Return STRICT JSON with fields:
prioritized_actions (list), estimated_costs (object), expected_impact (object), 30_day_plan (list), 90_day_plan (list).

Client: {request.clientId}

Company profile:
{company_profile}
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
    except Exception as e:
        logger.error(f"Gemini recommendations error: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendations failed: {str(e)}")


@router.post("/analyze-document")
async def gemini_analyze_document(
    document: UploadFile = File(...),
    analysis_type: str = Form("comprehensive"),
):
    try:
        logger.info(f"Gemini document analysis for: {document.filename}")

        content = await document.read()
        text = content.decode("utf-8", errors="ignore")

        # Optional PDF extraction
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

        prompt = f"""
You are an ESG analyst. Analyze the following document ({document.filename}).
Analysis type: {analysis_type}

Return STRICT JSON with fields:
summary, key_findings (list), risks (list), opportunities (list), action_items (list).

Document text:
{text[:25000]}
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
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

        prompt = f"""
You are an ESG reporting expert. Generate an ESG report.
Report type: {request.reportType}

Return Markdown (not JSON) with clear headings.

Client: {request.clientId}

Company data:
{company_data}
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
    except Exception as e:
        logger.error(f"Gemini report generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/status")
async def get_gemini_status():
    try:
        # if this function errors, it means Gemini not configured
        _ = get_gemini_esg_service()
        return JSONResponse(
            content={
                "service": "Gemini AI",
                "status": "active",
                "configured": True,
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "service": "Gemini AI",
                "status": "inactive",
                "configured": False,
                "error": str(e),
            }
        )


@router.post("/chat")
async def gemini_esg_chat(payload: ChatRequest):
    try:
        logger.info(f"Gemini ESG chat: {payload.question[:50]}...")

        prompt = f"""
You are an ESG expert assistant.

Question:
{payload.question}

Context:
{payload.context}

Return a helpful, practical answer (plain text).
"""
        answer = _ask(prompt)
        return JSONResponse(content={"answer": answer})
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
