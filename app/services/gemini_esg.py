# backend/app/services/gemini_esg.py

import os
import io
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class GeminiAnalyticsService:
    """
    Single service used by all Gemini endpoints.
    - If GEMINI_API_KEY is missing -> mock_mode True (fallback outputs)
    - If GEMINI_API_KEY exists -> uses google-generativeai (lazy import)
    """

    def __init__(self):
        self.api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.model_name = (os.getenv("GEMINI_MODEL") or "gemini-1.5-flash").strip()

        self.enabled = bool(self.api_key)
        self.mock_mode = not self.enabled

        self._genai = None
        self._model = None

        if not self.enabled:
            logger.warning("GEMINI_API_KEY not found. Using fallback analytics (mock_mode=True).")
        else:
            self._init_client()

    def _init_client(self):
        """Initialize Gemini client lazily and safely."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
            self._model = genai.GenerativeModel(self.model_name)
            self.mock_mode = False
            self.enabled = True
            logger.info(f"Gemini AI ready: model={self.model_name}")
        except Exception as e:
            self._genai = None
            self._model = None
            self.enabled = False
            self.mock_mode = True
            logger.warning(f"Gemini init failed -> fallback mode: {type(e).__name__}: {e}")

    def refresh_service(self):
        """Reload env vars (useful after changing Render env)."""
        self.api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.model_name = (os.getenv("GEMINI_MODEL") or "gemini-1.5-flash").strip()
        self.enabled = bool(self.api_key)
        self.mock_mode = not self.enabled

        self._genai = None
        self._model = None

        if self.enabled:
            self._init_client()
        else:
            logger.warning("Gemini refresh: GEMINI_API_KEY still missing -> mock_mode=True")

    # ---------------------------------------------------------------------
    # Your existing analytics methods (kept, only small safety improvements)
    # ---------------------------------------------------------------------

    async def analyze_energy_trends(self, energy_data: List[Dict], live_data: Optional[Dict] = None) -> Dict[str, Any]:
        try:
            if not energy_data:
                return self._get_fallback_insights("energy")

            total_energy = sum(float(d.get("energy", 0) or 0) for d in energy_data)
            avg_energy = total_energy / len(energy_data) if energy_data else 0

            recent_data = energy_data[-7:] if len(energy_data) >= 7 else energy_data
            recent_avg = sum(float(d.get("energy", 0) or 0) for d in recent_data) / len(recent_data) if recent_data else 0

            trend = "stable"
            if recent_avg > avg_energy * 1.1:
                trend = "increasing"
            elif recent_avg < avg_energy * 0.9:
                trend = "decreasing"

            values = [float(d.get("energy", 0) or 0) for d in energy_data]
            peak = max(values) if values else 0
            minimum = min(values) if values else 0

            insights = {
                "summary": f"Bertha House shows {trend} energy consumption with average usage of {avg_energy:.0f} kWh",
                "trends": [
                    f"7-day average: {recent_avg:.0f} kWh ({trend})",
                    f"Peak usage: {peak:.0f} kWh",
                    f"Minimum usage: {minimum:.0f} kWh",
                ],
                "anomalies": self._detect_anomalies(energy_data),
                "recommendations": self._generate_recommendations(avg_energy, trend),
                "opportunities": ["Solar panel installation", "LED lighting upgrade", "HVAC optimization"],
                "risks": ["Equipment aging", "Seasonal variations"],
                "efficiency_score": max(0, 100 - (avg_energy / 50)),  # Simple scoring
                "cost_savings_potential": f"R {avg_energy * 0.1:.0f}/month",
                "carbon_reduction_potential": f"{max(5, 100 - avg_energy / 20)}%",
            }

            logger.info(f"Generated energy analytics for {len(energy_data)} data points")
            return insights

        except Exception as e:
            logger.error(f"Error generating energy analytics: {str(e)}")
            return self._get_fallback_insights("energy")

    async def analyze_carbon_footprint(self, energy_data: List[Dict], carbon_factor: float = 0.95) -> Dict[str, Any]:
        try:
            if not energy_data:
                return self._get_fallback_insights("carbon")

            total_energy = sum(float(d.get("energy", 0) or 0) for d in energy_data)
            total_carbon = total_energy * float(carbon_factor) / 1000  # tCO2e

            analysis = {
                "total_carbon_tco2e": f"{total_carbon:.2f}",
                "carbon_intensity": f"{total_carbon / 1000:.3f} tCO₂e/m²",  # assuming 1000m²
                "monthly_trend": "stable",
                "reduction_strategies": [
                    "Renewable energy procurement",
                    "Energy efficiency upgrades",
                    "Behavioral change programs",
                ],
                "renewable_opportunities": ["Rooftop solar", "Green energy tariffs"],
                "offset_recommendations": ["Local reforestation", "Carbon credit purchase"],
                "compliance_status": "on_track" if total_carbon < 100 else "at_risk",
                "target_achievement": f"{max(0, 100 - total_carbon)}%",
            }

            logger.info("Generated carbon footprint analytics")
            return analysis

        except Exception as e:
            logger.error(f"Error generating carbon analytics: {str(e)}")
            return self._get_fallback_insights("carbon")

    async def generate_esg_report(self, energy_data: List[Dict], carbon_data: Dict, water_data: List[Dict]) -> Dict[str, Any]:
        try:
            report = {
                "executive_summary": "Bertha House demonstrates moderate ESG performance with opportunities for improvement in energy efficiency and carbon reduction.",
                "key_achievements": [
                    "Consistent energy monitoring",
                    "Carbon footprint tracking established",
                    "ESG reporting framework implemented",
                ],
                "environmental_metrics": {
                    "energy_efficiency": "Good",
                    "carbon_management": "Improving",
                    "water_conservation": "Adequate",
                },
                "social_impact": {
                    "employee_engagement": "High",
                    "community_initiatives": ["Local sustainability programs", "Educational outreach"],
                },
                "governance_compliance": {
                    "reporting_status": "Compliant",
                    "audit_readiness": "Ready",
                },
                "forward_looking": "Focus on renewable energy integration and efficiency improvements to enhance ESG performance.",
                "recommendations": [
                    "Implement solar energy solution",
                    "Enhance energy monitoring systems",
                    "Develop comprehensive sustainability strategy",
                ],
            }

            logger.info("Generated ESG report")
            return report

        except Exception as e:
            logger.error(f"Error generating ESG report: {str(e)}")
            return self._get_fallback_insights("report")

    def _detect_anomalies(self, energy_data: List[Dict]) -> List[str]:
        if not energy_data:
            return []

        values = [float(d.get("energy", 0) or 0) for d in energy_data]
        avg = sum(values) / len(values) if values else 0
        threshold = avg * 1.5 if avg else 0

        anomalies = []
        for i, data in enumerate(energy_data):
            val = float(data.get("energy", 0) or 0)
            if threshold and val > threshold:
                anomalies.append(f"High consumption on day {i+1}: {val:.0f} kWh")

        return anomalies[:3]

    def _generate_recommendations(self, avg_energy: float, trend: str) -> List[str]:
        recommendations = []

        if avg_energy > 3000:
            recommendations.append("Consider energy audit to identify inefficiencies")

        if trend == "increasing":
            recommendations.append("Investigate causes of rising energy consumption")
            recommendations.append("Implement energy-saving measures")

        recommendations.append("Monitor peak usage patterns")
        recommendations.append("Consider renewable energy options")

        return recommendations[:3]

    def _get_fallback_insights(self, analysis_type: str) -> Dict[str, Any]:
        fallbacks = {
            "energy": {
                "summary": "Energy performance analysis based on available data",
                "trends": ["Data collection in progress"],
                "anomalies": ["Monitoring for patterns"],
                "recommendations": ["Install comprehensive monitoring", "Establish baseline metrics"],
                "opportunities": ["Energy efficiency assessment"],
                "risks": ["Limited visibility on consumption patterns"],
                "efficiency_score": 75,
                "cost_savings_potential": "R 1,500/month",
                "carbon_reduction_potential": "10%",
            },
            "carbon": {
                "total_carbon_tco2e": "15.5",
                "carbon_intensity": "0.015 tCO₂e/m²",
                "monthly_trend": "stable",
                "reduction_strategies": ["Energy efficiency", "Renewable energy"],
                "renewable_opportunities": ["Solar assessment"],
                "offset_recommendations": ["Local carbon projects"],
                "compliance_status": "on_track",
                "target_achievement": "85%",
            },
            "report": {
                "executive_summary": "ESG reporting framework established with ongoing data collection and analysis.",
                "key_achievements": ["Monitoring systems operational", "Baseline metrics established"],
                "environmental_metrics": {
                    "energy_efficiency": "Good",
                    "carbon_management": "Developing",
                    "water_conservation": "Adequate",
                },
                "social_impact": {
                    "employee_engagement": "Program development",
                    "community_initiatives": ["Planning phase"],
                },
                "governance_compliance": {
                    "reporting_status": "Framework establishment",
                    "audit_readiness": "Preparation phase",
                },
                "forward_looking": "Building comprehensive ESG monitoring and reporting capabilities.",
                "recommendations": ["Enhance data collection", "Develop sustainability strategy"],
            },
        }
        return fallbacks.get(analysis_type, {"error": "Analysis type not recognized"})

    # ---------------------------------------------------------------------
    # Methods your gemini_ai router is calling (so Render won't crash)
    # ---------------------------------------------------------------------

    async def predict_esg_scores(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "mode": "mock",
                "prediction": {"environmental": 76, "social": 82, "governance": 79, "overall": 79},
                "notes": "GEMINI_API_KEY missing -> mock response",
            }
        return await self._ask_gemini_json(
            "Predict ESG scores (E,S,G,overall) from this company profile. Return JSON only.",
            company_data,
        )

    async def assess_esg_risks(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "mode": "mock",
                "risks": ["Carbon compliance risk", "Energy cost volatility", "Operational disruptions"],
                "severity": "medium",
            }
        return await self._ask_gemini_json(
            "Assess ESG risks for this portfolio. Return JSON with risks[], severity, mitigations[]. JSON only.",
            portfolio_data,
        )

    async def forecast_carbon_emissions(self, historical_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "mode": "mock",
                "forecast_next_6_months": [1180, 1165, 1172, 1150, 1142, 1130],
                "trend": "slight_decrease",
            }
        return await self._ask_gemini_json(
            "Forecast carbon emissions for next 6 months. Return JSON only.",
            historical_data,
        )

    async def generate_recommendations(self, company_profile: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "mode": "mock",
                "recommendations": [
                    "Improve HVAC scheduling",
                    "Install LED lighting",
                    "Increase renewable energy share",
                ],
            }
        return await self._ask_gemini_json(
            "Generate sustainability recommendations. Return JSON with recommendations[]. JSON only.",
            company_profile,
        )

    async def analyze_document(self, text: str, filename: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "mode": "mock",
                "filename": filename,
                "summary": "Document analysis unavailable (no GEMINI_API_KEY).",
                "key_findings": [],
                "risks": [],
                "recommendations": [],
            }
        payload = {"filename": filename, "text": text[:12000]}
        return await self._ask_gemini_json(
            "Analyze this ESG document and return JSON with summary, key_findings[], risks[], recommendations[]. JSON only.",
            payload,
        )

    async def generate_ai_report(self, company_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "mode": "mock",
                "report_type": report_type,
                "report": "AI report generation unavailable (no GEMINI_API_KEY).",
            }
        payload = {"report_type": report_type, "company_data": company_data}
        return await self._ask_gemini_json(
            "Generate an ESG report narrative. Return JSON with sections. JSON only.",
            payload,
        )

    async def chat(self, prompt: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"answer": "Mock chat: configure GEMINI_API_KEY to enable live responses.", "model": "mock"}
        try:
            resp_text = await self._ask_gemini_text(prompt)
            return {"answer": resp_text, "model": self.model_name}
        except Exception as e:
            return {"answer": f"Gemini chat error: {type(e).__name__}: {e}", "model": "error"}

    async def comprehensive_analysis(self, document_data: List[Dict[str, Any]], client_id: str, analysis_depth: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"mode": "mock", "clientId": client_id, "analysis_depth": analysis_depth, "summary": "Mock comprehensive analysis"}
        payload = {"clientId": client_id, "analysis_depth": analysis_depth, "documents": document_data}
        return await self._ask_gemini_json(
            "Perform comprehensive ESG analysis over provided documents. Return JSON only.",
            payload,
        )

    async def real_time_insights(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        if self.mock_mode:
            return {"mode": "mock", "clientId": client_id, "insights": ["Mock real-time insights"]}
        payload = {"clientId": client_id}
        return await self._ask_gemini_json(
            "Generate real-time ESG insights. Return JSON only.",
            payload,
        )

    async def predictive_analytics(self, client_id: str, prediction_type: str, time_horizon: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"mode": "mock", "clientId": client_id, "prediction_type": prediction_type, "time_horizon": time_horizon}
        payload = {"clientId": client_id, "prediction_type": prediction_type, "time_horizon": time_horizon}
        return await self._ask_gemini_json(
            "Run predictive ESG analytics. Return JSON only.",
            payload,
        )

    async def benchmark_analysis(self, client_id: str, industry: str, peer_group: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"mode": "mock", "clientId": client_id, "industry": industry, "peer_group": peer_group, "benchmark": "mock"}
        payload = {"clientId": client_id, "industry": industry, "peer_group": peer_group}
        return await self._ask_gemini_json(
            "Benchmark ESG performance against peers. Return JSON only.",
            payload,
        )

    # ---------------------------------------------------------------------
    # Gemini helpers
    # ---------------------------------------------------------------------

    async def _ask_gemini_text(self, prompt: str) -> str:
        if self.mock_mode or not self._model:
            return "Gemini unavailable (mock_mode)."
        resp = self._model.generate_content(prompt)
        return getattr(resp, "text", None) or str(resp)

    async def _ask_gemini_json(self, instruction: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        We request JSON-only, but still handle if Gemini returns text.
        """
        if self.mock_mode or not self._model:
            return {"mode": "mock", "error": "Gemini unavailable", "payload": payload}

        prompt = (
            f"{instruction}\n\n"
            f"Return STRICT JSON only.\n\n"
            f"PAYLOAD:\n{payload}"
        )
        text = await self._ask_gemini_text(prompt)

        # Best-effort JSON parse
        try:
            import json
            return json.loads(text)
        except Exception:
            return {"mode": "live", "raw": text, "note": "Gemini did not return strict JSON"}


# Global instance used by routers/imports
gemini_esg_service = GeminiAnalyticsService()
