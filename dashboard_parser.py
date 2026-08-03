import os
import csv
import json

def load_json_species(json_path):
    """Loads unique bird species common names from the photos-ebird-mybird.json file."""
    if not os.path.exists(json_path):
        print(f"⚠️ Warning: JSON file not found at {json_path}")
        return set()
        
    try:
        with open(json_path, mode='r', encoding='utf-8') as f:
            data = json.load(f)
            # Find unique common names from the list of photos
            return {item["Common Name"].strip() for item in data if "Common Name" in item}
    except Exception as e:
        print(f"⚠️ Error loading JSON file: {e}")
        return set()

def load_valid_taxonomy_names(taxonomy_path):
    """Loads all valid English common names from the eBird taxonomy CSV file."""
    valid_names = set()
    if not os.path.exists(taxonomy_path):
        print(f"⚠️ Warning: Taxonomy file not found at {taxonomy_path}")
        return valid_names
        
    try:
        with open(taxonomy_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                com_name = row.get("PRIMARY_COM_NAME")
                if com_name:
                    valid_names.add(com_name.strip())
    except Exception as e:
        print(f"⚠️ Error parsing taxonomy CSV: {e}")
    return valid_names

def load_ebird_locations(csv_path):
    """Parses eBird CSV file and returns a dictionary of:
    (common_name_lower, date_str) -> set of locations (hotspots)"""
    ebird_locs = {}
    if not os.path.exists(csv_path):
        return ebird_locs
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Common Name")
                date = row.get("Date")
                loc = row.get("Location")
                if name and date and loc:
                    key = (name.lower().strip(), date.strip())
                    if key not in ebird_locs:
                        ebird_locs[key] = set()
                    ebird_locs[key].add(loc.strip())
    except Exception as e:
        print(f"⚠️ Error parsing eBird locations: {e}")
    return ebird_locs

def parse_ebird_sightings(csv_path):
    """Parses eBird CSV file and returns a set of unique common names seen."""
    if not os.path.exists(csv_path):
        print(f"⚠️ Warning: eBird CSV file not found at {csv_path}")
        return set()
        
    sightings = set()
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Common Name")
                if name:
                    sightings.add(name.strip())
    except Exception as e:
        print(f"⚠️ Error parsing eBird CSV: {e}")
    return sightings

def load_ebird_sightings_by_date(csv_path):
    """Parses eBird CSV file and returns a dictionary of:
    date_str (YYYY-MM-DD) -> set of species names logged
    """
    sightings = {}
    if not os.path.exists(csv_path):
        print(f"⚠️ Warning: eBird CSV file not found at {csv_path}")
        return sightings
        
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date = row.get("Date")
                name = row.get("Common Name")
                if date and name:
                    d = date.strip()
                    if d not in sightings:
                        sightings[d] = set()
                    sightings[d].add(name.strip())
    except Exception as e:
        print(f"⚠️ Error parsing eBird CSV: {e}")
    return sightings
