#!/usr/bin/python3

import os
import csv
import sys
from lrcat_utils import open_catalog

REPORTS_DIR = "reports"
OUTPUT_CSV = os.path.join(REPORTS_DIR, "taxonomy_migration_audit.csv")
OUTPUT_HTML = os.path.join(REPORTS_DIR, "taxonomy_migration_audit.html")
EBIRD_CSV = "ebird.csv"

# 2024 -> 2025 taxonomy mapping rules based on your personal eBird taxonomy report
RENAME_MAPS = {
    "Squirrel Cuckoo": "Common Squirrel-Cuckoo",
    "Elegant Trogon": "Coppery-tailed Trogon",
    "Collared Aracari": "Pale-mandibled Aracari",
    "Gray-hooded Bush Tanager": "Pink-billed Cnemoscopus",
    "Gartered Trogon": "Gartered Violaceous Trogon",
    "Guianan Trogon": "Guianan Violaceous Trogon",
    "Northern Black-throated Trogon": "Graceful Black-throated Trogon",
    "Eurasian Hoopoe": "Common Hoopoe",
    "Cherrie's Tanager": "Scarlet-rumped Tanager",
    "Passerini's Tanager": "Scarlet-rumped Tanager",
    "Mealy Parrot": "Mealy Amazon",
    "Greenfinch": "European Greenfinch",
    "Violaeous Trogon": "Violaceous Trogon",
    "White-crested Elania": "White-crested Elaenia",
    "Safron-crowned Tanager": "Saffron-crowned Tanager",
    "Barn Swalliow": "Barn Swallow",
    "Broadbilled Hummingbird": "Broad-billed Hummingbird",
    "Ochreaceous Pewee": "Ochraceous Pewee",
    "Great Tinnamou": "Great Tinamou",
    "Slated-colored Junco": "Slate-colored Junco",
    "Common House-Martin": "Western House-Martin",
    "House Martin": "Western House-Martin",
    "Common Whitethroat": "Greater Whitethroat",
    "Sooty-capped Bush-Tanager": "Sooty-capped Chlorospingus",
    "Grey-headed Tanager": "Gray-headed Tanager",
    "Yellow-billed Tropicbird": "White-tailed Tropicbird",
    "Red-crowned Parrot": "Red-crowned Amazon",
    "Glistening Green Tanager": "Glistening-green Tanager",
    "Tāiko": "Magenta Petrel",
    "Tūī": "Tui",
    "Western Mockingbird": "Northern Mockingbird",
}

SPLIT_MAPS = {
    "Whimbrel": ["Hudsonian Whimbrel", "Eurasian Whimbrel"],
    "Southern Rockhopper Penguin": ["Eastern Rockhopper Penguin", "Western Rockhopper Penguin"],
    "Striated Heron": ["Lava Heron", "Little Heron", "Striated Heron"],
    "Warbling Vireo": ["Eastern Warbling Vireo", "Western Warbling Vireo"],
    "Yellow Warbler": ["Mangrove Yellow Warbler", "Northern Yellow Warbler"],
}

LUMP_MAPS = {
    "Antarctic Shag": "Imperial Cormorant",
    "Macquarie Shag": "Imperial Cormorant",
    "South Georgia Shag": "Imperial Cormorant",
}

# Case-insensitive maps for lookup safety
RENAME_MAPS_LOWER = {k.lower(): (k, v) for k, v in RENAME_MAPS.items()}
SPLIT_MAPS_LOWER = {k.lower(): (k, v) for k, v in SPLIT_MAPS.items()}
LUMP_MAPS_LOWER = {k.lower(): (k, v) for k, v in LUMP_MAPS.items()}

def load_ebird_sightings_by_date(csv_path):
    """
    Parses eBird CSV file and returns:
    date_str (YYYY-MM-DD) -> set of species names logged
    """
    sightings = {}
    if not os.path.exists(csv_path):
        print(f"⚠️ Warning: eBird CSV file not found at {csv_path}")
        return sightings
        
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
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

def fetch_photos_needing_migration(cursor):
    """Queries Lightroom for all published photos carrying 2024 tags to migrate."""
    all_before_names = set(RENAME_MAPS.keys()).union(SPLIT_MAPS.keys()).union(LUMP_MAPS.keys())
    placeholders = ", ".join("?" for _ in all_before_names)
    
    query = f"""
    SELECT DISTINCT
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime,
        FolderPath,
        Source
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime,
            fold.pathFromRoot AS FolderPath,
            'Color Label' AS Source
        FROM Adobe_images i
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        JOIN AgLibraryFolder fold ON f.folder = fold.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        WHERE LOWER(i.colorLabels) IN ({placeholders})
        
        UNION ALL
        
        SELECT 
            k.name AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime,
            fold.pathFromRoot AS FolderPath,
            'Keyword Tag' AS Source
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        JOIN AgLibraryFolder fold ON f.folder = fold.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        WHERE LOWER(k.name) IN ({placeholders})
    )
    ORDER BY SpeciesName, CaptureTime;
    """
    
    lower_names = [name.lower() for name in all_before_names]
    params = lower_names + lower_names
    cursor.execute(query, params)
    return cursor.fetchall()

