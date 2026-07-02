#!/usr/bin/python3

import os
import csv
import json
import sys
from datetime import datetime
from collections import defaultdict
from lrcat_utils import open_catalog, BIRD_ROOT

OUTPUT_HTML = "html/chronological_life_list.html"
EBIRD_CSV = "ebird.csv"

# --- LOCATION FORMATTER ---

def format_location(loc, city, state, country):
    """Formats Lightroom location components into a readable string."""
    parts = []
    if loc and loc != 'No Location':
        parts.append(loc)
    if city and city != 'No City' and city != loc:
        parts.append(city)
    if state:
        parts.append(state)
    if country:
        parts.append(country)
    return ", ".join(parts) if parts else "Unknown Location"

def make_relative_url(url):
    """Converts absolute SmugMug URLs into site-relative paths to optimize HTML size."""
    if not url:
        return ""
    for domain in ["https://billwalker.smugmug.com", "https://www.birdwalker.com"]:
        if url.startswith(domain):
            return url[len(domain):]
    return url

# --- EBIRD CSV PARSER ---

def parse_ebird_sightings(csv_path):
    """
    Parses eBird CSV file and returns a dictionary of:
    common_name -> { "date": YYYY-MM-DD, "location": location_name }
    containing the earliest sighting for each species.
    """
    if not os.path.exists(csv_path):
        print(f"❌ Error: eBird CSV file not found at: {csv_path}")
        sys.exit(1)
        
    print(f"Reading eBird sightings from {csv_path}...")
    species_first_sighting = {}
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Common Name")
            date_str = row.get("Date") # Format: YYYY-MM-DD
            location = row.get("Location", "Unknown Location")
            
            if not name or not date_str:
                continue
                
            name = name.strip()
            # Ignore general genus-level entries or hybrids like "duck sp." or "Rhea pennata/pennata"
            if " sp." in name.lower() or "/" in name or "hybrid" in name.lower():
                continue
                
            # Keep the earliest sighting date
            if name not in species_first_sighting:
                species_first_sighting[name] = {
                    "date": date_str,
                    "location": location
                }
            else:
                existing_date = species_first_sighting[name]["date"]
                if date_str < existing_date:
                    species_first_sighting[name] = {
                        "date": date_str,
                        "location": location
                    }
                    
    print(f"Parsed {len(species_first_sighting)} unique species from eBird.")
    return species_first_sighting

# --- LIGHTROOM DB QUERY ---

def fetch_earliest_published_photos(cursor):
    """
    Queries Lightroom copy for the single earliest published SmugMug photo 
    for every species, utilizing SQLite window functions.
    Returns: dict mapping common_name.lower() -> { date, location, url }
    """
    print("Querying Lightroom for earliest published SmugMug photos...")
    
    query = """
    WITH PublishedPhotos AS (
        SELECT 
            k.name AS SpeciesName,
            i.captureTime AS CaptureTime,
            loc.value AS Location,
            city.value AS City,
            state.value AS State,
            country.value AS Country,
            rp.url AS SmugMugUrl,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.url LIKE '%smugmug.com%'
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
        LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
        LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
        LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        SpeciesName,
        CaptureTime,
        Location, City, State, Country,
        SmugMugUrl,
        photo_count
    FROM PublishedPhotos
    WHERE rn = 1;
    """
    
    cursor.execute(query, (BIRD_ROOT,))
    rows = cursor.fetchall()
    
    published_photos = {}
    for r in rows:
        species_name = r[0]
        capture_time = r[1]
        loc = r[2]
        city = r[3]
        state = r[4]
        country = r[5]
        url = r[6]
        photo_count = r[7]
        
        formatted_loc = format_location(loc, city, state, country)
        date_only = capture_time[:10] if capture_time else "Unknown Date"
        
        published_photos[species_name.lower().strip()] = {
            "name": species_name.strip(),
            "date": date_only,
            "location": formatted_loc,
            "url": url,
            "photo_count": photo_count
        }
        
    print(f"Fetched published photo details for {len(published_photos)} species from Lightroom.")
    return published_photos

