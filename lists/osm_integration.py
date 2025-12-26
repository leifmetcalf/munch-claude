"""
OpenStreetMap API v0.6 integration for creating nodes.
"""

import urllib.request
import xml.etree.ElementTree as ET

from django.conf import settings


class OsmAuthError(Exception):
    """Raised when OSM API returns 401 Unauthorized (token revoked or invalid)."""

    pass


def _make_request(method: str, url: str, access_token: str, data: bytes = None) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/xml",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        if e.code == 401:
            raise OsmAuthError("OpenStreetMap authorization was revoked or is invalid")
        raise ValueError(f"OSM API error {e.code}: {error_body}")


def build_restaurant_tags(data: dict) -> dict[str, str]:
    """Build OSM tags from restaurant data. Converts addr_* keys to addr:* tags."""
    tags = {"amenity": data.get("amenity", "restaurant"), "name": data["name"]}

    for key, value in data.items():
        if not value or key in ("amenity", "name", "latitude", "longitude"):
            continue
        if key == "cuisine":
            # Normalize cuisine: lowercase, underscores, semicolon-separated
            cuisine_values = [
                c.strip().lower().replace(" ", "_") for c in value.split(",")
            ]
            tags["cuisine"] = ";".join(cuisine_values)
        elif key.startswith("addr_"):
            tags[key.replace("_", ":")] = value
        else:
            tags[key] = value

    return tags


def build_node_xml(latitude: float, longitude: float, tags: dict[str, str]) -> str:
    """Build XML for node creation (for preview)."""
    osm = ET.Element("osm")
    node = ET.SubElement(osm, "node")
    node.set("changeset", "{CHANGESET_ID}")
    node.set("lat", str(latitude))
    node.set("lon", str(longitude))
    for key, value in tags.items():
        if value:
            tag = ET.SubElement(node, "tag")
            tag.set("k", key[:255])
            tag.set("v", str(value)[:255])
    return ET.tostring(osm, encoding="unicode")


def create_restaurant_node(
    access_token: str,
    data: dict,
) -> int:
    """Create a restaurant node in OSM. Returns the new node ID."""
    tags = build_restaurant_tags(data)

    # Create changeset
    osm = ET.Element("osm")
    changeset = ET.SubElement(osm, "changeset")
    for k, v in [("created_by", "Munch Zone munchzone.net"), ("comment", "Added restaurant with Munch Zone")]:
        tag = ET.SubElement(changeset, "tag")
        tag.set("k", k)
        tag.set("v", v)
    xml_bytes = f'<?xml version="1.0" encoding="UTF-8"?>{ET.tostring(osm, encoding="unicode")}'.encode(
        "utf-8"
    )
    changeset_id = int(
        _make_request(
            "PUT", f"{settings.OSM_API_URL}/changeset/create", access_token, xml_bytes
        ).strip()
    )

    # Create node
    osm = ET.Element("osm")
    node = ET.SubElement(osm, "node")
    node.set("changeset", str(changeset_id))
    node.set("lat", str(data["latitude"]))
    node.set("lon", str(data["longitude"]))
    for key, value in tags.items():
        if value:
            tag = ET.SubElement(node, "tag")
            tag.set("k", key[:255])
            tag.set("v", str(value)[:255])
    xml_bytes = f'<?xml version="1.0" encoding="UTF-8"?>{ET.tostring(osm, encoding="unicode")}'.encode(
        "utf-8"
    )
    node_id = int(
        _make_request(
            "POST", f"{settings.OSM_API_URL}/nodes", access_token, xml_bytes
        ).strip()
    )

    # Close changeset
    _make_request(
        "PUT",
        f"{settings.OSM_API_URL}/changeset/{changeset_id}/close",
        access_token,
        b"",
    )

    return node_id
