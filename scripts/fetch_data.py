import csv
import os
import re
import json
import requests

RESOURCE_ID = "86e75d11-1c2c-4cd9-9b0d-9fccec302b30"
API_URL = "https://data.ontario.ca/api/3/action/datastore_search"
DATA_PATH = "data/ltb_orders.json"
CITIES_CSV_PATH = "data/city_coordinates_cache.csv"
LIMIT = 10000

def load_ontario_cities():
    """Loads Ontario municipalities from city geocode cache into a lookup dictionary."""
    city_map = {}
    if os.path.exists(CITIES_CSV_PATH):
        with open(CITIES_CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                # Fixed: Use >= 3 because csv rows have 3 columns (city, latitude, longitude)
                if len(row) >= 2:
                    city_name = row[0].strip()
                    try:
                        lat = float(row[1])
                        lng = float(row[2])
                        if lat != 0.0 and lng != 0.0:
                            city_map[city_name.upper()] = {
                                "name": city_name,
                                "lat": lat,
                                "lng": lng
                            }
                    except ValueError:
                        continue    
    print(f"Loaded {len(city_map)} valid municipalities from cache.")
    return city_map

# Load once globally
ONTARIO_CITIES = load_ontario_cities()
# Sort by length descending so longer city names match first (e.g., "North Bay" before "Bay")
SORTED_CITY_NAMES = sorted(ONTARIO_CITIES.keys(), key=len, reverse=True)

def match_city_from_csv(address_str):
    """Extremely fast Ontario city matcher using C-speed string guards."""
    if not address_str or address_str == "N/A":
        return "Unknown", 0.0, 0.0
    
    addr_upper = address_str.upper()
    
    # 1. Fast path: Use C-speed 'in' check first. Only run regex if the substring matches.
    for city_key in SORTED_CITY_NAMES:
        if city_key in addr_upper:
            pattern = r'\b' + re.escape(city_key) + r'\b'
            if re.search(pattern, addr_upper):
                match_data = ONTARIO_CITIES[city_key]
                return match_data["name"], match_data["lat"], match_data["lng"]
            
    # 2. Fallback: Parse out comma-separated chunks (O(1) dictionary lookups)
    parts = [p.strip() for p in address_str.split(',')]
    if len(parts) >= 2:
        for part in reversed(parts[:-1]):
            clean_part = re.sub(r'\b(ON|Ontario|Canada|[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d)\b', '', part, flags=re.IGNORECASE).strip().upper()
            if clean_part in ONTARIO_CITIES:
                match_data = ONTARIO_CITIES[clean_part]
                return match_data["name"], match_data["lat"], match_data["lng"]

    return "Unknown", 0.0, 0.0

def fetch_all_ltb_records():
    all_records = []
    offset = 0
    print("Fetching current LTB dataset from Ontario Open Data...")
    
    # Government APIs often require a user-agent to prevent blocking default scripts
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LTBDataHub/1.0 (Open Source Civic Project)"
    }
    
    while True:
        params = {"resource_id": RESOURCE_ID, "limit": LIMIT, "offset": offset}
        try:
            # (connect timeout, read timeout) prevents silent infinite hanging
            res = requests.get(API_URL, params=params, headers=headers, timeout=(10, 45))
            res.raise_for_status()
            
            data = res.json()
            records = data.get("result", {}).get("records", [])
            if not records:
                break
                
            all_records.extend(records)
            print(f"Fetched {len(all_records)} records so far...")
            
            offset += LIMIT
            if len(records) < LIMIT:
                break
                
        except requests.exceptions.Timeout:
            print("[Error] Connection or read timed out while communicating with data.ontario.ca.")
            break
        except requests.exceptions.RequestException as e:
            print(f"[Error] Network request failed: {e}")
            break
        except Exception as e:
            print(f"[Error] Unexpected error parsing response: {e}")
            break
            
    return all_records

def extract_url(hyperlink_str):
    if not hyperlink_str:
        return "#"
    match = re.search(r'HYPERLINK\("([^"]+)"', str(hyperlink_str))
    if match:
        return match.group(1)
    return hyperlink_str if str(hyperlink_str).startswith("http") else "#"

def transform_records(records):
    cleaned = []
    total = len(records)
    print(f"Transforming and geocoding {total} records...")
    
    for i, r in enumerate(records):
        if i > 0 and i % 10000 == 0:
            print(f"Processed {i}/{total} records...")
            
        unit_addr = r.get("Rental Unit Address/Adresse du logement locatif")
        complex_addr = r.get("Complex Address/Adresse du complexe")
        address = unit_addr or complex_addr or "N/A"
        
        # Match directly against the CSV municipal database
        city, lat, lng = match_city_from_csv(address)

        tenant_name = (
            r.get("Tenant Name/Nom du locataire")
            or r.get("Former Tenant Name/Nom de l’ancien locataire")
            or r.get("Co-op Member Name/Nom du membre de la cooperative")
            or r.get("Sub-Tenant Name/Nom du sous-locataire")
            or r.get("Occupant Names/Nom de l’occupant")
            or "N/A"
        )

        landlord_name = (
            r.get("Landlord Name/Nom du locateur")
            or r.get("Co-op Name/Nom de la cooperative")
            or r.get("Landlord Agent Name/Nom du représentant du locateur")
            or "N/A"
        )

        doc_id = r.get("Document ID/Identifiant du document", f"id-{r.get('_id')}")

        cleaned.append({
            "id": doc_id,
            "fileNumber": r.get("File Number/Numéro de dossier", "N/A"),
            "address": address,
            "city": city,
            "appType": (
                r.get("Applications/Requêtes")
                or r.get("Application Type/Type de requête", "N/A")
            ),
            "orderDate": r.get("Order Date/Date de l’ordonnance", "N/A"),
            "landlordName": landlord_name,
            "tenantName": tenant_name,
            "pdfUrl": extract_url(
                r.get("ContentDownload URL/URL de téléchargement du contenu")
            ),
            "lat": lat,
            "lng": lng,
        })
        
    print("Transformation complete.")
    return cleaned

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)

    existing_map = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            try:
                old_data = json.load(f)
                existing_map = {item["id"]: item for item in old_data}
            except Exception as e:
                print(f"Warning: Could not parse existing JSON: {e}")

    raw_data = fetch_all_ltb_records()
    clean_data = transform_records(raw_data)

    # Upsert while preserving or updating coordinates
    mapped_count = 0
    preserved_count = 0
    for item in clean_data:
        record_id = item["id"]
        
        # If fresh parse failed to find a city, check if we already have it in the existing map
        if item["city"] == "Unknown" and record_id in existing_map:
            old_item = existing_map[record_id]
            if old_item.get("city", "Unknown") != "Unknown":
                item["city"] = old_item["city"]
                item["lat"] = old_item.get("lat", 0.0)
                item["lng"] = old_item.get("lng", 0.0)
                preserved_count += 1
        elif item["city"] != "Unknown":
            mapped_count += 1
        
        existing_map[record_id] = item

    combined_data = list(existing_map.values())
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    
    print(f"Sync complete! Mapped {mapped_count} via cache, preserved {preserved_count} from history. Total repository size: {len(combined_data)} orders.")