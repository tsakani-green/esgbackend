# /app/app/services/sunsynk_service.py

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)

class SunsynkService:
    """
    Service to interact with Sunsynk API for solar energy data
    """
    
    def __init__(self):
        # Check if required environment variables are set
        if not settings.SUNSYNK_API_URL or not settings.SUNSYNK_API_KEY:
            logger.warning("Sunsynk API configuration missing – Sunsynk service disabled")
            self.enabled = False
            return

        self.enabled = True
        self.api_url = settings.SUNSYNK_API_URL.rstrip('/')
        self.api_key = settings.SUNSYNK_API_KEY
        self.api_secret = getattr(settings, 'SUNSYNK_API_SECRET', None)
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}
        self.cache_timeout = 60  # Cache data for 60 seconds
        
        logger.info(f"SunsynkService initialized with API URL: {self.api_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "ESGBackend/1.0",
                    "Accept": "application/json"
                }
            )
        return self.session
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Sunsynk API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.api_secret:
            headers["X-API-Secret"] = self.api_secret
            
        return headers
    
    async def _make_request(self, endpoint: str, method: str = "GET", 
                           data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make authenticated request to Sunsynk API
        """
        if not self.enabled:
            return None
            
        try:
            session = await self._get_session()
            url = f"{self.api_url}/{endpoint.lstrip('/')}"
            headers = self._get_auth_headers()
            
            logger.debug(f"Making {method} request to {url}")
            
            if method.upper() == "GET":
                async with session.get(url, headers=headers) as response:
                    return await self._handle_response(response)
            elif method.upper() == "POST" and data:
                async with session.post(url, headers=headers, json=data) as response:
                    return await self._handle_response(response)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for {endpoint}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {str(e)}")
            return None
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Optional[Dict]:
        """Handle API response and convert to dict"""
        try:
            if response.status == 200:
                data = await response.json()
                logger.debug(f"API response status: {response.status}")
                return data
            elif response.status == 401:
                logger.error("Sunsynk API authentication failed - check API key")
                return None
            elif response.status == 403:
                logger.error("Sunsynk API access forbidden - check permissions")
                return None
            elif response.status == 404:
                logger.error("Sunsynk API endpoint not found")
                return None
            elif response.status == 429:
                logger.warning("Sunsynk API rate limit exceeded")
                # Could implement retry logic here
                return None
            else:
                logger.error(f"Sunsynk API error: {response.status} - {await response.text()}")
                return None
        except Exception as e:
            logger.error(f"Error processing API response: {str(e)}")
            return None
    
    def _get_cache_key(self, endpoint: str, params: Optional[Dict] = None) -> str:
        """Generate cache key for endpoint and parameters"""
        if params:
            return f"{endpoint}:{hash(frozenset(params.items()))}"
        return endpoint
    
    async def get_bertha_house_data(self) -> Optional[Dict[str, Any]]:
        """
        Get Bertha House energy data from Sunsynk API
        
        Returns:
            Dict containing current power, energy usage, and device info
        """
        cache_key = self._get_cache_key("bertha-house")
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                logger.debug("Returning cached Bertha House data")
                return cached_data
        
        if not self.enabled:
            logger.warning("Sunsynk service disabled - cannot fetch Bertha House data")
            return None
        
        try:
            # Try multiple possible endpoints for Bertha House data
            endpoints_to_try = [
                "bertha-house/data",
                "plants/bertha-house",  # Common pattern for solar plants
                "sites/bertha-house",   # Common pattern for sites
                "plant/1",              # Default plant ID
                "realtime",             # General realtime data
            ]
            
            for endpoint in endpoints_to_try:
                data = await self._make_request(endpoint)
                if data:
                    # Transform the data to our expected format
                    transformed_data = self._transform_bertha_data(data)
                    
                    # Cache the result
                    self.cache[cache_key] = (transformed_data, datetime.now())
                    
                    logger.info(f"Successfully fetched Bertha House data from {endpoint}")
                    return transformed_data
            
            logger.warning("Could not fetch Bertha House data from any endpoint")
            return self._get_fallback_data()
            
        except Exception as e:
            logger.error(f"Error in get_bertha_house_data: {str(e)}")
            return self._get_fallback_data()
    
    def _transform_bertha_data(self, api_data: Dict) -> Dict[str, Any]:
        """
        Transform Sunsynk API response to our standard format
        
        Note: You may need to adjust this based on the actual Sunsynk API response structure
        """
        try:
            # Extract power data (adjust these keys based on actual API response)
            power_kw = api_data.get('power', api_data.get('current_power', 
                        api_data.get('output_power', api_data.get('pac', 0))))
            
            # Extract energy data
            energy_today = api_data.get('energy_today', api_data.get('eday', 
                          api_data.get('today_energy', 0)))
            
            # Extract device info
            device_name = api_data.get('plant_name', api_data.get('site_name',
                          api_data.get('device_name', "Bertha House Inverter")))
            
            # Extract battery data if available
            battery_soc = api_data.get('battery_soc', api_data.get('soc', None))
            battery_power = api_data.get('battery_power', None)
            
            # Extract grid data if available
            grid_power = api_data.get('grid_power', api_data.get('pgrid', None))
            
            transformed = {
                "current_power_kw": float(power_kw) if power_kw else 0,
                "energy_today_kwh": float(energy_today) if energy_today else 0,
                "timestamp": datetime.utcnow().isoformat(),
                "device_info": {
                    "name": str(device_name),
                    "status": api_data.get('status', 'online'),
                    "last_update": api_data.get('last_update', datetime.utcnow().isoformat())
                }
            }
            
            # Add optional fields if available
            if battery_soc is not None:
                transformed["battery_soc_percent"] = float(battery_soc)
            if battery_power is not None:
                transformed["battery_power_kw"] = float(battery_power)
            if grid_power is not None:
                transformed["grid_power_kw"] = float(grid_power)
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming Bertha data: {str(e)}")
            return self._get_fallback_data()
    
    def _get_fallback_data(self) -> Dict[str, Any]:
        """Return fallback data when API is unavailable"""
        return {
            "current_power_kw": 0.0,
            "energy_today_kwh": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
            "device_info": {
                "name": "Bertha House Inverter",
                "status": "offline",
                "last_update": datetime.utcnow().isoformat()
            },
            "is_fallback": True
        }
    
    async def get_device_list(self) -> List[Dict[str, Any]]:
        """
        Get list of available devices/plants from Sunsynk API
        
        Returns:
            List of devices with their details
        """
        if not self.enabled:
            logger.warning("Sunsynk service disabled - cannot fetch device list")
            return []
        
        try:
            data = await self._make_request("plants") or await self._make_request("sites")
            
            if data:
                devices = data.get('data', data.get('plants', data.get('sites', [])))
                
                if isinstance(devices, list):
                    formatted_devices = []
                    for device in devices:
                        formatted_devices.append({
                            "id": device.get('id', device.get('plant_id', 'unknown')),
                            "name": device.get('name', device.get('plant_name', 'Unnamed Device')),
                            "type": device.get('type', 'inverter'),
                            "status": device.get('status', 'unknown'),
                            "capacity_kw": device.get('capacity', device.get('installed_capacity', 0)),
                            "last_updated": device.get('last_update', device.get('updated_at', ''))
                        })
                    return formatted_devices
            
            # If no data or empty response, return at least Bertha House
            return [{
                "id": "1",
                "name": "Bertha House",
                "type": "inverter",
                "status": "online",
                "capacity_kw": 50.0,
                "last_updated": datetime.utcnow().isoformat()
            }]
            
        except Exception as e:
            logger.error(f"Error fetching device list: {str(e)}")
            return []
    
    async def get_historical_data(self, start_date: str, end_date: str, 
                                 granularity: str = "hour") -> Optional[Dict]:
        """
        Get historical energy data for Bertha House
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: Data granularity ('hour', 'day', 'month')
        """
        if not self.enabled:
            return None
        
        try:
            endpoint = f"bertha-house/historical"
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "granularity": granularity
            }
            
            # For POST request
            data = await self._make_request(endpoint, method="POST", data=params)
            return data
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {str(e)}")
            return None
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Sunsynk API
        Returns connection status and details
        """
        if not self.enabled:
            return {
                "connected": False,
                "message": "Sunsynk service is disabled - check environment variables",
                "details": {
                    "SUNSYNK_API_URL": "Not set" if not settings.SUNSYNK_API_URL else "Set",
                    "SUNSYNK_API_KEY": "Not set" if not settings.SUNSYNK_API_KEY else "Set"
                }
            }
        
        try:
            # Try to get a simple endpoint to test connection
            data = await self._make_request("status") or await self._make_request("ping")
            
            if data:
                return {
                    "connected": True,
                    "message": "Successfully connected to Sunsynk API",
                    "api_url": self.api_url,
                    "response_time": "N/A",  # Could measure actual response time
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "connected": False,
                    "message": "Could not get valid response from Sunsynk API",
                    "api_url": self.api_url,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "connected": False,
                "message": f"Connection test failed: {str(e)}",
                "api_url": self.api_url,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Cleanup method to close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("SunsynkService session closed")


# Optional: Create a singleton instance if you prefer that pattern
# sunsynk_service = SunsynkService()