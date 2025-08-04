from geopy.geocoders import Nominatim

def get_coords_for_location(location_name):
    """Converts a location name to latitude and longitude."""
    try:
        geolocator = Nominatim(user_agent="community_watch_app")
        location = geolocator.geocode(location_name)
        if location:
            return (location.latitude, location.longitude)
        return None
    except Exception:
        return None

def get_location_for_coords(lat, lng):
    """Converts coordinates to a human-readable address."""
    try:
        geolocator = Nominatim(user_agent="community_watch_app")
        location = geolocator.reverse((lat, lng), exactly_one=True)
        if location:
            return location.address
        return "Unknown location"
    except Exception:
        return "Could not determine address"