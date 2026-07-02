#!/usr/bin/python3

import sys
import os
import json
import subprocess
from lrcat_utils import open_catalog, BIRD_ROOT, format_location

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
        fold.pathFromRoot AS FolderPath,
        rf.absolutePath AS RootPath
    FROM Adobe_images i
    JOIN AgLibraryFile f ON i.rootFile = f.id_local
    JOIN AgLibraryFolder fold ON f.folder = fold.id_local
    JOIN AgLibraryRootFolder rf ON fold.rootFolder = rf.id_local
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
    # Remove --reveal argument if present to parse the species name easily
    args = sys.argv[1:]
    reveal_idx = None
    if "--reveal" in args:
        try:
            idx_pos = args.index("--reveal")
            if idx_pos + 1 < len(args):
                reveal_idx = int(args[idx_pos + 1])
                # Remove --reveal and the index from args list
                args.pop(idx_pos + 1)
                args.pop(idx_pos)
            else:
                print("❌ Error: Please specify a valid integer index for --reveal (e.g. --reveal 1)")
                sys.exit(1)
        except ValueError:
            print("❌ Error: Please specify a valid integer index for --reveal (e.g. --reveal 1)")
            sys.exit(1)

    if not args:
        print("Usage: python3 species_details_report.py <species_common_name> [--reveal <index>]")
        print("Example: python3 species_details_report.py \"Cactus Wren\"")
        print("         python3 species_details_report.py \"Cactus Wren\" --reveal 1")
        sys.exit(1)
        
    species_name = args[0]
    
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

    # 3. Handle Finder Reveal if requested
    if reveal_idx is not None:
        total_lr = len(lr_photos)
        total_json = len(json_photos)
        
        if 1 <= reveal_idx <= total_lr:
            # Reveal Lightroom photo
            photo = lr_photos[reveal_idx - 1]
            filename = photo[0]
            root_path = photo[8]
            folder_path = photo[7]
            abs_path = os.path.join(root_path, folder_path, filename)
            
            if not os.path.exists(abs_path):
                print(f"❌ Error: Cannot reveal in Finder. The file path does not exist locally.")
                print(f"   (Please check if the external volume '{root_path.split('/')[2]}' is mounted: {root_path})")
            else:
                print(f"🔍 Attempting to reveal in Finder: {abs_path}")
                try:
                    subprocess.run(["open", "-R", abs_path], check=True)
                    print("✅ Finder open command executed successfully.")
                except Exception as e:
                    print(f"❌ Error revealing file: {e}")
        elif total_lr < reveal_idx <= (total_lr + total_json):
            # Reveal JSON photo (cannot be revealed)
            print(f"❌ Error: Index {reveal_idx} is a legacy JSON photo from the old website. Local file paths are not available.")
        else:
            print(f"❌ Error: Invalid index '{reveal_idx}'. Choose a Lightroom photo index (1 to {total_lr}).")
        
        print() # Add spacer

    # 4. Print Report
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
        
        print(f"{'Idx':<5}{'Filename':<{fn_width}}{'Capture Date':<{dt_width}}Location")
        print("-" * 80)
        for i, r in enumerate(lr_photos):
            idx_str = f"[{i + 1}]"
            filename = r[0]
            date_str = r[1][:10] if r[1] else "N/A"
            location = format_location(r[2], r[3], r[4], r[5])
            print(f"{idx_str:<5}{filename:<{fn_width}}{date_str:<{dt_width}}{location}")
            
    # Section B: JSON published photos (Old website)
    print(f"\nLegacy JSON File (photos-ebird-mybird.json) - Found {len(json_photos)} photos:")
    print("-" * 80)
    if not json_photos:
        print("  No matching photos found in legacy JSON file.")
    else:
        # Determine column widths
        fn_width = max(len("Filename"), max(len(p.get("Filename", "")) for p in json_photos)) + 2
        dt_width = 15
        
        print(f"{'Idx':<5}{'Filename':<{fn_width}}{'Date':<{dt_width}}Location")
        print("-" * 80)
        for i, item in enumerate(json_photos):
            idx_str = f"[{len(lr_photos) + i + 1}]"
            filename = item.get("Filename", "N/A")
            date_str = item.get("Date", "N/A")
            location = format_json_location(item.get("Location"), item.get("County"), item.get("State/Province"))
            print(f"{idx_str:<5}{filename:<{fn_width}}{date_str:<{dt_width}}{location}")
            
    print("\n" + "=" * 80)
    if lr_photos:
        print(f"💡 Tip: To reveal a Lightroom photo in Finder, run: \n   python3 species_details_report.py \"{species_name}\" --reveal 1")
    print("💡 Tip: To locate a photo inside Lightroom, copy its filename (e.g. 7V5Z1564) and search")
    print("   for it using the Text filter (key '\\') in the Library module.")
    print("=" * 80)

if __name__ == "__main__":
    main()
