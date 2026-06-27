#!/usr/bin/python3

import sys
import os
import json
from lrcat_utils import open_catalog, BIRD_ROOT

def load_json_photos(json_path, species_name):
    """Loads matching photos from the JSON file for the given species (case-insensitive)."""
    if not os.path.exists(json_path):
        return []
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        matches = []
        name_lower = species_name.lower()
        for item in data:
            if item.get("Common Name", "").lower() == name_lower:
                matches.append(item)
        return matches
    except Exception as e:
        print(f"⚠️ Error loading JSON file: {e}")
        return []

def query_lr_photos(cursor, species_name):
    """Queries the Lightroom catalog for published photos of the species."""
    query = """
    SELECT DISTINCT
        f.baseName || '.' || f.extension AS Filename,
        i.captureTime AS CaptureTime,
        loc.value AS Location,
        city.value AS City,
        state.value AS State,
        country.value AS Country,
        parent_coll.name AS CollectionName,
        fold.pathFromRoot AS FolderPath
    FROM Adobe_images i
    JOIN AgLibraryFile f ON i.rootFile = f.id_local
    JOIN AgLibraryFolder fold ON f.folder = fold.id_local
    JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
    JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
    JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
        AND parent_coll.name LIKE '%SmugMug%'
    LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
    LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
    LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
    LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
    LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
    LEFT JOIN AgLibraryKeywordImage ki ON i.id_local = ki.image
    LEFT JOIN AgLibraryKeyword k ON ki.tag = k.id_local AND k.genealogy LIKE ?
    WHERE (lower(k.name) = lower(?) OR lower(i.colorLabels) = lower(?))
    ORDER BY CaptureTime ASC;
    """
    cursor.execute(query, (BIRD_ROOT, species_name, species_name))
    return cursor.fetchall()

def format_lr_location(loc, city, state, country):
    parts = []
    if loc and loc != 'No Location':
        parts.append(loc)
    if city and city != 'No City' and city != loc:
        parts.append(city)
    if state:
        parts.append(state)
    if country:
        parts.append(country)
    return ", ".join(parts) if parts else "N/A"

def format_json_location(loc, county, state_prov):
    parts = []
    if loc:
        parts.append(loc)
    if county:
        parts.append(f"{county} Co.")
    if state_prov:
        parts.append(state_prov)
    return ", ".join(parts) if parts else "N/A"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 species_details_report.py <species_common_name>")
        print("Example: python3 species_details_report.py \"Cactus Wren\"")
        sys.exit(1)
        
    species_name = sys.argv[1]
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "photos-ebird-mybird.json")
    
    # 1. Fetch from JSON
    json_photos = load_json_photos(json_path, species_name)
    
    # 2. Fetch from Lightroom
    try:
        with open_catalog() as cursor:
            lr_photos = query_lr_photos(cursor, species_name)
    except Exception as e:
        print(f"❌ Database error: {e}")
        lr_photos = []

    # 3. Print Report
    print("=" * 80)
    print(f"SPECIES DETAILS REPORT: {species_name}")
    print("=" * 80)
    
    # Section A: Lightroom Published Photos
    print(f"\nLightroom Catalog (Published to SmugMug) - Found {len(lr_photos)} photos:")
    print("-" * 80)
    if not lr_photos:
        print("  No published photos found in Lightroom catalog.")
    else:
        # Determine column widths
        fn_width = max(len("Filename"), max(len(p[0]) for p in lr_photos)) + 2
        dt_width = 15  # "Capture Date" + padding
        
        print(f"{'Filename':<{fn_width}}{'Capture Date':<{dt_width}}Location")
        print("-" * 80)
        for r in lr_photos:
            filename = r[0]
            date_str = r[1][:10] if r[1] else "N/A"
            location = format_lr_location(r[2], r[3], r[4], r[5])
            print(f"{filename:<{fn_width}}{date_str:<{dt_width}}{location}")
            
    # Section B: JSON published photos (Old website)
    print(f"\nLegacy JSON File (photos-ebird-mybird.json) - Found {len(json_photos)} photos:")
    print("-" * 80)
    if not json_photos:
        print("  No matching photos found in legacy JSON file.")
    else:
        # Determine column widths
        fn_width = max(len("Filename"), max(len(p.get("Filename", "")) for p in json_photos)) + 2
        dt_width = 15
        
        print(f"{'Filename':<{fn_width}}{'Date':<{dt_width}}Location")
        print("-" * 80)
        for item in json_photos:
            filename = item.get("Filename", "N/A")
            date_str = item.get("Date", "N/A")
            location = format_json_location(item.get("Location"), item.get("County"), item.get("State/Province"))
            print(f"{filename:<{fn_width}}{date_str:<{dt_width}}{location}")
            
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
