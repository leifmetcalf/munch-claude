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

    Uses a two-step approach: first searches with Google Maps grounding,
    then extracts structured data in a second call.

    Returns:
        RestaurantDetails if found, None otherwise
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Step 1: Search with Google Maps grounding (can't use structured output)
    search_prompt = f"""Find the restaurant: {query}

Provide the full details including:
- Name
- Full address (street number, street name, suburb, state, postcode)
- GPS coordinates (latitude and longitude)
- Phone number
- Website
- Cuisine type"""

    search_config = types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps())],
    )

    if latitude is not None and longitude is not None:
        search_config.tool_config = types.ToolConfig(
            retrieval_config=types.RetrievalConfig(
                lat_lng=types.LatLng(latitude=latitude, longitude=longitude)
            )
        )

    search_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=search_prompt,
        config=search_config,
    )

    search_result = search_response.text
    if not search_result:
        return None

    # Step 2: Extract structured data from the search result
    extract_prompt = f"""Extract restaurant details from this text for OpenStreetMap. If no restaurant was found, return null for name.

Text:
{search_result}

Extract these fields following OSM conventions:

- name: Restaurant name exactly as displayed (e.g., "Café Sydney", "McDonald's")

- latitude: GPS latitude as decimal degrees (e.g., -33.8915)

- longitude: GPS longitude as decimal degrees (e.g., 151.1903)

- addr_unit: Unit, suite, or shop number within a larger building. Only if the restaurant is inside a complex. Examples: "Shop 5", "Suite 110A", "Unit 3"

- addr_housenumber: The street number, which may contain letters or ranges. Examples: "42", "42A", "42-44"

- addr_street: Street name only, without the number. Examples: "George Street", "Oxford Road"

- addr_suburb: Suburb name. Examples: "Surry Hills", "Paddington", "Sydney"

- addr_state: State abbreviation in uppercase. Examples: "NSW", "VIC", "QLD"

- addr_postcode: Postal code. Examples: "2000", "3000"

- cuisine: Type of cuisine in lowercase, using singular form. Multiple types separated by semicolons. Use ethnicity (japanese, italian) or food type (ramen, pizza). Examples: "japanese", "pizza;pasta", "vietnamese;noodle"

- phone: Phone number in international ITU-T E.164 format with + prefix. Examples: "+61 2 9234 5678", "+61 412 345 678"

- website: Full URL with https:// prefix. No tracking parameters or URL shorteners. Example: "https://www.example.com.au" """

    extract_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RestaurantDetails,
    )

    extract_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=extract_prompt,
        config=extract_config,
    )

    details: RestaurantDetails = extract_response.parsed
    if not details.name:
        return None

    return details
