"""
api/external_apis.py
Handles all external API integrations for NancyTravels.
Each function corresponds to an OpenAI function definition in functions/api_functions.json.
"""

import json
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config.json."""
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    with open(config_path, "r") as f:
        return json.load(f)


def search_restaurants(
    city: str,
    party_size: int,
    date: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_price_per_person: Optional[float] = None
) -> dict:
    """
    Search for restaurants using the OpenTable API.
    Falls back to simulated results if API key is not configured.
    """
    config = load_config()
    api_key = config.get("external_apis", {}).get("opentable", {}).get("api_key", "")
    base_url = config.get("external_apis", {}).get("opentable", {}).get("base_url", "")

    # Use public OpenTable endpoint (no auth required for this endpoint)
    try:
        params = {
            "city": city,
            "size": party_size,
        }
        if city:
            response = requests.get(
                f"{base_url}/restaurants",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                restaurants = data.get("restaurants", [])[:5]
                results = []
                for r in restaurants:
                    price = r.get("price", 2)
                    price_per_person = price * 15  # Estimate
                    if max_price_per_person and price_per_person > max_price_per_person:
                        continue
                    results.append({
                        "name": r.get("name", "Unknown Restaurant"),
                        "cuisine": r.get("cuisine", "Various"),
                        "price_range": "$" * price,
                        "estimated_cost_per_person": price_per_person,
                        "rating": r.get("aggregate_rating", "N/A"),
                        "address": r.get("address", ""),
                        "city": r.get("city", city),
                        "booking_link": r.get("reserve_url", f"https://www.opentable.com/city/{city.lower().replace(' ', '-')}"),
                        "source": "OpenTable"
                    })
                if results:
                    return {
                        "success": True,
                        "restaurants": results,
                        "city": city,
                        "party_size": party_size
                    }
    except Exception as e:
        logger.warning(f"OpenTable API error: {e}")

    # Return simulated results as fallback
    return _simulate_restaurants(city, party_size, cuisine, max_price_per_person)


def _simulate_restaurants(
    city: str,
    party_size: int,
    cuisine: Optional[str],
    max_price_per_person: Optional[float]
) -> dict:
    """Return simulated restaurant results for demo purposes."""
    restaurants = [
        {
            "name": f"The {city} Kitchen",
            "cuisine": cuisine or "Contemporary",
            "price_range": "$$",
            "estimated_cost_per_person": 35,
            "rating": "4.5",
            "address": f"123 Main St, {city}",
            "booking_link": f"https://www.opentable.com/s/?covers={party_size}&dateTime=&metroId=&regionIds=&neighborhoodIds=&term={city.replace(' ', '+')}",
            "source": "OpenTable (Demo)"
        },
        {
            "name": f"{city} Bistro",
            "cuisine": cuisine or "French",
            "price_range": "$$$",
            "estimated_cost_per_person": 60,
            "rating": "4.7",
            "address": f"456 Park Ave, {city}",
            "booking_link": f"https://www.opentable.com/s/?covers={party_size}&term={city.replace(' ', '+')}",
            "source": "OpenTable (Demo)"
        },
        {
            "name": f"Casa {city}",
            "cuisine": cuisine or "Mediterranean",
            "price_range": "$$",
            "estimated_cost_per_person": 28,
            "rating": "4.3",
            "address": f"789 Harbor Blvd, {city}",
            "booking_link": f"https://www.opentable.com/s/?covers={party_size}&term={city.replace(' ', '+')}",
            "source": "OpenTable (Demo)"
        }
    ]
    if max_price_per_person:
        restaurants = [r for r in restaurants if r["estimated_cost_per_person"] <= max_price_per_person]
    return {
        "success": True,
        "restaurants": restaurants,
        "city": city,
        "party_size": party_size,
        "note": "Demo results – add your OpenTable API key to config.json for live data"
    }


def search_events(
    city: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = "all",
    max_price: Optional[float] = None,
    num_tickets: Optional[int] = 1
) -> dict:
    """
    Search for events using the Ticketmaster Discovery API.
    Falls back to simulated results if API key is not configured.
    """
    config = load_config()
    api_key = config.get("external_apis", {}).get("ticketmaster", {}).get("api_key", "")
    base_url = config.get("external_apis", {}).get("ticketmaster", {}).get("base_url", "")

    if api_key and not api_key.startswith("YOUR_"):
        try:
            params = {
                "apikey": api_key,
                "city": city,
                "size": 5,
            }
            if category and category != "all":
                params["classificationName"] = category
            if start_date:
                params["startDateTime"] = f"{start_date}T00:00:00Z"
            if end_date:
                params["endDateTime"] = f"{end_date}T23:59:59Z"

            response = requests.get(
                f"{base_url}/events.json",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                events_data = data.get("_embedded", {}).get("events", [])
                results = []
                for event in events_data[:5]:
                    price_ranges = event.get("priceRanges", [{}])
                    min_price = price_ranges[0].get("min", 0) if price_ranges else 0
                    if max_price and min_price > max_price:
                        continue
                    venues = event.get("_embedded", {}).get("venues", [{}])
                    venue = venues[0] if venues else {}
                    results.append({
                        "name": event.get("name", "Unknown Event"),
                        "category": event.get("classifications", [{}])[0].get("segment", {}).get("name", category),
                        "date": event.get("dates", {}).get("start", {}).get("localDate", "TBD"),
                        "venue": venue.get("name", "TBD"),
                        "address": f"{venue.get('address', {}).get('line1', '')}, {city}",
                        "min_price": min_price,
                        "max_price": price_ranges[0].get("max", min_price) if price_ranges else min_price,
                        "ticket_link": event.get("url", f"https://www.ticketmaster.com/search?q={city.replace(' ', '+')}"),
                        "source": "Ticketmaster"
                    })
                if results:
                    return {
                        "success": True,
                        "events": results,
                        "city": city
                    }
        except Exception as e:
            logger.warning(f"Ticketmaster API error: {e}")

    return _simulate_events(city, category, max_price, num_tickets)


def _simulate_events(
    city: str,
    category: Optional[str],
    max_price: Optional[float],
    num_tickets: Optional[int]
) -> dict:
    """Return simulated event results for demo purposes."""
    events = [
        {
            "name": f"{city} Music Festival",
            "category": "Music",
            "date": "Upcoming",
            "venue": f"{city} Amphitheater",
            "address": f"1 Concert Way, {city}",
            "min_price": 45,
            "max_price": 150,
            "ticket_link": f"https://www.ticketmaster.com/search?q={city.replace(' ', '+')}&type=event",
            "source": "Ticketmaster (Demo)"
        },
        {
            "name": f"{city} Arts & Culture Tour",
            "category": "Arts",
            "date": "Daily",
            "venue": f"{city} Arts District",
            "address": f"Art District, {city}",
            "min_price": 20,
            "max_price": 50,
            "ticket_link": f"https://www.ticketmaster.com/search?q={city.replace(' ', '+')}+arts",
            "source": "Ticketmaster (Demo)"
        },
        {
            "name": f"{city} Comedy Night",
            "category": "Comedy",
            "date": "Weekly",
            "venue": f"The Laugh Factory {city}",
            "address": f"Comedy Lane, {city}",
            "min_price": 30,
            "max_price": 60,
            "ticket_link": f"https://www.ticketmaster.com/search?q={city.replace(' ', '+')}+comedy",
            "source": "Ticketmaster (Demo)"
        }
    ]
    if max_price:
        events = [e for e in events if e["min_price"] <= max_price]
    return {
        "success": True,
        "events": events,
        "city": city,
        "note": "Demo results – add your Ticketmaster API key to config.json for live data"
    }


def search_attractions(
    city: str,
    category: Optional[str] = "all",
    max_price_per_person: Optional[float] = None,
    num_people: Optional[int] = 1
) -> dict:
    """
    Search for attractions using the TripAdvisor API.
    Falls back to simulated results if API key is not configured.
    """
    config = load_config()
    api_key = config.get("external_apis", {}).get("tripadvisor", {}).get("api_key", "")
    base_url = config.get("external_apis", {}).get("tripadvisor", {}).get("base_url", "")

    if api_key and not api_key.startswith("YOUR_"):
        try:
            params = {
                "key": api_key,
                "searchQuery": f"{category} attractions in {city}",
                "language": "en"
            }
            response = requests.get(
                f"{base_url}/location/search",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                locations = data.get("data", [])[:5]
                results = []
                for loc in locations:
                    results.append({
                        "name": loc.get("name", "Unknown Attraction"),
                        "category": category,
                        "description": loc.get("description", "A must-see attraction"),
                        "rating": loc.get("rating", "N/A"),
                        "price_per_person": 25,
                        "address": loc.get("address_obj", {}).get("address_string", f"{city}"),
                        "booking_link": f"https://www.tripadvisor.com/Search?q={loc.get('name', city).replace(' ', '+')}",
                        "source": "TripAdvisor"
                    })
                if results:
                    return {
                        "success": True,
                        "attractions": results,
                        "city": city
                    }
        except Exception as e:
            logger.warning(f"TripAdvisor API error: {e}")

    return _simulate_attractions(city, category, max_price_per_person, num_people)


def _simulate_attractions(
    city: str,
    category: Optional[str],
    max_price_per_person: Optional[float],
    num_people: Optional[int]
) -> dict:
    """Return simulated attraction results for demo purposes."""
    attractions = [
        {
            "name": f"{city} Historical Museum",
            "category": "Museums",
            "description": f"Explore the rich history and culture of {city} through fascinating exhibits",
            "rating": "4.6",
            "price_per_person": 18,
            "hours": "9:00 AM - 5:00 PM",
            "address": f"Historic District, {city}",
            "booking_link": f"https://www.tripadvisor.com/Search?q={city.replace(' ', '+')}+museum",
            "source": "TripAdvisor (Demo)"
        },
        {
            "name": f"{city} City Walking Tour",
            "category": "Tours",
            "description": f"Discover the hidden gems and iconic landmarks of {city} with a local guide",
            "rating": "4.8",
            "price_per_person": 25,
            "hours": "10:00 AM & 2:00 PM daily",
            "address": f"City Center, {city}",
            "booking_link": f"https://www.tripadvisor.com/Search?q={city.replace(' ', '+')}+walking+tour",
            "source": "TripAdvisor (Demo)"
        },
        {
            "name": f"{city} Botanical Garden",
            "category": "Outdoors",
            "description": f"A stunning collection of plants and flowers from around the world in the heart of {city}",
            "rating": "4.4",
            "price_per_person": 12,
            "hours": "8:00 AM - 6:00 PM",
            "address": f"Garden District, {city}",
            "booking_link": f"https://www.tripadvisor.com/Search?q={city.replace(' ', '+')}+botanical+garden",
            "source": "TripAdvisor (Demo)"
        },
        {
            "name": f"{city} Skyline Observation Deck",
            "category": "Sights",
            "description": f"Breathtaking panoramic views of {city} from the highest point in the city",
            "rating": "4.7",
            "price_per_person": 30,
            "hours": "10:00 AM - 10:00 PM",
            "address": f"Downtown, {city}",
            "booking_link": f"https://www.tripadvisor.com/Search?q={city.replace(' ', '+')}+observation+deck",
            "source": "TripAdvisor (Demo)"
        }
    ]
    if max_price_per_person:
        attractions = [a for a in attractions if a["price_per_person"] <= max_price_per_person]
    return {
        "success": True,
        "attractions": attractions,
        "city": city,
        "note": "Demo results – add your TripAdvisor API key to config.json for live data"
    }


def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    num_guests: int,
    max_price_per_night: Optional[float] = None
) -> dict:
    """
    Search for hotels using the Expedia API.
    Falls back to simulated results if API key is not configured.
    """
    return _simulate_hotels(city, check_in, check_out, num_guests, max_price_per_night)


def _simulate_hotels(
    city: str,
    check_in: str,
    check_out: str,
    num_guests: int,
    max_price_per_night: Optional[float]
) -> dict:
    """Return simulated hotel results for demo purposes."""
    hotels = [
        {
            "name": f"The Grand {city} Hotel",
            "rating": "4.5",
            "stars": 4,
            "price_per_night": 180,
            "amenities": ["Pool", "Spa", "Restaurant", "Free WiFi", "Gym"],
            "address": f"1 Grand Blvd, {city}",
            "booking_link": f"https://www.expedia.com/Hotel-Search?destination={city.replace(' ', '+')}",
            "source": "Expedia (Demo)"
        },
        {
            "name": f"{city} Boutique Inn",
            "rating": "4.7",
            "stars": 3,
            "price_per_night": 120,
            "amenities": ["Free WiFi", "Breakfast included", "City views"],
            "address": f"45 Heritage St, {city}",
            "booking_link": f"https://www.expedia.com/Hotel-Search?destination={city.replace(' ', '+')}",
            "source": "Expedia (Demo)"
        },
        {
            "name": f"{city} Budget Stay",
            "rating": "4.0",
            "stars": 2,
            "price_per_night": 75,
            "amenities": ["Free WiFi", "24-hour reception"],
            "address": f"200 Economy Ave, {city}",
            "booking_link": f"https://www.expedia.com/Hotel-Search?destination={city.replace(' ', '+')}",
            "source": "Expedia (Demo)"
        }
    ]
    if max_price_per_night:
        hotels = [h for h in hotels if h["price_per_night"] <= max_price_per_night]
    return {
        "success": True,
        "hotels": hotels,
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "note": "Demo results – add your Expedia API key to config.json for live data"
    }


def get_city_info(
    city: str,
    info_type: Optional[str] = "all"
) -> dict:
    """
    Get general city information using TripAdvisor.
    Falls back to simulated results if API key is not configured.
    """
    config = load_config()
    api_key = config.get("external_apis", {}).get("tripadvisor", {}).get("api_key", "")

    if api_key and not api_key.startswith("YOUR_"):
        try:
            base_url = config["external_apis"]["tripadvisor"]["base_url"]
            params = {
                "key": api_key,
                "searchQuery": city,
                "language": "en"
            }
            response = requests.get(
                f"{base_url}/location/search",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                locations = data.get("data", [])
                if locations:
                    loc = locations[0]
                    return {
                        "success": True,
                        "city": city,
                        "name": loc.get("name", city),
                        "overview": f"{city} is a vibrant destination with plenty to offer.",
                        "transportation": f"Getting around {city} is easy with public transit, taxis, and ride-sharing apps.",
                        "neighborhoods": f"Popular neighborhoods include the downtown area, historic district, and waterfront.",
                        "tips": [
                            "Book popular restaurants in advance",
                            "Use public transit to save on transportation costs",
                            "Visit popular attractions early to avoid crowds"
                        ],
                        "source": "TripAdvisor"
                    }
        except Exception as e:
            logger.warning(f"TripAdvisor city info error: {e}")

    return {
        "success": True,
        "city": city,
        "overview": f"{city} is a wonderful destination full of culture, food, and activities.",
        "transportation": (
            f"Getting around {city}: Use the metro/subway for long distances, "
            "ride-sharing apps (Uber/Lyft) for convenience, "
            "and walk or bike for short distances in central areas."
        ),
        "neighborhoods": (
            f"Key areas in {city}: Downtown (business & nightlife), "
            "Historic District (culture & sightseeing), "
            "Waterfront/Park areas (outdoors & relaxation), "
            "Arts District (galleries & restaurants)"
        ),
        "tips": [
            "Book popular restaurants and attractions at least 1-2 days in advance",
            "Download the local transit app for real-time updates",
            "Many museums offer free admission on certain days",
            "Early morning visits to popular spots mean smaller crowds",
            "Ask your hotel for neighborhood-specific recommendations"
        ],
        "best_time_to_visit": "Spring and Fall typically offer the best weather and fewer crowds",
        "source": "TripAdvisor (Demo)",
        "note": "Demo results – add your TripAdvisor API key to config.json for live data"
    }


# Map of function names to their implementations
FUNCTION_MAP = {
    "search_restaurants": search_restaurants,
    "search_events": search_events,
    "search_attractions": search_attractions,
    "search_hotels": search_hotels,
    "get_city_info": get_city_info,
}


def execute_function(name: str, arguments: dict) -> dict:
    """
    Execute an external API function by name with the given arguments.
    This is called by the AI manager when OpenAI requests a function call.
    """
    func = FUNCTION_MAP.get(name)
    if not func:
        return {"error": f"Unknown function: {name}"}
    try:
        return func(**arguments)
    except TypeError as e:
        logger.error(f"Function call error for {name}: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in function {name}: {e}")
        return {"error": f"An error occurred: {str(e)}"}
