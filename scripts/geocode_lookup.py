#!/usr/bin/env python3
import os
import csv
import time
from pathlib import Path

# Optional: Try importing geopy for live fallback geocoding, 
# otherwise rely purely on offline lookup and caching.
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False

CACHE_FILE = Path("data/city_coordinates_cache.csv")
CITIES_REF = Path("data/canadacities.csv")

def load_cache():
    """Loads known coordinates cache into a dictionary: {city_lower: (lat, lon)}"""
    cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = row.get("city", "").strip().lower()
                if city:
                    cache[city] = (row.get("latitude"), row.get("longitude"))
    return cache

def save_cache(cache):
    """Saves the updated coordinate cache back to CSV."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "latitude", "longitude"])
        for city, coords in sorted(cache.items()):
            writer.writerow([city, coords[0], coords[1]])

def load_reference_cities():
    """Loads reference data from canadacities.csv if available."""
    ref_cache = {}
    if CITIES_REF.exists():
        with open(CITIES_REF, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Adjust column names depending on your canadacities.csv schema (e.g., 'city_ascii' or 'city', 'lat', 'lng')
                city = row.get("city", row.get("city_ascii", "")).strip().lower()
                lat = row.get("lat", row.get("latitude"))
                lng = row.get("lng", row.get("longitude"))
                if city and lat and lng:
                    ref_cache[city] = (lat, lng)
    return ref_cache

def resolve_unknown_cities(target_cities):
    """
    Takes a set or list of unknown city strings, checks the reference file, 
    queries Nominatim optionally with rate limits, and updates the cache.
    """
    cache = load_cache()
    ref_data = load_reference_cities()
    
    geolocator = Nominatim(user_agent="ltb_data_hub_geocoder", timeout=5) if HAS_GEOPY else None
    new_discoveries = 0

    for raw_city in target_cities:
        if not raw_city:
            continue
        clean_city = raw_city.strip().lower()
        
        # Skip if already cached
        if clean_city in cache:
            print(f'Already Cached {raw_city}')
            continue
            
        # 1. Check offline reference CSV first (Fast & reliable)
        if clean_city in ref_data:
            cache[clean_city] = ref_data[clean_city]
            print(f"[Cache Update] Found '{raw_city}' in reference dataset.")
            new_discoveries += 1
            continue
            
        # 2. Fall back to live geocoding if geopy is installed and non-blocking
        if geolocator:
            try:
                print(f"[Geocoding] Querying live coordinates for: {raw_city}, Ontario, Canada")
                location = geolocator.geocode(f"{raw_city}, Ontario, Canada")
                if location:
                    cache[clean_city] = (str(location.latitude), str(location.longitude))
                    print(f"  -> Resolved: {location.latitude}, {location.longitude}")
                    new_discoveries += 1
                else:
                    # Mark as empty/none so we don't spam queries repeatedly next run
                    cache[clean_city] = ("", "")
                time.sleep(1.1) # Respect Nominatim 1 request/sec usage policy
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"[Warning] Geocoding service timeout/error for {raw_city}: {e}")
                break # Stop live queries gracefully if network/API drops
            except Exception as ex:
                print(f"[Warning] Unexpected error geocoding {raw_city}: {ex}")

    if new_discoveries > 0:
        save_cache(cache)
        print(f"Successfully added {new_discoveries} new city coordinates to {CACHE_FILE}")
    else:
        print("No new unknown cities resolved during this run.")

import re

def extract_city_from_text(text):
    """
    Extracts the city name from full address strings such as:
    '306-4399 CONCORD AVE, BEAMSVILLE, ON L3J0M7' -> 'BEAMSVILLE'
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()
    if not text or len(text) < 2:
        return None

    # Option A: Handle comma-separated address structures
    parts = [p.strip() for p in text.split(',')]
    
    if len(parts) >= 2:
        # Check parts from right to left (since City is usually right before 'ON' or Postal Code)
        for part in reversed(parts[:-1]):  # Skip the very last part if it contains province/postal
            # Strip out Province codes, "Canada", postal codes, and pure numbers
            clean_part = re.sub(
                r'\b(ON|Ontario|Canada|[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d)\b', 
                '', 
                part, 
                flags=re.IGNORECASE
            ).strip()
            
            # Skip street suffixes or unit numbers if they accidentally slipped in
            if clean_part and not clean_part.isdigit() and len(clean_part) > 2:
                # If part isn't just a street prefix/number, return it
                return clean_part

    # Option B: Regex fallback for addresses without commas
    # Matches words preceding 'ON' or 'Ontario'
    match = re.search(r'([A-Za-z\s]+)\s+(?:ON|Ontario)\b', text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        # Grab the last word group if street details are attached
        words = candidate.split()
        if len(words) > 0:
            return words[-1]

    # Return raw text if it's already a short city name
    return text if not any(char.isdigit() for char in text) else None

if __name__ == "__main__":
    import json
    json_path = Path("data/ltb_orders.json")
    
    unknowns = set()
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                orders = json.load(f)
                print(f"Scanning {len(orders)} orders for city names...")
                for order in orders:
                    # Check multiple common keys where location data might live
                    raw_location = (
                        order.get("address")
                    )
                    
                    extracted = extract_city_from_text(raw_location)
                    if extracted:
                        unknowns.add(extracted)
                        
            print(f"Found {len(unknowns)} unique city/location strings to verify against cache/reference.")
        except Exception as e:
            print(f"Could not parse ltb_orders.json: {e}")
            
    resolve_unknown_cities(unknowns)