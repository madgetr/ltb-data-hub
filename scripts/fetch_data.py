import json
import os
import re
import time
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from geopy.geocoders import Nominatim
import requests

RESOURCE_ID = "86e75d11-1c2c-4cd9-9b0d-9fccec302b30"
API_URL = "https://data.ontario.ca/api/3/action/datastore_search"
DATA_PATH = "data/ltb_orders.json"
LIMIT = 10000

# Instantiate geolocator globally right here
geolocator = Nominatim(user_agent="ltb_spatial_intelligence_hub_v1")

def extract_url(hyperlink_str):
  if not hyperlink_str:
    return "#"
  match = re.search(r'HYPERLINK\("([^"]+)"', str(hyperlink_str))
  if match:
    return match.group(1)
  return hyperlink_str if str(hyperlink_str).startswith("http") else "#"


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

def geocode_address(address_str):
  if not address_str or address_str == "N/A":
    return None, None

  # Clean and format address for Ontario geocoding
  query = address_str
  if "ONTARIO" not in query.upper() and "ON" not in query.upper():
    query += ", Ontario, Canada"
  elif "CANADA" not in query.upper():
    query += ", Canada"

  try:
    location = geolocator.geocode(query, timeout=10)
    if location:
      return location.latitude, location.longitude
  except (GeocoderTimedOut, GeocoderServiceError):
    print(f"Geocoding timeout for address: {address_str}")
  except Exception as e:
    print(f"Geocoding error for {address_str}: {e}")

  return None, None


def transform_records(records):
  cleaned = []
  for r in records:
    unit_addr = r.get("Rental Unit Address/Adresse du logement locatif")
    complex_addr = r.get("Complex Address/Adresse du complexe")
    address = unit_addr or complex_addr or "N/A"

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
        "appType": (
            r.get("Applications/Requêtes")
            or r.get("Application Type/Type de requête", "N/A")
        ),
        "orderDate": r.get("Order Date/Date de l’ordonnance", "N/A"),
        "landlordName": landlord_name,
        "tenantName": tenant_name,
        "pdfUrl": extract_url(
            r.get("ContentDownload URL/URL de téléchargement du contenu"
            )
        ),
        "lat": None,  # Populated incrementally
        "lng": None,  # Populated incrementally
    })
  return cleaned

if __name__ == "__main__":
  os.makedirs("data", exist_ok=True)

  # 1. Load existing records (to preserve existing lat/lng coordinates)
  existing_map = {}
  if os.path.exists(DATA_PATH):
    with open(DATA_PATH, "r", encoding="utf-8") as f:
      try:
        old_data = json.load(f)
        existing_map = {item["id"]: item for item in old_data}
        print(f"Loaded {len(existing_map)} existing records from storage.")
      except Exception as e:
        print(f"Warning: Could not parse existing JSON file: {e}")

  # 2. Fetch fresh batch from Ontario Open Data
  raw_data = fetch_all_ltb_records()
  clean_data = transform_records(raw_data)

  # 3. Upsert records while preserving previously computed lat/lng values
  added_count = 0
  for item in clean_data:
    record_id = item["id"]
    if record_id in existing_map:
      # Keep existing lat/lng if already geocoded
      item["lat"] = existing_map[record_id].get("lat")
      item["lng"] = existing_map[record_id].get("lng")
    else:
      added_count += 1
    existing_map[record_id] = item

  # 4. Incremental Batch Geocoding (Limit to 300 per run to respect API rates & timeouts)
  MAX_GEOCODE_PER_RUN = 300
  geocoded_count = 0

  print(
      "Checking for records requiring geocoding (Max"
      f" {MAX_GEOCODE_PER_RUN} batch)..."
  )
  for record_id, item in existing_map.items():
    if (
        item["lat"] is None
        and item["lng"] is None
        and item["address"] != "N/A"
    ):
      if geocoded_count >= MAX_GEOCODE_PER_RUN:
        print(
            "Reached batch geocoding limit for this run. Remaining addresses"
            " will be processed next time."
        )
        break

      lat, lng = geocode_address(item["address"])
      if lat and lng:
        item["lat"] = lat
        item["lng"] = lng
        geocoded_count += 1
        print(
            f"[{geocoded_count}/{MAX_GEOCODE_PER_RUN}] Geocoded:"
            f" {item['address']} -> ({lat}, {lng})"
        )
      else:
        # Mark as checked (using 0,0 or keeping None) so we don't retry failed addresses endlessly
        item["lat"] = 0.0
        item["lng"] = 0.0

      # Mandatory 1-second pause to comply with Nominatim OpenStreetMap usage policy
      time.sleep(1)

  combined_data = list(existing_map.values())

  # 5. Save cumulative dataset back out
  with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(combined_data, f, indent=2, ensure_ascii=False)

  print(
      f"Sync complete! Added {added_count} new records. Newly geocoded:"
      f" {geocoded_count}. Total repository size: {len(combined_data)} orders."
  )