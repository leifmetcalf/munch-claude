"""
Gemini API integration with Google Maps grounding for restaurant search.
"""

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class RestaurantDetails(BaseModel):
    """Structured restaurant details from Gemini. All null if restaurant not found."""

    name: str | None = Field(default=None, description="Restaurant name")
    latitude: float | None = Field(default=None, description="Latitude coordinate")
    longitude: float | None = Field(default=None, description="Longitude coordinate")
    addr_unit: str | None = Field(default=None, description="Unit or shop number")
    addr_housenumber: str | None = Field(default=None, description="Street number")
    addr_street: str | None = Field(
        default=None, description="Street name only, without number"
    )
    addr_suburb: str | None = Field(default=None, description="Suburb or city name")
    addr_state: str | None = Field(
        default=None, description="State abbreviation (e.g., NSW, VIC)"
    )
    addr_postcode: str | None = Field(default=None, description="Postal code")
    cuisine: str | None = Field(
        default=None, description="Type of cuisine (e.g., japanese, italian)"
    )
    phone: str | None = Field(default=None, description="Phone number")
    website: str | None = Field(default=None, description="Website URL")


def get_restaurant_details_from_gemini(
    query: str, latitude: float | None = None, longitude: float | None = None
) -> RestaurantDetails | None:
    """
    Search for a restaurant using Gemini with Google Maps grounding.

    Returns:
        RestaurantDetails if found, None otherwise
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = f"""Find the restaurant: {query}

If found, fill in the details. If not found, return null for name."""

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps())],
        response_mime_type="application/json",
        response_schema=RestaurantDetails,
    )

    if latitude is not None and longitude is not None:
        config.tool_config = types.ToolConfig(
            retrieval_config=types.RetrievalConfig(
                lat_lng=types.LatLng(latitude=latitude, longitude=longitude)
            )
        )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )

    details: RestaurantDetails = response.parsed
    if not details.name:
        return None

    return details
