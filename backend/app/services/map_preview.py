import io
import math
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from PIL import Image, ImageDraw

from ..config import settings

USER_AGENT = "bdinvite-map-preview/1.0 (contact: admin@roadtotech.me)"

GOOGLE_MAPS_DOMAINS = (
    "maps.app.goo.gl",
    "goo.gl",
    "google.com",
    "www.google.com",
    "maps.google.com",
)


def is_google_maps_host(host: str) -> bool:
    """Check if the hostname belongs to Google Maps, Google share links, or Goo.gl shortlinks."""
    clean_host = host.lower().strip()
    if clean_host in ("maps.app.goo.gl", "goo.gl", "share.google"):
        return True
    if clean_host.startswith("maps.google."):
        return True
    if clean_host == "google.com" or clean_host.endswith(".google.com") or clean_host.endswith(".google"):
        return True
    # Regional domains like google.es, google.co, google.com.co
    if re.match(r"^(?:www\.)?google\.[a-z.]+$", clean_host):
        return True
    return False


def validate_google_maps_url_format(url: str) -> None:
    """Validate that the given string is a structurally sound Google Maps URL."""
    clean = url.strip()
    if not clean:
        raise ValueError("La URL de Google Maps no puede estar vacía.")

    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("La URL debe comenzar con http:// o https://")

    if not parsed.netloc or not is_google_maps_host(parsed.netloc):
        raise ValueError(
            "La URL debe ser un enlace de Google Maps válido (ej. maps.app.goo.gl/... o google.com/maps/...)"
        )


def extract_coordinates_from_text(text: str) -> tuple[float, float] | None:
    """Extract latitude and longitude from URL fragments, paths, or query strings."""
    # Pattern 1: @<lat>,<lng> (e.g. /@34.143245,-118.255132,17z)
    match_at = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", text)
    if match_at:
        lat = float(match_at.group(1))
        lng = float(match_at.group(2))
        if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
            return lat, lng

    # Pattern 2: !3d<lat>!4d<lng> (Google Maps protobuf data parameter)
    match_data = re.search(r"!3d(-?\d+(?:\.\d+)?)(?:!4d|.*?!4d)(-?\d+(?:\.\d+)?)", text)
    if match_data:
        lat = float(match_data.group(1))
        lng = float(match_data.group(2))
        if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
            return lat, lng

    # Pattern 3: Query parameters (q=lat,lng, ll=lat,lng, destination=lat,lng)
    parsed = urlparse(text)
    if parsed.query:
        qs = parse_qs(parsed.query)
        for param in ("q", "ll", "destination"):
            if param in qs and qs[param]:
                val = qs[param][0].strip()
                m = re.match(r"^(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)$", val)
                if m:
                    lat = float(m.group(1))
                    lng = float(m.group(2))
                    if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
                        return lat, lng

    return None


