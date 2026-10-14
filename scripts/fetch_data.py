import csv
import os
import re
import json
import requests

RESOURCE_ID = "86e75d11-1c2c-4cd9-9b0d-9fccec302b30"
API_URL = "https://data.ontario.ca/api/3/action/datastore_search"
DATA_PATH = "data/ltb_orders.json"
CITIES_CSV_PATH = "data/canadacities.csv"
LIMIT = 10000

def load_ontario_cities():
    """Loads Ontario municipalities from cancities.csv into a lookup dictionary."""
    city_map = {}
    if os.path.exists(CITIES_CSV_PATH):
        with open(CITIES_CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 5:
                    city_name = row[0].strip()
                    province = row[2].strip().upper()
                    if province == "ON":
                        try:
                            lat = float(row[4])
                            lng = float(row[5])
                            city_map[city_name.upper()] = {
                                "name": city_name,
                                "lat": lat,
                                "lng": lng
                            }
                        except ValueError:
                            continue
    return city_map

# Load once globally
ONTARIO_CITIES = load_ontario_cities()
# Sort by length descending so longer city names match first (e.g., "North Bay" before "Bay")
SORTED_CITY_NAMES = sorted(ONTARIO_CITIES.keys(), key=len, reverse=True)

def match_city_from_csv(address_str):
    """Scans the address string for a valid Ontario city name from cancities.csv."""
    if not address_str or address_str == "N/A":
        return "Unknown", 0.0, 0.0
    
    addr_upper = address_str.upper()
    for city_key in SORTED_CITY_NAMES:
        pattern = r'\b' + re.escape(city_key) + r'\b'
        if re.search(pattern, addr_upper):
            match_data = ONTARIO_CITIES[city_key]
            return match_data["name"], match_data["lat"], match_data["lng"]
            
    return "Unknown", 0.0, 0.0

def fetch_all_ltb_records():
    all_records = []
    offset = 0
    print("Fetching current LTB dataset from Ontario Open Data...")
    while True:
        params = {"resource_id": RESOURCE_ID, "limit": LIMIT, "offset": offset}
        try:
            res = requests.get(API_URL, params=params, timeout=30).json()
            records = res.get("result", {}).get("records", [])
            if not records:
                break
            all_records.extend(records)
            offset += LIMIT
            if len(records) < LIMIT:
                break
        except Exception as e:
            print(f"Error fetching data: {e}")
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
    for r in records:
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
    return cleaned

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print(f"Loaded {len(ONTARIO_CITIES)} Ontario municipalities from cancities.csv.")

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

    # Upsert while preserving or updating coordinates from the CSV dictionary
    mapped_count = 0
    for item in clean_data:
        record_id = item["id"]
        # If city was matched successfully from CSV, use those coords; otherwise check existing map
        if item["city"] == "Unknown" and record_id in existing_map:
            item["lat"] = existing_map[record_id].get("lat", 0.0)
            item["lng"] = existing_map[record_id].get("lng", 0.0)
            item["city"] = existing_map[record_id].get("city", "Unknown")
        elif item["city"] != "Unknown":
            mapped_count += 1
        
        existing_map[record_id] = item

    combined_data = list(existing_map.values())
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    
    print(f"Sync complete! Mapped {mapped_count} records using cancities.csv. Total repository size: {len(combined_data)} orders.")