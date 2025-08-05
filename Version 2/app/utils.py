"""
Utility functions for geocoding and reverse geocoding in the CommunityWatch application.
"""

from typing import Tuple, Optional
from geopy.geocoders import Nominatim
from flask import current_app

def get_coords_for_location(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Convert a location name to latitude and longitude coordinates.

    Args:
        location_name: The name or address of the location to geocode.

    Returns:
        A tuple of (latitude, longitude) if successful, None otherwise.
    """
    try:
        geolocator = Nominatim(user_agent="community_watch_app")
        location = geolocator.geocode(location_name)
        if location:
            return location.latitude, location.longitude
        current_app.logger.warning(f"Geocoding failed for location: {location_name}")
        return None
    except Exception as e:
        current_app.logger.error(f"Geocoding error for {location_name}: {str(e)}")
        return None

def get_location_for_coords(lat: float, lng: float) -> str:
    """
    Convert coordinates to a human-readable address.

    Args:
        lat: Latitude of the location.
        lng: Longitude of the location.

    Returns:
        A string containing the address or an error message if the lookup fails.
    """
    try:
        geolocator = Nominatim(user_agent="community_watch_app")
        location = geolocator.reverse((lat, lng), exactly_one=True)
        if location:
            return location.address
        current_app.logger.warning(f"Reverse geocoding failed for coordinates: ({lat}, {lng})")
        return "Unknown location"
    except Exception as e:
        current_app.logger.error(f"Reverse geocoding error for ({lat}, {lng}): {str(e)}")
        return "Could not determine address"