async def resolve_google_maps_coordinates(
    map_url: str,
    fallback_query: str | None = None,
) -> tuple[float, float, str]:
    """
    Validate and resolve a Google Maps URL, following redirects if necessary,
    and return (latitude, longitude, resolved_url).
    """
    validate_google_maps_url_format(map_url)
    clean_url = map_url.strip()

    # Try direct extraction before making any network requests
    direct_coords = extract_coordinates_from_text(clean_url)
    if direct_coords:
        return direct_coords[0], direct_coords[1], clean_url

    # Follow HTTP redirects to resolve short links (maps.app.goo.gl, share.google, etc.)
    resolved_url = clean_url
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        try:
            response = await client.get(clean_url)
            resolved_url = str(response.url)
            # Check redirect history URLs in case coordinates were in an intermediate hop
            for hop in response.history:
                hop_coords = extract_coordinates_from_text(str(hop.url))
                if hop_coords:
                    return hop_coords[0], hop_coords[1], resolved_url
        except httpx.RequestError as exc:
            raise ValueError(f"No se pudo resolver el enlace de Google Maps: {exc}") from exc

    # Try extraction on the final resolved destination URL
    final_coords = extract_coordinates_from_text(resolved_url)
    if final_coords:
        return final_coords[0], final_coords[1], resolved_url

    # Fallback: check if there is a place search query in the URL or query string
    parsed = urlparse(resolved_url)
    qs = parse_qs(parsed.query)
    query_text = None
    if "q" in qs and qs["q"]:
        query_text = qs["q"][0]
    elif "/place/" in parsed.path:
        # e.g. /maps/place/Fresco+Ristorante/...
        place_part = parsed.path.split("/place/")[1].split("/")[0]
        query_text = unquote(place_part.replace("+", " "))

    # Build search candidates for geocoding
    candidates: list[str] = []
    clean_fallback = fallback_query.strip() if fallback_query else None

    if query_text and clean_fallback:
        candidates.append(f"{query_text}, {clean_fallback}")
    if clean_fallback:
        for line in clean_fallback.splitlines():
            line_str = line.strip().strip(",")
            if line_str and line_str not in candidates:
                candidates.append(line_str)
        if clean_fallback not in candidates:
            candidates.append(clean_fallback)
    if query_text and query_text not in candidates:
        candidates.append(query_text)

    if candidates:
        async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": USER_AGENT}) as client:
            for candidate in candidates:
                try:
                    nom_res = await client.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"q": candidate, "format": "json", "limit": 1},
                    )
                    if nom_res.status_code == 200:
                        results = nom_res.json()
                        if results and isinstance(results, list) and len(results) > 0:
                            lat = float(results[0]["lat"])
                            lng = float(results[0]["lon"])
                            if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
                                return lat, lng, resolved_url
                except Exception:
                    pass

    raise ValueError(
        "No se pudieron extraer las coordenadas de la URL de Google Maps. "
        "Asegúrate de que el enlace dirija a un lugar o coordenadas específicas."
    )


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    """Convert latitude and longitude to floating-point Slippy tile coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


async def generate_map_preview_image(
    lat: float,
    lng: float,
    zoom: int = 16,
    output_path: Path | None = None,
) -> Path:
    """
    Download OpenStreetMap tiles surrounding (lat, lng), stitch them into a canvas,
    crop a 400x400 square centered on the location, render a golden marker pin,
    and save the resulting PNG to output_path (defaulting to settings.map_preview_file).
    """
    dest_path = output_path or settings.map_preview_file
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    xtile, ytile = deg2num(lat, lng, zoom)
    x_int, y_int = int(xtile), int(ytile)
    dx = xtile - x_int
    dy = ytile - y_int

    # Canvas of 3x3 tiles = 768x768 pixels
    canvas = Image.new("RGB", (768, 768), color=(229, 227, 223))

    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": USER_AGENT}) as client:
        for r_idx, y in enumerate(range(y_int - 1, y_int + 2)):
            for c_idx, x in enumerate(range(x_int - 1, x_int + 2)):
                tile_url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                try:
                    res = await client.get(tile_url)
                    if res.status_code == 200:
                        tile = Image.open(io.BytesIO(res.content)).convert("RGB")
                        canvas.paste(tile, (c_idx * 256, r_idx * 256))
                except Exception:
                    # Keep neutral background tile if individual tile fails
                    pass

    # Exact target location within the 768x768 canvas
    cx = 256 + int(dx * 256)
    cy = 256 + int(dy * 256)

    # 400x400 crop centered on target coordinates
    box = (cx - 200, cy - 200, cx + 200, cy + 200)
    cropped = canvas.crop(box)

    # Draw marker pin centered at (200, 200)
    # The pin tip touches (200, 200)
    draw = ImageDraw.Draw(cropped, "RGBA")

    # Ground shadow underneath the pin tip
    draw.ellipse((192, 198, 208, 204), fill=(40, 40, 40, 140))

    # Golden pin pointer (inverted triangle)
    draw.polygon([(188, 184), (212, 184), (200, 200)], fill="#d4a843", outline="#1a1a1a")

    # Golden pin circular head
    draw.ellipse((188, 170, 212, 194), fill="#d4a843", outline="#1a1a1a", width=2)

    # Dark center eye
    draw.ellipse((197, 179, 203, 185), fill="#1a1a1a")

    # Save to disk as PNG
    cropped.save(dest_path, "PNG", optimize=True)
    return dest_path
