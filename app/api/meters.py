# backend/app/api/meters.py

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone

from app.services.egauge_poller import (
    LATEST, 
    get_egauge_status, 
    force_poll,
    get_cached_data,
    STATUS,
)
from app.services.egauge_client import (
    diagnose_egauge_connection, 
    test_egauge_auth,
    fetch_check_page_register_watts,
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/bertha-house/latest")
async def get_bertha_house_latest(force: bool = False):
    """
    Get latest meter reading for Bertha House.
    
    Parameters:
    - force: If True, force a fresh poll before returning data
    """
    asset_id = "bertha-house"
    
    # Force fresh poll if requested
    if force:
        logger.info(f"Forcing fresh poll for {asset_id}")
        result = await force_poll(asset_id)
        if result["status"] == "error":
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Failed to fetch fresh data",
                    "error": result.get("error"),
                    "suggestion": "Try without force parameter or check eGauge connection"
                }
            )
        data = result["data"]
    else:
        data = get_cached_data(asset_id)
    
    if not data:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No data available yet",
                "suggestion": "The eGauge poller may still be starting up. Try again in a few minutes."
            }
        )
    
    return data


@router.get("/29-degrees-south/latest")
async def get_29_degrees_south_latest(force: bool = False):
    """
    Get latest meter reading for 29 Degrees South.
    
    Parameters:
    - force: If True, force a fresh poll before returning data
    """
    asset_id = "29-degrees-south"
    
    # Force fresh poll if requested
    if force:
        logger.info(f"Forcing fresh poll for {asset_id}")
        result = await force_poll(asset_id)
        if result["status"] == "error":
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Failed to fetch fresh data",
                    "error": result.get("error"),
                    "suggestion": "Try without force parameter or check eGauge connection"
                }
            )
        data = result["data"]
    else:
        data = get_cached_data(asset_id)
    
    if not data:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No data available yet",
                "suggestion": "The eGauge poller may still be starting up. Try again in a few minutes."
            }
        )
    
    return data


@router.get("/{meter_id}/latest")
async def get_meter_latest(meter_id: str, force: bool = False):
    """
    Generic endpoint to get latest meter reading for any meter.
    
    Parameters:
    - meter_id: The meter identifier
    - force: If True, force a fresh poll before returning data
    """
    # Force fresh poll if requested
    if force:
        logger.info(f"Forcing fresh poll for {meter_id}")
        result = await force_poll(meter_id)
        if result["status"] == "error":
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Failed to fetch fresh data",
                    "error": result.get("error"),
                    "suggestion": "Try without force parameter or check eGauge connection"
                }
            )
        data = result["data"]
    else:
        data = get_cached_data(meter_id)
    
    if not data:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No data available yet",
                "suggestion": "The eGauge poller may still be starting up. Try again in a few minutes."
            }
        )
    
    return data


@router.get("/status")
async def get_meter_status(asset_id: str = "bertha-house"):
    """Get status of meter polling"""
    return get_egauge_status(asset_id)


@router.get("/diagnose")
async def diagnose_meter_connection():
    """Run diagnostic on eGauge connection"""
    try:
        # Run diagnostics
        connection_diag = await diagnose_egauge_connection(settings.EGAUGE_BASE_URL)
        auth_diag = await test_egauge_auth(settings.EGAUGE_BASE_URL)
        current_status = get_egauge_status()
        
        # Analyze results
        working_urls = [r for r in connection_diag if r.get("status") == 200]
        auth_required = any(r.get("status") == 401 for r in connection_diag)
        
        return {
            "summary": {
                "has_working_endpoints": len(working_urls) > 0,
                "auth_required": auth_required,
                "auth_configured": auth_diag.get("auth_configured", False),
                "auth_working": auth_diag.get("with_auth", {}).get("success", False),
                "current_health": current_status["status"]["health"],
            },
            "config": {
                "base_url": settings.EGAUGE_BASE_URL,
                "poll_interval": settings.EGAUGE_POLL_INTERVAL_SECONDS,
                "has_auth": bool(settings.EGAUGE_USERNAME and settings.EGAUGE_PASSWORD),
            },
            "connection_tests": connection_diag,
            "auth_test": auth_diag,
            "current_status": current_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Diagnostic failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-auth")
async def test_egauge_authentication():
    """Test eGauge authentication"""
    return await test_egauge_auth(settings.EGAUGE_BASE_URL)


@router.post("/force-poll")
async def trigger_force_poll():
    """Manually trigger a poll (for testing)"""
    result = await force_poll("bertha-house")
    return result


@router.get("/health")
async def get_meter_health():
    """Get health status of all meters"""
    results = {}
    for asset_id in STATUS.keys():
        results[asset_id] = get_egauge_status(asset_id)
    
    # Overall health (worst of all assets)
    all_health = [status["status"]["health"] for status in results.values()]
    overall_health = "healthy"
    if "offline" in all_health:
        overall_health = "offline"
    elif "degraded" in all_health:
        overall_health = "degraded"
    
    return {
        "overall": overall_health,
        "assets": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/history/errors")
async def get_polling_errors(limit: int = 50):
    """Get recent polling errors from database"""
    try:
        from app.core.database import db
        errors = await db.polling_errors.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(length=limit)
        
        return {
            "count": len(errors),
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"Failed to fetch errors: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/test-direct")
async def test_direct_fetch():
    """Test direct eGauge fetch (bypasses cache and scheduler)"""
    try:
        data = await fetch_check_page_register_watts(settings.EGAUGE_BASE_URL)
        return {
            "success": True,
            "data": data,
            "message": "Direct fetch successful",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Direct fetch failed",
            "config": {
                "base_url": settings.EGAUGE_BASE_URL,
                "has_auth": bool(settings.EGAUGE_USERNAME and settings.EGAUGE_PASSWORD),
            }
        }