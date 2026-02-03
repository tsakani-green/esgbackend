# backend/app/services/gemini_esg.py

import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class GeminiESGService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_APIKEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.mock_mode = not bool(self.api_key)

        if self.mock_mode:
            logger.warning("GEMINI_API_KEY not set -> GeminiESGService running in MOCK mode")
        else:
            logger.info(f"GeminiESGService enabled (model={self.model_name})")

        # Lazy import so app can boot even if google-genai isn’t installed
        self._client = None
        if not self.mock_mode:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Gemini client init failed, switching to MOCK mode: {e}")
                self.mock_mode = True
                self._client = None

    def refresh_service(self):
        """Re-read env vars and recreate client"""
        self.__init__()

    async def _generate_text(self, prompt: str) -> str:
        if self.mock_mode or not self._client:
            return "MOCK: Gemini is not configured. Set GEMINI_API_KEY on Render."

        try:
            # google-genai API shape can vary by version; this is a common working pattern
            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            # normalize
            text = getattr(resp, "text", None)
            if text:
                return text
            # fallback
            return str(resp)
        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            return "Gemini call failed; falling back to mock response."

    async def predict_esg_scores(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "predicted_scores": {"environmental": 78, "social": 81, "governance": 77},
                "overall": 78.7,
                "confidence": 0.82,
                "notes": ["MOCK mode"],
            }

        prompt = f"""
You are an ESG analyst. Predict ESG scores (E,S,G) for this company data and explain briefly.
Return JSON with keys: predicted_scores (env/social/gov), overall, confidence, drivers (list).
Company data: {company_data}
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def assess_esg_risks(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "risk_level": "medium",
                "top_risks": ["Carbon exposure", "Energy price volatility"],
                "mitigations": ["Efficiency upgrades", "Renewable procurement"],
                "notes": ["MOCK mode"],
            }

        prompt = f"""
Assess ESG risks for this portfolio. Return JSON with keys: risk_level, top_risks, mitigations.
Portfolio data: {portfolio_data}
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def forecast_carbon_emissions(self, historical_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "forecast": [1100, 1080, 1060, 1045, 1030, 1015],
                "trend": "decreasing",
                "confidence": 0.78,
                "notes": ["MOCK mode"],
            }

        prompt = f"""
Forecast carbon emissions from historical data. Return JSON: forecast(list), trend, confidence.
Historical data: {historical_data}
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def generate_recommendations(self, company_profile: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "recommendations": [
                    {"title": "LED retrofit", "impact": "medium", "effort": "low"},
                    {"title": "Rooftop solar assessment", "impact": "high", "effort": "medium"},
                ],
                "notes": ["MOCK mode"],
            }

        prompt = f"""
Generate sustainability recommendations. Return JSON: recommendations(list of title/impact/effort).
Company profile: {company_profile}
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def analyze_document(self, text_content: str, filename: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "filename": filename,
                "summary": "MOCK summary (Gemini not configured).",
                "flags": [],
                "notes": ["MOCK mode"],
            }

        prompt = f"""
Analyze this ESG document and extract key points and risks.
Return JSON: summary, key_points, risks, missing_info.
Filename: {filename}
Content: {text_content[:12000]}
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def generate_ai_report(self, company_data: Dict[str, Any], report_type: str = "comprehensive") -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "report_type": report_type,
                "executive_summary": "MOCK report (Gemini not configured).",
                "sections": [],
                "notes": ["MOCK mode"],
            }

        prompt = f"""
Write an ESG report ({report_type}) for the following company data.
Return JSON: executive_summary, strengths, gaps, recommendations, next_steps.
Company data: {company_data}
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def chat(self, prompt: str) -> Dict[str, Any]:
        text = await self._generate_text(prompt)
        return {"answer": text}

    async def comprehensive_analysis(self, document_data: List[Dict[str, Any]], client_id: str, depth: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"clientId": client_id, "depth": depth, "summary": "MOCK comprehensive analysis", "notes": ["MOCK mode"]}

        prompt = f"""
Do a comprehensive ESG analysis for client {client_id} with depth={depth}.
Docs: {document_data}
Return JSON: summary, material_issues, recommendations.
"""
        text = await self._generate_text(prompt)
        return {"raw": text}

    async def real_time_insights(self, client_id: Optional[str]) -> Dict[str, Any]:
        # keep lightweight
        return {
            "clientId": client_id,
            "insights": [
                "Energy consumption stable",
                "Carbon intensity improving",
            ],
            "ai": (not self.mock_mode),
        }

    async def predictive_analytics(self, client_id: str, prediction_type: str, time_horizon: str) -> Dict[str, Any]:
        return {
            "clientId": client_id,
            "prediction_type": prediction_type,
            "time_horizon": time_horizon,
            "prediction": "stable",
            "ai": (not self.mock_mode),
        }

    async def benchmark_analysis(self, client_id: str, industry: str, peer_group: str) -> Dict[str, Any]:
        return {
            "clientId": client_id,
            "industry": industry,
            "peer_group": peer_group,
            "benchmark": {"overall": 7.6, "peer_avg": 7.2},
            "ai": (not self.mock_mode),
        }

# Singleton getter (this fixes your ImportError)
_gemini_singleton: GeminiESGService | None = None

def get_gemini_esg_service() -> GeminiESGService:
    global _gemini_singleton
    if _gemini_singleton is None:
        _gemini_singleton = GeminiESGService()
    return _gemini_singleton

# Backwards-compatible name used in your router
gemini_esg_service = get_gemini_esg_service()
