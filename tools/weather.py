"""Free weather data via Open-Meteo (no API key). Feeds the indirect-impact chains
the system is meant to reason about (e.g. drought -> crop yield -> food/input costs
-> downstream sectors). Geocoding + forecast; cached; degrades gracefully offline.
"""

from __future__ import annotations

import httpx

from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("weather")
_cache = DiskCache("weather", ttl_s=6 * 3600)


async def geocode(name: str) -> dict:
    key = f"geo:{name}"
    cached = _cache.get(key)
    if cached is not None:
        return {**cached[0], "stale": cached[1]}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://geocoding-api.open-meteo.com/v1/search",
                            params={"name": name, "count": 1})
            r.raise_for_status()
            res = (r.json().get("results") or [])
        if not res:
            return {"name": name, "available": False, "reason": "not found"}
        g = res[0]
        out = {"name": name, "lat": g["latitude"], "lon": g["longitude"],
               "country": g.get("country"), "region": g.get("admin1")}
        _cache.set(key, out)
        return {**out, "stale": False}
    except Exception as exc:
        log.warning("geocode_failed", name=name, error=str(exc))
        return {"name": name, "available": False, "error": str(exc)}


async def weather_forecast(latitude: float, longitude: float, days: int = 7) -> dict:
    key = f"fc:{latitude:.2f}:{longitude:.2f}:{days}"
    cached = _cache.get(key)
    if cached is not None:
        return {**cached[0], "stale": cached[1]}
    params = {
        "latitude": latitude, "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": max(1, min(16, days)), "timezone": "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params=params)
            r.raise_for_status()
            data = r.json()
        out = {"latitude": latitude, "longitude": longitude,
               "daily": data.get("daily", {}), "source": "open-meteo"}
        _cache.set(key, out)
        return {**out, "stale": False}
    except Exception as exc:
        log.warning("forecast_failed", error=str(exc))
        stale = _cache.get(key, allow_stale=True)
        if stale is not None:
            return {**stale[0], "stale": True}
        return {"available": False, "error": str(exc)}


async def weather(location: str, days: int = 7) -> dict:
    """Convenience: place name -> forecast (geocode + forecast in one call)."""
    g = await geocode(location)
    if not g.get("lat"):
        return {"location": location, "available": False, "reason": g.get("reason", "geocode failed")}
    fc = await weather_forecast(g["lat"], g["lon"], days)
    return {"location": location, "coords": {"lat": g["lat"], "lon": g["lon"]},
            "country": g.get("country"), "forecast": fc.get("daily", {}),
            "stale": fc.get("stale", False), "source": "open-meteo"}
