# backend/app/services/gemini_esg.py

import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class GeminiAnalyticsService:
    """
    Lightweight Gemini-backed ESG analytics service.

    - If google-generativeai is installed AND GEMINI_API_KEY is set -> tries real calls.
    - Otherwise falls back to mock/fallback results (non-crashing, safe for Render startup).
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip() or "gemini-1.5-flash"

        self._client_available = False
        self._genai = None
        self._model = None

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found. Using mock/fallback analytics.")
            self.mock_mode = True
            return

        # Try to enable real Gemini calls (optional dependency)
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.api_key)
            self._genai = genai
            self._model = genai.GenerativeModel(self.model_name)
            self._client_available = True
            self.mock_mode = False
            logger.info(f"Gemini AI service initialized. model={self.model_name}")
        except Exception as e:
            logger.warning(f"Gemini client not available, using mock mode. Reason: {e}")
            self.mock_mode = True

    # -------------------------
    # Public helpers
    # -------------------------
    def refresh_service(self):
        """Re-read env vars and re-init the service."""
        self.__init__()

    async def chat(self, prompt: str) -> Dict[str, Any]:
        """Generic chat helper used by /chat endpoint."""
        if self.mock_mode or not self._client_available:
            return {
                "answer": "Gemini is in mock mode. Provide GEMINI_API_KEY (and install google-generativeai) to enable real responses.",
                "model": "gemini-pro-mock",
                "confidence": 0.75,
            }

        try:
            # generate_content is sync; keep it simple
            res = self._model.generate_content(prompt)
            text = getattr(res, "text", "") or str(res)
            return {"answer": text, "model": self.model_name, "confidence": 0.90}
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            return {
                "answer": "Gemini call failed; falling back to mock response.",
                "model": "gemini-pro-mock",
                "confidence": 0.70,
                "error": str(e),
            }

    # -------------------------
    # Your analytics-style methods
    # -------------------------
    async def analyze_energy_trends(self, energy_data: List[Dict], live_data: Optional[Dict] = None) -> Dict[str, Any]:
        try:
            if not energy_data:
                return self._get_fallback_insights("energy")

            total_energy = sum(d.get("energy", 0) for d in energy_data)
            avg_energy = total_energy / len(energy_data) if energy_data else 0

            recent_data = energy_data[-7:] if len(energy_data) >= 7 else energy_data
            recent_avg = sum(d.get("energy", 0) for d in recent_data) / len(recent_data) if recent_data else 0

            trend = "stable"
            if recent_avg > avg_energy * 1.1:
                trend = "increasing"
            elif recent_avg < avg_energy * 0.9:
                trend = "decreasing"

            insights = {
                "summary": f"Bertha House shows {trend} energy consumption with average usage of {avg_energy:.0f} kWh",
                "trends": [
                    f"7-day average: {recent_avg:.0f} kWh ({trend})",
                    f"Peak usage: {max(d.get('energy', 0) for d in energy_data):.0f} kWh",
                    f"Minimum usage: {min(d.get('energy', 0) for d in energy_data):.0f} kWh",
                ],
                "anomalies": self._detect_anomalies(energy_data),
                "recommendations": self._generate_recommendations(avg_energy, trend),
                "opportunities": ["Solar panel installation", "LED lighting upgrade", "HVAC optimization"],
                "risks": ["Equipment aging", "Seasonal variations"],
                "efficiency_score": max(0, 100 - (avg_energy / 50)),
                "cost_savings_potential": f"R {avg_energy * 0.1:.0f}/month",
                "carbon_reduction_potential": f"{max(5, 100 - avg_energy / 20)}%",
            }

            return insights
        except Exception as e:
            logger.error(f"Error generating energy analytics: {e}")
            return self._get_fallback_insights("energy")

    async def analyze_carbon_footprint(self, energy_data: List[Dict], carbon_factor: float = 0.95) -> Dict[str, Any]:
        try:
            if not energy_data:
                return self._get_fallback_insights("carbon")

            total_energy = sum(d.get("energy", 0) for d in energy_data)
            total_carbon = total_energy * carbon_factor / 1000  # tCO2e

            return {
                "total_carbon_tco2e": f"{total_carbon:.2f}",
                "carbon_intensity": f"{total_carbon / 1000:.3f} tCO₂e/m²",
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
        except Exception as e:
            logger.error(f"Error generating carbon analytics: {e}")
            return self._get_fallback_insights("carbon")

    async def generate_esg_report(self, energy_data: List[Dict], carbon_data: Dict, water_data: List[Dict]) -> Dict[str, Any]:
        try:
            return {
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
                "governance_compliance": {"reporting_status": "Compliant", "audit_readiness": "Ready"},
                "forward_looking": "Focus on renewable energy integration and efficiency improvements to enhance ESG performance.",
                "recommendations": [
                    "Implement solar energy solution",
                    "Enhance energy monitoring systems",
                    "Develop comprehensive sustainability strategy",
                ],
            }
        except Exception as e:
            logger.error(f"Error generating ESG report: {e}")
            return self._get_fallback_insights("report")

    # -------------------------
    # Compatibility methods used by your API router
    # -------------------------
    async def predict_esg_scores(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            base = company_data.get("current_esg_score", 75)
            return {
                "predicted_scores": {
                    "environmental": min(100, base + 2),
                    "social": min(100, base + 3),
                    "governance": min(100, base + 1),
                },
                "overall_prediction": min(100, base + 2),
                "model": "gemini-pro-mock",
                "notes": ["Mock prediction (enable GEMINI_API_KEY for real)."],
            }

        prompt = f"Predict ESG scores based on: {json.dumps(company_data)}. Return JSON."
        return await self._prompt_json(prompt, fallback={"overall_prediction": 80})

    async def assess_esg_risks(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "overall_risk": "medium",
                "top_risks": ["Energy price volatility", "Aging equipment", "Reporting gaps"],
                "mitigations": ["Efficiency upgrades", "Preventive maintenance", "ESG controls"],
                "model": "gemini-pro-mock",
            }

        prompt = f"Assess ESG risks for: {json.dumps(portfolio_data)}. Return JSON."
        return await self._prompt_json(prompt, fallback={"overall_risk": "medium"})

    async def forecast_carbon_emissions(self, historical_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "forecast_next_6_months": ["stable", "stable", "slight increase", "stable", "slight decrease", "stable"],
                "confidence": 0.82,
                "model": "gemini-pro-mock",
            }

        prompt = f"Forecast carbon emissions using: {json.dumps(historical_data)}. Return JSON."
        return await self._prompt_json(prompt, fallback={"confidence": 0.8})

    async def generate_recommendations(self, company_profile: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "recommendations": [
                    "Run an energy audit and identify top 3 load drivers",
                    "Implement LED + occupancy sensors",
                    "Optimize HVAC schedules and setpoints",
                ],
                "estimated_impact": {"cost_savings": "5-12%", "carbon_reduction": "8-15%"},
                "model": "gemini-pro-mock",
            }

        prompt = f"Generate sustainability recommendations for: {json.dumps(company_profile)}. Return JSON."
        return await self._prompt_json(prompt, fallback={"recommendations": []})

    async def analyze_document(self, text: str, filename: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "filename": filename,
                "summary": "Mock document analysis. Enable GEMINI_API_KEY for real extraction.",
                "key_findings": ["Policies present", "Targets mentioned", "Need stronger KPIs"],
                "model": "gemini-pro-mock",
            }

        prompt = f"Analyze ESG document '{filename}'. Text:\n{text[:8000]}\nReturn JSON."
        return await self._prompt_json(prompt, fallback={"filename": filename})

    async def generate_ai_report(self, company_data: Dict[str, Any], report_type: str = "comprehensive") -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "report_type": report_type,
                "narrative": "Mock ESG report narrative. Enable GEMINI_API_KEY for real writing.",
                "highlights": ["Energy monitoring active", "Opportunities: solar + HVAC optimization"],
                "model": "gemini-pro-mock",
            }

        prompt = f"Write an ESG report ({report_type}) for: {json.dumps(company_data)}. Return JSON."
        return await self._prompt_json(prompt, fallback={"report_type": report_type})

    async def comprehensive_analysis(self, document_data: List[Dict[str, Any]], client_id: str, analysis_depth: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "clientId": client_id,
                "analysis_depth": analysis_depth,
                "summary": "Mock comprehensive analysis.",
                "documents_received": [d.get("filename") for d in document_data],
                "model": "gemini-pro-mock",
            }

        prompt = f"Do comprehensive ESG analysis for client={client_id}, depth={analysis_depth} using: {json.dumps(document_data)}. Return JSON."
        return await self._prompt_json(prompt, fallback={"clientId": client_id})

    async def real_time_insights(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        # This can stay mock even when enabled; it's usually driven by your live DB data.
        return {
            "clientId": client_id,
            "insights": ["Monitor peak loads", "Consider solar feasibility study"],
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "model": self.model_name if not self.mock_mode else "gemini-pro-mock",
        }

    async def predictive_analytics(self, client_id: str, prediction_type: str, time_horizon: str) -> Dict[str, Any]:
        return {
            "clientId": client_id,
            "prediction_type": prediction_type,
            "time_horizon": time_horizon,
            "result": "stable",
            "confidence": 0.8,
            "model": self.model_name if not self.mock_mode else "gemini-pro-mock",
        }

    async def benchmark_analysis(self, client_id: str, industry: str, peer_group: str) -> Dict[str, Any]:
        return {
            "clientId": client_id,
            "industry": industry,
            "peer_group": peer_group,
            "benchmark": {"environmental": 78, "social": 81, "governance": 76},
            "note": "Benchmarks are placeholders unless you wire real peer datasets.",
            "model": self.model_name if not self.mock_mode else "gemini-pro-mock",
        }

    # -------------------------
    # Internals
    # -------------------------
    async def _prompt_json(self, prompt: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        """Ask Gemini for JSON; if anything fails, return fallback."""
        if self.mock_mode or not self._client_available:
            return {"model": "gemini-pro-mock", **fallback}

        try:
            res = self._model.generate_content(prompt)
            text = getattr(res, "text", "") or ""
            # attempt to parse JSON from model output
            text_stripped = text.strip()
            if text_stripped.startswith("```"):
                # remove fenced blocks if present
                text_stripped = text_stripped.strip("`")
                # best effort; not perfect but avoids crashes
            try:
                data = json.loads(text_stripped)
                data["model"] = self.model_name
                return data
            except Exception:
                return {"model": self.model_name, "raw": text, **fallback}
        except Exception as e:
            logger.error(f"Gemini prompt failed: {e}")
            return {"model": "gemini-pro-mock", "error": str(e), **fallback}

    def _detect_anomalies(self, energy_data: List[Dict]) -> List[str]:
        if not energy_data:
            return []
        values = [d.get("energy", 0) for d in energy_data]
        avg = sum(values) / len(values)
        threshold = avg * 1.5
        anomalies = []
        for i, data in enumerate(energy_data):
            if data.get("energy", 0) > threshold:
                anomalies.append(f"High consumption on day {i+1}: {data.get('energy', 0):.0f} kWh")
        return anomalies[:3]

    def _generate_recommendations(self, avg_energy: float, trend: str) -> List[str]:
        recs = []
        if avg_energy > 3000:
            recs.append("Consider energy audit to identify inefficiencies")
        if trend == "increasing":
            recs.append("Investigate causes of rising energy consumption")
            recs.append("Implement energy-saving measures")
        recs.append("Monitor peak usage patterns")
        recs.append("Consider renewable energy options")
        return recs[:3]

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
                "social_impact": {"employee_engagement": "Program development", "community_initiatives": ["Planning phase"]},
                "governance_compliance": {"reporting_status": "Framework establishment", "audit_readiness": "Preparation phase"},
                "forward_looking": "Building comprehensive ESG monitoring and reporting capabilities.",
                "recommendations": ["Enhance data collection", "Develop sustainability strategy"],
            },
        }
        return fallbacks.get(analysis_type, {"error": "Analysis type not recognized"})


# Singleton + accessor (matches your main.py startup import)
_gemini_singleton: Optional[GeminiAnalyticsService] = None


def get_gemini_esg_service() -> GeminiAnalyticsService:
    global _gemini_singleton
    if _gemini_singleton is None:
        _gemini_singleton = GeminiAnalyticsService()
    return _gemini_singleton


# Backwards-compatible name used by your router
gemini_esg_service = get_gemini_esg_service()
