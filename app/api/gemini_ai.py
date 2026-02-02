# backend/app/api/gemini_ai.py

import io
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
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

        result = await gemini_esg_service.predict_esg_scores(company_data)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini ESG prediction error: {str(e)}")
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

        result = await gemini_esg_service.assess_esg_risks(portfolio_data)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini risk assessment error: {str(e)}")
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

        result = await gemini_esg_service.forecast_carbon_emissions(historical_data)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini carbon forecast error: {str(e)}")
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

        result = await gemini_esg_service.generate_recommendations(company_profile)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini recommendations error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendations failed: {str(e)}")


@router.post("/analyze-document")
async def gemini_analyze_document(
    document: UploadFile = File(...),
    analysis_type: str = Form("comprehensive"),
):
    try:
        logger.info(f"Gemini document analysis for: {document.filename}")

        content = await document.read()
        text = ""

        # Use pypdf which you have installed
        if (document.filename or "").lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                for page in reader.pages:
                    text += page.extract_text() or ""
            except Exception as e:
                logger.warning(f"PDF text extraction failed, fallback to bytes decode: {e}")
                text = content.decode("utf-8", errors="ignore")
        else:
            text = content.decode("utf-8", errors="ignore")

        result = await gemini_esg_service.analyze_document(text, document.filename or "document")
        result["analysis_type"] = analysis_type

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini document analysis error: {str(e)}")
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

        result = await gemini_esg_service.generate_ai_report(company_data, request.reportType)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.post("/refresh")
async def refresh_gemini_service():
    try:
        gemini_esg_service.refresh_service()
        return JSONResponse(
            content={
                "message": "Gemini service refreshed",
                "mock_mode": gemini_esg_service.mock_mode,
                "model": gemini_esg_service.model_name,
                "api_key_configured": not gemini_esg_service.mock_mode,
            }
        )
    except Exception as e:
        logger.error(f"Gemini refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")


@router.get("/status")
async def get_gemini_status():
    try:
        status = {
            "service": "Gemini AI",
            "status": "active",
            "model": gemini_esg_service.model_name if not gemini_esg_service.mock_mode else "mock",
            "mock_mode": gemini_esg_service.mock_mode,
            "api_key_configured": not gemini_esg_service.mock_mode,
        }
        return JSONResponse(content=status)

    except Exception as e:
        logger.error(f"Gemini status error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/chat")
async def gemini_esg_chat(question: str = Form(...), context: str = Form("")):
    try:
        logger.info(f"Gemini ESG chat: {question[:50]}...")
        prompt = f"""
You are an ESG (Environmental, Social, Governance) expert assistant.
Answer this question: {question}

Context: {context}

Provide accurate, actionable ESG guidance with specific recommendations.
Focus on practical sustainability solutions.
"""
        result = await gemini_esg_service.chat(prompt)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Gemini chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/comprehensive-analysis")
async def comprehensive_esg_analysis(
    clientId: str = Form(...),
    files: List[UploadFile] = File(...),
    analysis_depth: str = Form("standard"),
):
    try:
        logger.info(f"Comprehensive ESG analysis for client: {clientId}")

        document_data = []
        for f in files:
            content = await f.read()
            text = ""

            if (f.filename or "").lower().endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(content))
                    for page in reader.pages:
                        text += page.extract_text() or ""
                except Exception:
                    text = content.decode("utf-8", errors="ignore")
            else:
                text = content.decode("utf-8", errors="ignore")

            document_data.append(
                {
                    "filename": f.filename,
                    "content": text[:4000],
                    "type": "pdf" if (f.filename or "").lower().endswith(".pdf") else "text",
                }
            )

        result = await gemini_esg_service.comprehensive_analysis(document_data, clientId, analysis_depth)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Comprehensive analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/real-time-insights")
async def get_real_time_esg_insights(clientId: str = None):
    try:
        logger.info(f"Real-time ESG insights for client: {clientId}")
        insights = await gemini_esg_service.real_time_insights(clientId)
        return JSONResponse(content=insights)

    except Exception as e:
        logger.error(f"Real-time insights error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Insights failed: {str(e)}")


@router.post("/predictive-analytics")
async def predictive_esg_analytics(
    clientId: str = Form(...),
    prediction_type: str = Form("performance"),
    time_horizon: str = Form("12months"),
):
    try:
        logger.info(f"Predictive ESG analytics for client: {clientId}")
        result = await gemini_esg_service.predictive_analytics(clientId, prediction_type, time_horizon)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Predictive analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/benchmark-analysis")
async def benchmark_esg_performance(
    clientId: str = Form(...),
    industry: str = Form("general"),
    peer_group: str = Form("industry"),
):
    try:
        logger.info(f"Benchmark analysis for client: {clientId}")
        result = await gemini_esg_service.benchmark_analysis(clientId, industry, peer_group)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Benchmark analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {str(e)}")
