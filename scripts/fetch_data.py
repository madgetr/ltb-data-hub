import json
import os
import re
import requests

RESOURCE_ID = "86e75d11-1c2c-4cd9-9b0d-9fccec302b30"
API_URL = "https://data.ontario.ca/api/3/action/datastore_search"
DATA_PATH = "data/ltb_orders.json"
LIMIT = 10000

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
            r.get("ContentDownload URL/URL de téléchargement du contenu")
        ),
    })
  return cleaned


if __name__ == "__main__":
  os.makedirs("data", exist_ok=True)

  # 1. Load existing records if they exist
  existing_map = {}
  if os.path.exists(DATA_PATH):
    with open(DATA_PATH, "r", encoding="utf-8") as f:
      try:
        old_data = json.load(f)
        existing_map = {item["id"]: item for item in old_data}
        print(f"Loaded {len(existing_map)} existing historical records.")
      except Exception as e:
        print(f"Warning: Could not parse existing JSON file: {e}")

  # 2. Fetch fresh batch
  raw_data = fetch_all_ltb_records()
  clean_data = transform_records(raw_data)

  # 3. Upsert / Merge new records into the map
  added_count = 0
  for item in clean_data:
    record_id = item["id"]
    if record_id not in existing_map:
      added_count += 1
    existing_map[record_id] = item  # Overwrite with latest if updated

  combined_data = list(existing_map.values())

  # 4. Save cumulative dataset back out
  with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(combined_data, f, indent=2, ensure_ascii=False)

  print(
      f"Sync complete! Added {added_count} new records. Total repository size:"
      f" {len(combined_data)} orders."
  )