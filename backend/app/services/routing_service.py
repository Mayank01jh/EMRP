"""Routing service — OSRM road ETA with haversine fallback."""
from __future__ import annotations

import math

import httpx

from app.core.config import get_settings
from app.core.logging import logger


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def get_road_eta_seconds(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> tuple[int, float]:
    """
    Returns (eta_seconds, distance_km).
    Tries OSRM first; falls back to haversine estimate if unavailable.
    """
    settings = get_settings()
    url = (
        f"{settings.osrm_url}/route/v1/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        "?overview=false&annotations=false"
    )
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            route = data["routes"][0]
            return int(route["duration"]), route["distance"] / 1000.0
    except Exception as exc:
        logger.warning("OSRM unavailable, falling back to haversine", error=str(exc))
        dist_km = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
        # rough estimate: 40 km/h average urban speed
        eta_seconds = int((dist_km / 40.0) * 3600)
        return eta_seconds, dist_km