# --- HTML GENERATOR ---

def generate_html_content(chronological_data, total_seen_count):
    """Generates HTML content utilizing the shared base template and partials."""
    # 1. Load layout template and partials
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "templates", "base_layout.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(base_dir, "templates", "chronological_section.html"), "r", encoding="utf-8") as f:
        section_template = f.read()
    with open(os.path.join(base_dir, "templates", "chronological_row_photo.html"), "r", encoding="utf-8") as f:
        row_photo_template = f.read()
    with open(os.path.join(base_dir, "templates", "chronological_row_text.html"), "r", encoding="utf-8") as f:
        row_text_template = f.read()

    # 2. Build grid content
    content_sections = []
    sorted_years = sorted(chronological_data.keys(), reverse=True)
    
    for year in sorted_years:
        row_items = []
        # Sighting list is already sorted by date descending (latest first)
        for item in chronological_data[year]:
            species_name = item["name"]
            ebird_date = item["ebird_date"]
            ebird_loc = item["ebird_location"]
            photo = item["photo"]
            
            if photo:
                photo_url = make_relative_url(photo.get("url"))
                
                # Check link type
                if photo.get("photo_count", 0) == 1 and photo_url:
                    species_link = photo_url
                else:
                    url_name = species_name.replace(" ", "+")
                    species_link = f"/search/?q={url_name}"
                    
                photo_link = make_relative_url(photo["url"])
                row_item = (row_photo_template
                            .replace("{{ DATE }}", ebird_date)
                            .replace("{{ SPECIES_LINK }}", species_link)
                            .replace("{{ SPECIES_NAME }}", species_name)
                            .replace("{{ SIGHTING_LOCATION }}", ebird_loc)
                            .replace("{{ PHOTO_LINK }}", photo_link)
                            .replace("{{ PHOTO_DATE }}", photo["date"])
                            .replace("{{ PHOTO_LOCATION }}", photo["location"]))
            else:
                row_item = (row_text_template
                            .replace("{{ DATE }}", ebird_date)
                            .replace("{{ SPECIES_NAME }}", species_name)
                            .replace("{{ SIGHTING_LOCATION }}", ebird_loc))
            row_items.append("            " + row_item.strip())
            
        # Combine section template
        section_html = (section_template
                        .replace("{{ YEAR }}", year)
                        .replace("{{ ROWS }}", "\n".join(row_items)))
        content_sections.append(section_html)
        
    content = "\n".join(content_sections)

    # Calculate global totals
    total_photographed = sum(
        1 for species_list in chronological_data.values() 
        for s in species_list if s["photo"]
    )

    # 3. Page-specific CSS rules
    styles = """
        .year-section { margin-bottom: 50px; }
        .year-heading { 
            font-size: 1.8em; 
            font-weight: bold; 
            margin-top: 40px; 
            margin-bottom: 20px; 
            border-bottom: 2px solid #ff9f43;
            padding-bottom: 8px;
            color: #fff;
        }
        .timeline-table {
            display: grid;
            grid-template-columns: 120px 1.2fr 1.5fr 1.8fr;
            gap: 1px;
            background-color: #222;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
        }
        .table-header {
            background-color: #1a1a1a;
            color: #fff;
            font-weight: bold;
            padding: 14px 18px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border-bottom: 2px solid #333;
        }
        .table-row {
            display: contents; /* Allows grid alignment */
        }
        .table-cell {
            background-color: #131313;
            padding: 14px 18px;
            font-size: 0.95em;
            align-self: center;
            border-bottom: 1px solid #1a1a1a;
            line-height: 1.4;
        }
        .table-row:hover .table-cell {
            background-color: #1d1d1d;
        }
        .date-cell {
            font-family: monospace;
            font-size: 1.05em;
            color: #ff9f43; /* Warm orange to emphasize dates */
            font-weight: bold;
        }
        .species-cell {
            font-weight: 500;
        }
        .species-link { color: #4db8ff; text-decoration: none; }
        .species-link:hover { text-decoration: underline; }
        .species-text { color: #aaa; font-weight: normal; }
        
        .photo-cell {
            color: #ccc;
        }
        .photo-link {
            color: #00fa9a;
            text-decoration: none;
            font-weight: 500;
        }
        .photo-link:hover {
            text-decoration: underline;
        }
        .location-cell {
            color: #ccc;
        }
    """

    # 4. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Chronological Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Chronological Photo Life List")
    html = html.replace("{{ STATS_HEADER }}", f"Total eBird species: <strong>{total_seen_count}</strong> | Photographed & Published: <strong>{total_photographed}</strong>")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html

