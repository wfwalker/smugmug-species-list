#!/usr/bin/python3

import os
import csv
import sys
import shutil
import subprocess
from collections import defaultdict
from lrcat_utils import open_catalog, BIRD_ROOT

EBIRD_CSV = "ebird.csv"

# Taxonomy mappings for common name discrepancies between Lightroom and eBird
SYNONYMS = {
    "northern yellow warbler": "yellow warbler",
    "hudsonian whimbrel": "whimbrel",
    "american gannet": "northern gannet",
    "common house-martin": "western house-martin",
    "gray-breasted wood-wren": "grey-breasted wood-wren",
    "american barn owl": "barn owl",
    "northern house wren": "house wren",
    "western whimbrel": "whimbrel",
    "white-headed stilt": "pied stilt",
    "american black oystercatcher": "black oystercatcher",
}

def check_exiftool():
    """Checks if exiftool is installed in the system path."""
    if not shutil.which("exiftool"):
        print("❌ Error: 'exiftool' is not installed or not in your PATH.")
        print("Please install it by running: brew install exiftool")
        sys.exit(1)

def load_ebird_locations(csv_path):
    """Parses eBird CSV file and returns a dictionary of sightings."""
    ebird_locs = {}
    if not os.path.exists(csv_path):
        print(f"❌ Error: eBird CSV file not found at {csv_path}")
        sys.exit(1)
        
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
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
        print(f"❌ Error parsing eBird CSV: {e}")
        sys.exit(1)
    return ebird_locs

EXCLUDED_TAGS = ["People", "Wildlife"]

def fetch_published_photos_without_location(cursor):
    """Queries Lightroom for all published photos missing location details."""
    excluded_tags_sql = ", ".join(f"'{tag}'" for tag in EXCLUDED_TAGS)
    exclude_clause = f"""
      AND i.id_local NOT IN (
          SELECT ki_ex.image 
          FROM AgLibraryKeywordImage ki_ex
          JOIN AgLibraryKeyword k_ex ON ki_ex.tag = k_ex.id_local
          WHERE k_ex.name IN ({excluded_tags_sql})
      )
    """

    query = """
    SELECT DISTINCT
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime,
        FolderPath,
        RootPath
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime,
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
        WHERE i.colorLabels != '' 
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
          AND (iptc.locationRef IS NULL OR iptc.locationRef = '')
          AND (iptc.cityRef IS NULL OR iptc.cityRef = '')
          AND (iptc.stateRef IS NULL OR iptc.stateRef = '')
          AND (iptc.countryRef IS NULL OR iptc.countryRef = '')
          {exclude_clause}
        
        UNION ALL
        
        SELECT 
            k.name AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime,
            fold.pathFromRoot AS FolderPath,
            rf.absolutePath AS RootPath
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        JOIN AgLibraryFolder fold ON f.folder = fold.id_local
        JOIN AgLibraryRootFolder rf ON fold.rootFolder = rf.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        WHERE k.genealogy LIKE ?
          AND (iptc.locationRef IS NULL OR iptc.locationRef = '')
          AND (iptc.cityRef IS NULL OR iptc.cityRef = '')
          AND (iptc.stateRef IS NULL OR iptc.stateRef = '')
          AND (iptc.countryRef IS NULL OR iptc.countryRef = '')
          {exclude_clause}
    )
    ORDER BY SpeciesName, CaptureTime;
    """.replace("{exclude_clause}", exclude_clause)
    
    cursor.execute(query, (BIRD_ROOT,))
    return cursor.fetchall()

def write_location_metadata(file_path, location):
    """Executes exiftool to write sub-location metadata to the photo file."""
    cmd = [
        "exiftool",
        "-overwrite_original",
        f"-iptc:sub-location={location}",
        f"-xmp:location={location}",
        file_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to write to {os.path.basename(file_path)}: {e.stderr.decode().strip()}")
        return False

def main():
    check_exiftool()
    
    print("Loading eBird locations from ebird.csv...")
    ebird_locs = load_ebird_locations(EBIRD_CSV)

    print("Connecting to Lightroom Catalog to fetch published photos without location...")
    with open_catalog() as cursor:
        photos = fetch_published_photos_without_location(cursor)
        
    print(f"Found {len(photos)} published photos with missing location metadata.")

    # Match and group tasks by Lightroom folder for convenient selection
    matched_tasks = []
    folder_groups = defaultdict(list)
    missing_files_count = 0
    
    for r in photos:
        species_name = r[0]
        filename = r[1]
        collection = r[2]
        capture_time = r[3]
        folder_path = r[4]
        root_path = r[5]
        
        if not capture_time:
            continue
            
        capture_date = capture_time[:10]
        name_lower = species_name.lower().strip()
        
        # Test candidate names (direct + synonyms)
        candidates = [name_lower]
        if name_lower in SYNONYMS:
            candidates.append(SYNONYMS[name_lower])
            
        matched_hotspots = None
        for cand in candidates:
            key = (cand, capture_date)
            if key in ebird_locs:
                matched_hotspots = ebird_locs[key]
                break
                
        if matched_hotspots:
            # Combine hotspots into a single string (separated by / if multiple)
            suggested_loc = " / ".join(sorted(matched_hotspots))
            abs_path = os.path.join(root_path, folder_path, filename)
            
            if not os.path.exists(abs_path):
                missing_files_count += 1
                continue
                
            matched_tasks.append((abs_path, suggested_loc, folder_path, filename))
            folder_groups[folder_path].append((filename, suggested_loc))

    print(f"Matched {len(matched_tasks)} photos currently present on disk. (Skipped {missing_files_count} unmounted/missing files).")
    
    if not matched_tasks:
        print("No updates needed!")
        return

    print(f"\nProceeding to write location metadata to {len(matched_tasks)} files...")
    success_count = 0
    for idx, (abs_path, location, _, filename) in enumerate(matched_tasks):
        print(f" [{idx + 1}/{len(matched_tasks)}] Writing '{location}' to {filename}...", end="", flush=True)
        if write_location_metadata(abs_path, location):
            print(" ✅ Done.")
            success_count += 1
        else:
            print(" ❌ Failed.")

    print(f"\n==============================================================")
    print(f"🎉 Metadata Update Complete! Successfully updated {success_count} files.")
    print(f"==============================================================")
    print(f"\n👉 NEXT STEPS FOR LIGHTROOM:")
    print(f"1. Open Lightroom Classic.")
    print(f"2. For each of the folders listed below:")
    print(f"   a. Click the folder name in Lightroom's Library Catalog panel.")
    print(f"   b. Select the updated photos.")
    print(f"   c. Select 'Metadata' ➔ 'Read Metadata from Files' from the top menu bar.")
    print(f"\nFolders to update:")
    for folder, files in sorted(folder_groups.items()):
        print(f" • 📁 {folder} (contains {len(files)} updated photo{'s' if len(files) > 1 else ''}):")
        for f, loc in files:
            print(f"     - {f} ➔ '{loc}'")
            
if __name__ == "__main__":
    main()
