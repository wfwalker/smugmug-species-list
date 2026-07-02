#!/usr/bin/python3

import os
import csv
import sys
from lrcat_utils import open_catalog, BIRD_ROOT

REPORTS_DIR = "reports"
OUTPUT_CSV = os.path.join(REPORTS_DIR, "location_todo_list.csv")
OUTPUT_HTML = os.path.join(REPORTS_DIR, "location_todo_list.html")
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

def load_ebird_locations(csv_path):
    """
    Parses eBird CSV file and returns a dictionary of:
    (common_name_lower, date_str) -> set of locations (hotspots)
    """
    ebird_locs = {}
    if not os.path.exists(csv_path):
        print(f"⚠️ Warning: eBird CSV file not found at {csv_path}")
        return ebird_locs
        
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
        print(f"⚠️ Error parsing eBird CSV: {e}")
    return ebird_locs

def fetch_published_photos_without_location(cursor):
    """Queries Lightroom for all published photos missing location details."""
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
    )
    ORDER BY SpeciesName, CaptureTime;
    """
    cursor.execute(query, (BIRD_ROOT,))
    return cursor.fetchall()

def save_to_csv(output_path, matches):
    """Writes matching entries to a CSV file."""
    headers = ["Species", "Filename", "Date", "Suggested Location", "Lightroom Location Reference"]
    with open(output_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for m in matches:
            writer.writerow([
                m["species"],
                m["filename"],
                m["date"],
                m["suggested_location"],
                m["lr_path"]
            ])

def save_to_html(output_path, matches, total_audited):
    """Writes the dashboard-style HTML todo list with quick clipboard copy buttons."""
    base_dir = os.path.dirname(__file__)
    
    # 1. Load layout template
    layout_path = os.path.join(base_dir, "templates", "base_layout.html")
    with open(layout_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    # 2. Load partials
    with open(os.path.join(base_dir, "templates", "todo_section.html"), "r") as f:
        section_template = f.read()
    with open(os.path.join(base_dir, "templates", "todo_row.html"), "r") as f:
        row_template = f.read()

    # 3. Build Rows
    row_html_list = []
    for m in matches:
        # Build suggested location block with individual option rows
        hotspots = m.get("hotspots", [m["suggested_location"]])
        color_class = "single-hotspot" if len(hotspots) == 1 else "multi-hotspots"
        
        loc_blocks = []
        for loc in hotspots:
            escaped_loc = loc.replace("'", "\\'")
            loc_blocks.append(
                f'<div class="hotspot-option">'
                f'<span class="hotspot-name {color_class}">{loc}</span>'
                f'<button class="copy-btn" onclick="copyToClipboard(\'{escaped_loc}\', this)">Copy</button>'
                f'</div>'
            )
        suggested_block = "\n".join(loc_blocks)
        
        row_html = (row_template
                    .replace("{{ SPECIES }}", m["species"])
                    .replace("{{ FILENAME }}", m["filename"])
                    .replace("{{ DATE }}", m["date"])
                    .replace("{{ SUGGESTED_LOCATION_BLOCK }}", suggested_block)
                    .replace("{{ FULL_PATH }}", m["lr_path"])
                    .replace("{{ SHORT_PATH }}", m["lr_path"]))
        row_html_list.append("        " + row_html.strip())

    # 4. Build Table Section
    section_title = f"Location Recovery Tasks ({len(matches)} matches)"
    section_desc = f"Out of {total_audited} published photos audited, eBird sightings from the same capture date were found for {len(matches)} photos. Use the Copy button to quickly capture the hotspot name for copy-pasting into Lightroom."
    
    table_content = (section_template
                     .replace("{{ SECTION_TITLE }}", section_title)
                     .replace("{{ SECTION_DESCRIPTION }}", section_desc)
                     .replace("{{ ROWS }}", "\n".join(row_html_list)))

    # 5. Client-Side Clipboard Copy Script
    clipboard_script = """
    <script>
    function copyToClipboard(text, btn) {
        navigator.clipboard.writeText(text).then(function() {
            var oldText = btn.innerText;
            btn.innerText = "Copied!";
            btn.style.backgroundColor = "#2ed573";
            btn.style.borderColor = "#2ed573";
            setTimeout(function() {
                btn.innerText = oldText;
                btn.style.backgroundColor = "";
                btn.style.borderColor = "";
            }, 1200);
        }).catch(function(err) {
            console.error("Failed to copy text: ", err);
        });
    }
    </script>
    """
    
    content_html = table_content + "\n" + clipboard_script

    # 6. Page CSS rules
    styles = """
        .todo-table {
            width: 100%;
            border-collapse: collapse;
            background-color: #131313;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
            margin-top: 20px;
        }
        .todo-table th {
            background-color: #1a1a1a;
            color: #fff;
            font-weight: bold;
            padding: 12px 16px;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border-bottom: 2px solid #333;
            text-align: left;
        }
        .todo-table td {
            padding: 12px 16px;
            font-size: 0.9em;
            border-bottom: 1px solid #1a1a1a;
            vertical-align: top;
        }
        .todo-table tr:hover td {
            background-color: #1d1d1d;
        }
        .species-cell {
            font-weight: bold;
            color: #eee;
        }
        .hotspot-cell {
            padding: 8px 16px !important;
        }
        .hotspot-option {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 6px;
            padding-bottom: 6px;
            border-bottom: 1px dashed #222;
        }
        .hotspot-option:last-child {
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }
        .hotspot-name {
            font-weight: bold;
        }
        .single-hotspot {
            color: #2ed573; /* Green */
        }
        .multi-hotspots {
            color: #ffd32a; /* Yellow */
        }
        .copy-btn {
            background-color: #222;
            color: #fff;
            border: 1px solid #555;
            padding: 4px 8px;
            font-size: 0.8em;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .copy-btn:hover {
            background-color: #333;
            border-color: #888;
        }
        .path-cell {
            color: #888;
            font-size: 0.85em;
        }
        .section-heading {
            font-size: 1.6em;
            font-weight: bold;
            color: #fff;
            margin-bottom: 10px;
            border-bottom: 2px solid #00fa9a;
            padding-bottom: 8px;
        }
        .section-desc {
            color: #aaa;
            margin-bottom: 20px;
            font-size: 0.95em;
        }
    """

    # 7. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Lightroom Location Recovery To-Do List")
    html = html.replace("{{ HEADER_TITLE }}", "Lightroom Location Recovery To-Do List")
    html = html.replace("{{ STATS_HEADER }}", "")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    print("Loading eBird locations from ebird.csv...")
    ebird_locs = load_ebird_locations(EBIRD_CSV)
    print(f"Loaded {len(ebird_locs)} species-date sighting keys from eBird.")

    print("Connecting to Lightroom Catalog to fetch published photos without location...")
    with open_catalog() as cursor:
        photos = fetch_published_photos_without_location(cursor)
        
    print(f"Found {len(photos)} published photos with missing location metadata.")

    print("Matching photos to eBird sightings by date...")
    matches = []
    
    for r in photos:
        species_name = r[0]
        filename = r[1]
        collection = r[2]
        capture_time = r[3]
        folder_path = r[4]
        
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
            lr_ref = f"Coll: {collection} | Folder: {folder_path}"
            
            matches.append({
                "species": species_name,
                "filename": filename,
                "date": capture_date,
                "suggested_location": suggested_loc,
                "hotspots": sorted(matched_hotspots),
                "lr_path": lr_ref
            })

    # Sort matches by Species Name, Date
    matches.sort(key=lambda x: (x["species"], x["date"]))

    print(f"Matched {len(matches)} photos to eBird sightings.")

    print("Generating reports...")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    save_to_csv(OUTPUT_CSV, matches)
    save_to_html(OUTPUT_HTML, matches, len(photos))

    print(f"✅ Success! Location recovery lists generated:")
    print(f"   • CSV:  {OUTPUT_CSV}")
    print(f"   • HTML: {OUTPUT_HTML}")
    
if __name__ == "__main__":
    main()
