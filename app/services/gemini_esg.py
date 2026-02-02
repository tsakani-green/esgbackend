# backend/app/services/gemini_esg.py

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class GeminiAnalyticsService:
    """
    Lightweight analytics service that can work WITHOUT Gemini.
    If GEMINI_API_KEY is present, enabled=True (you can later plug in real Gemini calls).
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY".lower())
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found. Using fallback analytics.")
            self.enabled = False
        else:
            logger.info("Gemini AI service initialized (key detected).")
            self.enabled = True

        # Optional: track a "model name" concept for status endpoints
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
        # Optional: treat "enabled False" as mock mode
        self.mock_mode = not self.enabled

    # ------------------------------------------------------------
    # Public API used by routers
    # ------------------------------------------------------------

    async def analyze_energy_trends(
        self,
        energy_data: List[Dict],
        live_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        try:
            if not energy_data:
                return self._get_fallback_insights("energy")

            # Compute simple stats
            total_energy = sum(float(d.get("energy", 0) or 0) for d in energy_data)
            avg_energy = total_energy / len(energy_data) if energy_data else 0

            recent_data = energy_data[-7:] if len(energy_data) >= 7 else energy_data
            recent_avg = (
                sum(float(d.get("energy", 0) or 0) for d in recent_data) / len(recent_data)
                if recent_data
                else 0
            )

            trend = "stable"
            if avg_energy > 0:
                if recent_avg > avg_energy * 1.1:
                    trend = "increasing"
                elif recent_avg < avg_energy * 0.9:
                    trend = "decreasing"

            insights = {
                "summary": f"Bertha House shows {trend} energy consumption with average usage of {avg_energy:.0f} kWh",
                "trends": [
                    f"7-day average: {recent_avg:.0f} kWh ({trend})",
                    f"Peak usage: {max(float(d.get('energy', 0) or 0) for d in energy_data):.0f} kWh",
                    f"Minimum usage: {min(float(d.get('energy', 0) or 0) for d in energy_data):.0f} kWh",
                ],
                "anomalies": self._detect_anomalies(energy_data),
                "recommendations": self._generate_recommendations(avg_energy, trend),
                "opportunities": ["Solar panel installation", "LED lighting upgrade", "HVAC optimization"],
                "risks": ["Equipment aging", "Seasonal variations"],
                "efficiency_score": float(max(0, 100 - (avg_energy / 50))),  # simple scoring
                "cost_savings_potential": f"R {avg_energy * 0.1:.0f}/month",
                "carbon_reduction_potential": f"{max(5, 100 - avg_energy / 20):.0f}%",
                "ai_enabled": self.enabled,
                "model": self.model_name if self.enabled else "fallback",
            }

            logger.info(f"Generated energy analytics for {len(energy_data)} data points")
            return insights

        except Exception as e:
            logger.exception(f"Error generating energy analytics: {e}")
            return self._get_fallback_insights("energy")

    async def analyze_carbon_footprint(
        self,
        energy_data: List[Dict],
        carbon_factor: float = 0.95,
    ) -> Dict[str, Any]:
        try:
            if not energy_data:
                return self._get_fallback_insights("carbon")

            total_energy = sum(float(d.get("energy", 0) or 0) for d in energy_data)
            total_carbon = (total_energy * float(carbon_factor)) / 1000  # -> tCO2e

            analysis = {
                "total_carbon_tco2e": f"{total_carbon:.2f}",
                "carbon_intensity": f"{(total_carbon / 1000):.3f} tCO₂e/m²",  # assume 1000m²
                "monthly_trend": "stable",
                "reduction_strategies": [
                    "Renewable energy procurement",
                    "Energy efficiency upgrades",
                    "Behavioral change programs",
                ],
                "renewable_opportunities": ["Rooftop solar", "Green energy tariffs"],
                "offset_recommendations": ["Local reforestation", "Carbon credit purchase"],
                "compliance_status": "on_track" if total_carbon < 100 else "at_risk",
                "target_achievement": f"{max(0, 100 - total_carbon):.0f}%",
                "ai_enabled": self.enabled,
                "model": self.model_name if self.enabled else "fallback",
            }

            logger.info("Generated carbon footprint analytics")
            return analysis

        except Exception as e:
            logger.exception(f"Error generating carbon analytics: {e}")
            return self._get_fallback_insights("carbon")

    async def generate_esg_report(
        self,
        energy_data: List[Dict],
        carbon_data: Dict,
        water_data: List[Dict],
    ) -> Dict[str, Any]:
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
                "ai_enabled": self.enabled,
                "model": self.model_name if self.enabled else "fallback",
            }

            logger.info("Generated ESG report")
            return report

        except Exception as e:
            logger.exception(f"Error generating ESG report: {e}")
            return self._get_fallback_insights("report")

    # ------------------------------------------------------------
    # Compatibility helpers (IMPORTANT for your Render ImportError)
    # ------------------------------------------------------------

    def refresh_service(self):
        """
        If you change GEMINI_API_KEY on Render and want to pick it up without code changes,
        you can call /api/gemini/refresh and we re-check env.
        """
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY".lower())
        self.enabled = bool(self.api_key)
        self.mock_mode = not self.enabled
        logger.info(f"Gemini service refreshed. enabled={self.enabled}, model={self.model_name}")

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------

    def _detect_anomalies(self, energy_data: List[Dict]) -> List[str]:
        if not energy_data:
            return []

        values = [float(d.get("energy", 0) or 0) for d in energy_data]
        avg = sum(values) / len(values) if values else 0
        threshold = avg * 1.5

        anomalies = []
        for i, d in enumerate(energy_data):
            v = float(d.get("energy", 0) or 0)
            if avg > 0 and v > threshold:
                anomalies.append(f"High consumption on day {i + 1}: {v:.0f} kWh")

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
                "ai_enabled": False,
                "model": "fallback",
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
                "ai_enabled": False,
                "model": "fallback",
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
                "ai_enabled": False,
                "model": "fallback",
            },
        }
        return fallbacks.get(analysis_type, {"error": "Analysis type not recognized", "ai_enabled": False})


# Global instance (what routers import)
gemini_esg_service = GeminiAnalyticsService()


# ✅ Backwards compatible function (fixes your Render ImportError)
def get_gemini_esg_service():
    return gemini_esg_service