def save_to_csv(output_path, items):
    """Writes list of migration items to CSV."""
    headers = ["Photo Filename", "Lightroom Path", "Tag Source", "Capture Date", "Current 2024 Tag", "Type", "Suggested 2025 Action"]
    with open(output_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in items:
            writer.writerow([
                r["filename"],
                r["lr_path"],
                r["source"],
                r["date"],
                r["old_tag"],
                r["type"],
                r["suggested_action_txt"]
            ])

def save_to_html(output_path, items, total_photos):
    """Generates the HTML migration report with sections and rows."""
    base_dir = os.path.dirname(__file__)
    
    # 1. Load layout
    with open(os.path.join(base_dir, "templates", "base_layout.html"), "r") as f:
        html = f.read()
        
    # 2. Load sub-templates
    with open(os.path.join(base_dir, "templates", "migration_section.html"), "r") as f:
        section_template = f.read()
    with open(os.path.join(base_dir, "templates", "migration_row_simple.html"), "r") as f:
        row_simple_template = f.read()
    with open(os.path.join(base_dir, "templates", "migration_row_split.html"), "r") as f:
        row_split_template = f.read()

    # Split items into categories
    renames = [x for x in items if x["type"] in ("Rename", "Lump")]
    splits = [x for x in items if x["type"] == "Split"]

    sections_html = []

    # Section 1: Simple Renames & Lumps
    if renames:
        row_html_list = []
        for r in renames:
            row_html = (row_simple_template
                        .replace("{{ OLD_NAME }}", r["old_tag"])
                        .replace("{{ NEW_NAME }}", r["suggested_action_txt"])
                        .replace("{{ FILENAME }}", r["filename"])
                        .replace("{{ PATH }}", r["lr_path"])
                        .replace("{{ SOURCE }}", r["source"]))
            row_html_list.append("        " + row_html.strip())
            
        headers = "<th>Current 2024 Tag</th><th></th><th>New 2025 Tag</th><th>Filename</th><th>Lightroom Folder Reference</th><th>Source</th>"
        sec1 = (section_template
                .replace("{{ SECTION_TITLE }}", f"1. Simple Renames & Lumps ({len(renames)} items)")
                .replace("{{ SECTION_DESCRIPTION }}", "These tags are 1-to-1 renames or taxonomic lumps. You can easily double-click the old keyword in Lightroom's Keyword List panel and rename it, or drag-and-drop to clean up.")
                .replace("{{ HEADERS }}", headers)
                .replace("{{ ROWS }}", "\n".join(row_html_list)))
        sections_html.append(sec1)

    # Section 2: Splits requiring manual resolution
    if splits:
        row_html_list = []
        for r in splits:
            sightings_str = ", ".join(sorted(r["ebird_sightings"])) if r["ebird_sightings"] else "<span style='color: #888;'>None</span>"
            action_html = f"<span style='color: #ffd32a;'>{r['suggested_action_txt']}</span>"
            if "confirmed" in r["suggested_action_txt"]:
                action_html = f"<span style='color: #2ed573;'>{r['suggested_action_txt']}</span>"
                
            row_html = (row_split_template
                        .replace("{{ OLD_NAME }}", r["old_tag"])
                        .replace("{{ FILENAME }}", r["filename"])
                        .replace("{{ DATE }}", r["date"])
                        .replace("{{ EBIRD_SIGHTINGS }}", sightings_str)
                        .replace("{{ SUGGESTED_ACTION }}", action_html)
                        .replace("{{ PATH }}", r["lr_path"]))
            row_html_list.append("        " + row_html.strip())
            
        headers = "<th>2024 Tag (Split Species)</th><th>Filename</th><th>Capture Date</th><th>Logged eBird Sightings (Same Date)</th><th>Smart Suggestion</th><th>Lightroom Folder Reference</th>"
        sec2 = (section_template
                .replace("{{ SECTION_TITLE }}", f"2. Taxonomic Splits ({len(splits)} items)")
                .replace("{{ SECTION_DESCRIPTION }}", "These species were split. We checked your capture dates against your eBird sightings logs from the same dates to suggest the correct new split species concept.")
                .replace("{{ HEADERS }}", headers)
                .replace("{{ ROWS }}", "\n".join(row_html_list)))
        sections_html.append(sec2)

    content_html = "\n\n".join(sections_html)

    # Summary Statistics Header Cards
    stats_html = f"""
    <div class="dashboard-summary">
        <div class="summary-card info">
            <div class="card-title">Total Audit Items</div>
            <div class="card-val">{total_photos}</div>
        </div>
        <div class="summary-card primary">
            <div class="card-title">Simple Renames</div>
            <div class="card-val">{len(renames)}</div>
        </div>
        <div class="summary-card warning">
            <div class="card-title">Splits to Resolve</div>
            <div class="card-val">{len(splits)}</div>
        </div>
    </div>
    """

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
        .file-cell {
            font-family: monospace;
            color: #a55eea;
        }
        .date-cell {
            font-family: monospace;
            color: #888;
        }
        .source-cell {
            color: #00fa9a;
            font-size: 0.9em;
        }
        .path-cell {
            color: #888;
            font-size: 0.85em;
        }
        .dashboard-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .summary-card {
            background-color: #1a1a1a;
            border-left: 4px solid #4db8ff;
            padding: 20px;
            border-radius: 6px;
        }
        .summary-card.warning { border-left-color: #ff9f43; }
        .summary-card.primary { border-left-color: #2e7d32; }
        .summary-card.info { border-left-color: #a55eea; }
        .card-title {
            font-size: 0.9em;
            text-transform: uppercase;
            color: #aaa;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .card-val {
            font-size: 2.2em;
            font-weight: bold;
            color: #fff;
        }
        .section-heading {
            font-size: 1.6em;
            font-weight: bold;
            color: #fff;
            margin-bottom: 10px;
            border-bottom: 2px solid #a55eea;
            padding-bottom: 8px;
        }
        .section-desc {
            color: #aaa;
            margin-bottom: 20px;
            font-size: 0.95em;
        }
    """

    # Substitution
    html = html.replace("{{ PAGE_TITLE }}", "eBird v2025 Taxonomy Migration Audit")
    html = html.replace("{{ HEADER_TITLE }}", "eBird v2025 Taxonomy Migration Audit")
    html = html.replace("{{ STATS_HEADER }}", stats_html)
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    print("Loading eBird checklists from ebird.csv...")
    ebird_sightings = load_ebird_sightings_by_date(EBIRD_CSV)
    print(f"Loaded logs for {len(ebird_sightings)} dates from ebird.csv.")

    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        rows = fetch_photos_needing_migration(cursor)
        
    print(f"Found {len(rows)} photo tags matching affected 2024 species list.")

    migration_items = []
    for r in rows:
        species_name = r[0]
        filename = r[1]
        collection = r[2]
        capture_time = r[3]
        folder_path = r[4]
        source = r[5]
        
        name_lower = species_name.lower().strip()
        capture_date = capture_time[:10] if capture_time else "N/A"
        lr_ref = f"Coll: {collection} | Folder: {folder_path}"

        # 1. Check if it's a rename
        if name_lower in RENAME_MAPS_LOWER:
            original, suggested = RENAME_MAPS_LOWER[name_lower]
            if original.lower().strip() == suggested.lower().strip():
                continue
            migration_items.append({
                "filename": filename,
                "lr_path": lr_ref,
                "source": source,
                "date": capture_date,
                "old_tag": original,
                "type": "Rename",
                "suggested_action_txt": suggested,
                "ebird_sightings": []
            })
            
        # 2. Check if it's a lump
        elif name_lower in LUMP_MAPS_LOWER:
            original, suggested = LUMP_MAPS_LOWER[name_lower]
            if original.lower().strip() == suggested.lower().strip():
                continue
            migration_items.append({
                "filename": filename,
                "lr_path": lr_ref,
                "source": source,
                "date": capture_date,
                "old_tag": original,
                "type": "Lump",
                "suggested_action_txt": suggested,
                "ebird_sightings": []
            })
            
        # 3. Check if it's a split
        elif name_lower in SPLIT_MAPS_LOWER:
            original, candidates = SPLIT_MAPS_LOWER[name_lower]
            
            # Cross-reference with eBird log
            logged = ebird_sightings.get(capture_date, set())
            matches = logged.intersection(candidates)
            
            if len(matches) == 1:
                rec_action = f"Update to: {list(matches)[0]} (confirmed via eBird log)"
            elif len(matches) > 1:
                rec_action = f"Choose option: {', '.join(sorted(matches))} (multiple logged)"
            else:
                rec_action = f"Manual Review: {', '.join(candidates)}"
                
            migration_items.append({
                "filename": filename,
                "lr_path": lr_ref,
                "source": source,
                "date": capture_date,
                "old_tag": original,
                "type": "Split",
                "suggested_action_txt": rec_action,
                "ebird_sightings": list(logged)
            })

    print(f"Audited matches completed. Generating reports...")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    save_to_csv(OUTPUT_CSV, migration_items)
    save_to_html(OUTPUT_HTML, migration_items, len(migration_items))
    
    print(f"✅ Success! Reports generated:")
    print(f"   • CSV:  {OUTPUT_CSV}")
    print(f"   • HTML: {OUTPUT_HTML}")

if __name__ == "__main__":
    main()
