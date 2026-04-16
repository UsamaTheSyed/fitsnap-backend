from fastapi import APIRouter
import os
import math
import json
import httpx
from pydantic import BaseModel

router = APIRouter(prefix="/stores", tags=["stores"])


class StoreSearchRequest(BaseModel):
    latitude: float
    longitude: float
    outfit_query: str = ""
    radius_km: float = 10.0


@router.post("/nearby")
async def find_nearby_stores(request: StoreSearchRequest):
    """
    Use Google Places API to find clothing/fashion stores near the user.
    Falls back to mock stores if Google Places API key is not configured.
    """
    GOOGLE_PLACES_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

    stores = []

    # Step 1: Call Google Places Nearby Search
    if GOOGLE_PLACES_KEY:
        try:
            async with httpx.AsyncClient() as client:
                places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    "location": f"{request.latitude},{request.longitude}",
                    "radius": int(request.radius_km * 1000),
                    "type": "clothing_store",
                    "key": GOOGLE_PLACES_KEY,
                }
                resp = await client.get(places_url, params=params)
                data = resp.json()

                for place in data.get("results", [])[:10]:
                    lat = place["geometry"]["location"]["lat"]
                    lng = place["geometry"]["location"]["lng"]

                    # Calculate rough distance
                    dlat = abs(lat - request.latitude)
                    dlng = abs(lng - request.longitude)
                    dist_km = math.sqrt(dlat**2 + dlng**2) * 111
                    dist_str = f"{dist_km:.1f} km"

                    stores.append({
                        "id": place.get("place_id", ""),
                        "name": place.get("name", ""),
                        "address": place.get("vicinity", ""),
                        "latitude": lat,
                        "longitude": lng,
                        "distance": dist_str,
                        "rating": place.get("rating", 0.0),
                        "isOpen": place.get("opening_hours", {})
                                      .get("open_now", False),
                    })
        except Exception as e:
            print(f"Google Places error: {e}")

    # Fallback: return mock stores if Google Places not configured
    if not stores:
        stores = [
            {
                "id": "mock1",
                "name": "Local Fashion Store",
                "address": "Enable Google Places API for real results",
                "latitude": request.latitude,
                "longitude": request.longitude,
                "distance": "Nearby",
                "rating": 4.0,
                "isOpen": True,
            },
            {
                "id": "mock2",
                "name": "Ethnic Wear Collection",
                "address": "Traditional and fusion wear",
                "latitude": request.latitude + 0.002,
                "longitude": request.longitude + 0.001,
                "distance": "0.3 km",
                "rating": 4.5,
                "isOpen": True,
            },
            {
                "id": "mock3",
                "name": "Style Hub",
                "address": "Men's and women's fashion",
                "latitude": request.latitude - 0.003,
                "longitude": request.longitude + 0.002,
                "distance": "0.5 km",
                "rating": 4.2,
                "isOpen": False,
            },
        ]

    return {"stores": stores, "count": len(stores)}