# --- MAIN ENGINE ---

def main():
    # Ensure html output directory exists
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    # Check command-line flags
    show_all = "--all" in sys.argv or "--show-all" in sys.argv
    if show_all:
        print("Running in FULL LIST mode (includes unphotographed eBird sightings).")
    else:
        print("Running in PHOTOGRAPHED-ONLY mode (default, optimized for SmugMug HTML limits).")
        print("To generate the full list, run: python3 chronological-lifelist-custom-page.py --all")
    
    # 1. Parse eBird CSV
    ebird_sightings = parse_ebird_sightings(EBIRD_CSV)
    
    # 2. Query Lightroom for published photos
    with open_catalog() as cursor:
        published_photos = fetch_earliest_published_photos(cursor)
        
    # 3. Merge data and organize by Year -> Sighting list
    chronological_data = defaultdict(list)
    
    # Track which published species were matched with eBird
    matched_photo_species = set()
    
    # Loop over all eBird sightings
    for name, sighting in ebird_sightings.items():
        date_str = sighting["date"]
        loc = sighting["location"]
        
        # Try to match published photo details (case-insensitive)
        photo_info = published_photos.get(name.lower().strip())
        if photo_info:
            matched_photo_species.add(name.lower().strip())
        elif not show_all:
            # If we are only showing photographed species, and this has no photo, skip it
            continue
            
        # Parse year for grouping
        try:
            year = date_str.split("-")[0]
        except Exception:
            year = "Unknown"
            
        chronological_data[year].append({
            "name": name,
            "ebird_date": date_str,
            "ebird_location": loc,
            "photo": photo_info
        })
        
    # Loop over published species that were NOT in eBird
    # We add them using their earliest photo date as their life date!
    unmatched_count = 0
    for name_lower, photo_info in published_photos.items():
        if name_lower not in matched_photo_species:
            unmatched_count += 1
            orig_name = photo_info["name"]
            date_str = photo_info["date"]
            loc = photo_info["location"]
            
            # Parse year for grouping
            try:
                year = date_str.split("-")[0]
            except Exception:
                year = "Unknown"
                
            chronological_data[year].append({
                "name": orig_name,
                "ebird_date": date_str,
                "ebird_location": f"Lightroom Capture ({loc})",
                "photo": photo_info
            })
            
    print(f"Matched {len(matched_photo_species)} published species with eBird.")
    print(f"Added {unmatched_count} Lightroom-only published species using their capture date.")
        
    # Sort sightings within each year chronologically descending (latest seen first)
    for year in chronological_data:
        chronological_data[year].sort(key=lambda x: (x["ebird_date"], x["name"]), reverse=True)
        
    # 4. Generate HTML content
    print("Generating HTML content...")
    total_seen_count = len(ebird_sightings) + unmatched_count
    html_content = generate_html_content(chronological_data, total_seen_count)
    
    # 5. Write to output file
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\n✅ Success! Chronological Life List generated successfully:")
    print(f"   Destination: [html/chronological_life_list.html](file://{os.path.abspath(OUTPUT_HTML)})")

if __name__ == "__main__":
    main()
