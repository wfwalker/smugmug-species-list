#!/usr/bin/python3

import csv
import json
import os
from lrcat_utils import open_catalog, BIRD_ROOT, format_location

REPORTS_DIR = "reports"
OUTPUT_CSV = os.path.join(REPORTS_DIR, "bird_migration_dashboard.csv")
OUTPUT_HTML = os.path.join(REPORTS_DIR, "bird_migration_dashboard.html")

def load_json_species(json_path):
    """Loads unique bird species common names from the photos-ebird-mybird.json file."""
    if not os.path.exists(json_path):
        print(f"⚠️ Warning: JSON file not found at {json_path}")
        return set()
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            return {item["Common Name"] for item in json_data if "Common Name" in item}
    except Exception as e:
        print(f"⚠️ Error loading JSON file: {e}")
        return set()

def parse_ebird_sightings(csv_path):
    """Parses eBird CSV file and returns a set of unique common names seen."""
    if not os.path.exists(csv_path):
        print(f"⚠️ Warning: eBird CSV file not found at {csv_path}")
        return set()
        
    sightings = set()
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                common_name = row.get("Common Name")
                if common_name:
                    sightings.add(common_name.strip())
    except Exception as e:
        print(f"⚠️ Error parsing eBird CSV: {e}")
    return sightings

def fetch_db_statistics(cursor):
    """
    Queries the database and returns:
    - label_stats: dict of label -> {total_label, keyword_on_label, needs_tagging}
    - keyword_stats: dict of keyword -> count
    - published_stats: dict of species -> published_count
    - missing_location_counts: dict of species -> count of photos missing locations
    - photos_missing_location: list of tuples (Species, Filename, Collection, Date)
    - earliest_photos: dict of Species -> {filename, collection, date, location}
    """
    
    # Query A: Label-based statistics (Legacy color label info)
    query_label = """
    SELECT 
        i.colorLabels AS SpeciesName,
        COUNT(DISTINCT i.id_local) AS Total_With_This_Label,
        COUNT(DISTINCT ki.image) AS Total_With_Keyword,
        (COUNT(DISTINCT i.id_local) - COUNT(DISTINCT ki.image)) AS Needs_Tagging
    FROM Adobe_images i
    LEFT JOIN AgLibraryKeyword k 
        ON i.colorLabels = k.name 
        AND k.genealogy LIKE ?
    LEFT JOIN AgLibraryKeywordImage ki 
        ON i.id_local = ki.image AND k.id_local = ki.tag
    WHERE i.colorLabels != '' 
      AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
    GROUP BY i.colorLabels;
    """

    # Query B: Keyword-based statistics (Taxonomic keyword info)
    query_keyword = """
    SELECT 
        k.name AS SpeciesName,
        COUNT(DISTINCT i.id_local) AS Total_With_Keyword
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    WHERE k.genealogy LIKE ?
    GROUP BY k.name;
    """

    # Query C: De-duplicated SmugMug published counts (Keyword + Label published photos)
    query_published = """
    SELECT 
        SpeciesName,
        COUNT(DISTINCT ImageId) AS PublishedCount
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            i.id_local AS ImageId
        FROM Adobe_images i
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        WHERE i.colorLabels != '' 
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
        
        UNION
        
        SELECT 
            k.name AS SpeciesName,
            i.id_local AS ImageId
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        WHERE k.genealogy LIKE ?
    )
    GROUP BY SpeciesName;
    """

    # Query D: Count of published photos missing location details per species
    query_missing_location_counts = """
    SELECT 
        SpeciesName,
        COUNT(DISTINCT ImageId) AS MissingCount
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            i.id_local AS ImageId
        FROM Adobe_images i
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
            i.id_local AS ImageId
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
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
    GROUP BY SpeciesName;
    """

    # Query E: Specific detailed published photos missing locations
    query_photos_missing_location = """
    SELECT DISTINCT
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime
        FROM Adobe_images i
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
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
            i.captureTime AS CaptureTime
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
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

    # Query F: Details of the earliest photo for all published species
    query_earliest_photos = """
    WITH RankedPhotos AS (
        SELECT 
            SpeciesName,
            Filename,
            CollectionName,
            CaptureTime,
            Location,
            City,
            State,
            Country,
            ROW_NUMBER() OVER (PARTITION BY SpeciesName ORDER BY CaptureTime ASC) as rn
        FROM (
            SELECT 
                i.colorLabels AS SpeciesName,
                f.baseName || '.' || f.extension AS Filename,
                parent_coll.name AS CollectionName,
                i.captureTime AS CaptureTime,
                loc.value AS Location,
                city.value AS City,
                state.value AS State,
                country.value AS Country
            FROM Adobe_images i
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
            JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
            JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
                AND parent_coll.name LIKE '%SmugMug%'
            LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
            LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
            LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
            LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
            LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
            WHERE i.colorLabels != '' 
              AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
              
            UNION ALL
            
            SELECT 
                k.name AS SpeciesName,
                f.baseName || '.' || f.extension AS Filename,
                parent_coll.name AS CollectionName,
                i.captureTime AS CaptureTime,
                loc.value AS Location,
                city.value AS City,
                state.value AS State,
                country.value AS Country
            FROM AgLibraryKeyword k
            JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
            JOIN Adobe_images i ON ki.image = i.id_local
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
            JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
            JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
                AND parent_coll.name LIKE '%SmugMug%'
            LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
            LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
            LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
            LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
            LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
            WHERE k.genealogy LIKE ?
        )
    )
    SELECT 
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime,
        Location,
        City,
        State,
        Country
    FROM RankedPhotos
    WHERE rn = 1;
    """

    # Fetch label data
    cursor.execute(query_label, (BIRD_ROOT,))
    label_stats = {
        row[0]: {
            "total_label": row[1],
            "keyword_on_label": row[2],
            "needs_tagging": row[3]
        }
        for row in cursor.fetchall()
    }

    # Fetch keyword data
    cursor.execute(query_keyword, (BIRD_ROOT,))
    keyword_stats = {row[0]: row[1] for row in cursor.fetchall()}

    # Fetch published data
    cursor.execute(query_published, (BIRD_ROOT,))
    published_stats = {row[0]: row[1] for row in cursor.fetchall()}

    # Fetch missing location counts
    cursor.execute(query_missing_location_counts, (BIRD_ROOT,))
    missing_location_counts = {row[0]: row[1] for row in cursor.fetchall()}

    # Fetch detailed missing location photos list
    cursor.execute(query_photos_missing_location, (BIRD_ROOT,))
    photos_missing_location = cursor.fetchall()

    # Fetch earliest photo details
    cursor.execute(query_earliest_photos, (BIRD_ROOT,))
    earliest_photos = {}
    for r in cursor.fetchall():
        species = r[0]
        filename = r[1]
        collection = r[2]
        capture_time = r[3]
        formatted_loc = format_location(r[4], r[5], r[6], r[7])
        earliest_photos[species] = {
            "filename": filename,
            "collection": collection,
            "date": capture_time[:10] if capture_time else "N/A",
            "location": formatted_loc
        }

    return (
        label_stats, 
        keyword_stats, 
        published_stats, 
        missing_location_counts, 
        photos_missing_location, 
        earliest_photos
    )

def generate_report(label_stats, keyword_stats, published_stats, json_species, ebird_sightings, missing_location_counts):
    """Merges all sources into a unified list of species dicts, sorted in priority order."""
    all_species = set(label_stats.keys()).union(json_species).union(published_stats.keys())

    merged_rows = []
    for species in all_species:
        in_json = "Yes" if species in json_species else "No"
        in_ebird = "Yes" if species in ebird_sightings else "No"
        
        l_stats = label_stats.get(species, {})
        total_label = l_stats.get("total_label", 0)
        needs_tagging = l_stats.get("needs_tagging", 0)
        
        total_keyword = keyword_stats.get(species, 0)
        published_count = published_stats.get(species, 0)
        missing_loc_count = missing_location_counts.get(species, 0)
        
        merged_rows.append({
            "species_name": species,
            "in_json": in_json,
            "in_ebird": in_ebird,
            "total_label": total_label,
            "total_keyword": total_keyword,
            "published_count": published_count,
            "needs_tagging": needs_tagging,
            "missing_loc_count": missing_loc_count
        })

    # Sorting logic:
    # 1. Species in JSON but not published to SmugMug first (high priority action item)
    # 2. Species published to SmugMug but not in eBird (taxonomic name mismatches)
    # 3. Species with published photos missing location details
    # 4. Species needing Lightroom tagging (needs_tagging > 0)
    # 5. Total label photos descending
    # 6. Species name alphabetical
    def sort_key(item):
        is_json_unpublished = 1 if (item["in_json"] == "Yes" and item["published_count"] == 0) else 0
        is_published_no_ebird = 1 if (item["published_count"] > 0 and item["in_ebird"] == "No") else 0
        has_missing_location = 1 if (item["missing_loc_count"] > 0) else 0
        return (
            -is_json_unpublished,
            -is_published_no_ebird,
            -has_missing_location,
            -item["needs_tagging"],
            -item["total_label"],
            item["species_name"]
        )

    merged_rows.sort(key=sort_key)
    return merged_rows

def save_to_csv(output_path, merged_rows):
    """Writes the dashboard report rows to a CSV file."""
    headers = [
        "Species Name", 
        "In JSON List", 
        "In eBird", 
        "Total Photos (Label)", 
        "Has Taxonomic Keyword", 
        "Published to SmugMug", 
        "Mismatched/Needs Tagging",
        "Photos Missing Location"
    ]

    with open(output_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in merged_rows:
            writer.writerow([
                r["species_name"],
                r["in_json"],
                r["in_ebird"],
                r["total_label"],
                r["total_keyword"],
                r["published_count"],
                r["needs_tagging"],
                r["missing_loc_count"]
            ])

def save_to_html(output_path, merged_rows, photos_missing_location, earliest_photos):
    """Writes the dashboard report to an HTML file using layout and section templates."""
    base_dir = os.path.dirname(__file__)
    
    # 1. Load layout template
    layout_path = os.path.join(base_dir, "templates", "base_layout.html")
    with open(layout_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    # 2. Load partials
    with open(os.path.join(base_dir, "templates", "dashboard_summary.html"), "r") as f:
        summary_template = f.read()
    with open(os.path.join(base_dir, "templates", "dashboard_section.html"), "r") as f:
        section_template = f.read()
    with open(os.path.join(base_dir, "templates", "dashboard_row_s1.html"), "r") as f:
        row_s1_template = f.read()
    with open(os.path.join(base_dir, "templates", "dashboard_row_s2.html"), "r") as f:
        row_s2_template = f.read()
    with open(os.path.join(base_dir, "templates", "dashboard_row_s3.html"), "r") as f:
        row_s3_template = f.read()

    # 3. Calculate summary stats
    total_species = len(merged_rows)
    needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
    json_unpublished = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
    total_missing_loc = len(photos_missing_location)
    published_no_ebird = [
        r["species_name"] for r in merged_rows 
        if r["published_count"] > 0 and r["in_ebird"] == "No"
    ]
    no_ebird_count = len(published_no_ebird)

    # 4. Render Summary Cards panel
    summary_panel = (summary_template
                     .replace("{{ TOTAL_SPECIES }}", f"{total_species:,}")
                     .replace("{{ NEEDS_TAGGING }}", f"{needs_tagging_count:,}")
                     .replace("{{ JSON_UNPUBLISHED }}", f"{json_unpublished:,}")
                     .replace("{{ MISSING_LOCATION }}", f"{total_missing_loc:,}")
                     .replace("{{ MISSING_EBIRD }}", f"{no_ebird_count:,}"))

    # 5. Build Content Sections
    sections_html = []

    # --- Section 1 ---
    s1_headers = """
        <div class="table-header">Species Name</div>
        <div class="table-header" style="text-align: center;">In JSON</div>
        <div class="table-header" style="text-align: center;">In eBird</div>
        <div class="table-header" style="text-align: right;">Label Photos</div>
        <div class="table-header" style="text-align: right;">Taxonomic Tag</div>
        <div class="table-header" style="text-align: right;">Published</div>
        <div class="table-header" style="text-align: right;">Needs Tagging</div>
        <div class="table-header" style="text-align: right;">Missing Loc</div>
    """
    s1_rows = []
    for r in merged_rows:
        needs_tagging_class = "warning-text" if r["needs_tagging"] > 0 else ""
        missing_loc_class = "error-text" if r["missing_loc_count"] > 0 else ""
        
        row_html = (row_s1_template
                    .replace("{{ NAME }}", r["species_name"])
                    .replace("{{ IN_JSON }}", r["in_json"])
                    .replace("{{ IN_EBIRD }}", r["in_ebird"])
                    .replace("{{ TOTAL_LABEL }}", str(r["total_label"]))
                    .replace("{{ TOTAL_KEYWORD }}", str(r["total_keyword"]))
                    .replace("{{ PUBLISHED }}", str(r["published_count"]))
                    .replace("{{ NEEDS_TAGGING_CLASS }}", needs_tagging_class)
                    .replace("{{ NEEDS_TAGGING }}", str(r["needs_tagging"]))
                    .replace("{{ MISSING_LOCATION_CLASS }}", missing_loc_class)
                    .replace("{{ MISSING_LOCATION }}", str(r["missing_loc_count"])))
        s1_rows.append("        " + row_html.strip())
        
    s1_html = (section_template
               .replace("{{ SECTION_TITLE }}", "Section 1: Species Migration & Publishing Status")
               .replace("{{ SECTION_DESCRIPTION }}", "Global overview of species publishing status, comparing Lightroom, eBird sightings list, and the old website JSON index.")
               .replace("{{ TABLE_CLASS }}", "grid-s1")
               .replace("{{ HEADERS }}", s1_headers.strip())
               .replace("{{ ROWS }}", "\n".join(s1_rows)))
    sections_html.append(s1_html)

    # --- Section 2 ---
    s2_headers = """
        <div class="table-header">Species Name</div>
        <div class="table-header">Filename</div>
        <div class="table-header">Collection/Gallery</div>
        <div class="table-header">Capture Date</div>
    """
    s2_rows = []
    if not photos_missing_location:
        s2_rows.append('        <div class="table-row"><div class="table-cell" style="grid-column: span 4; text-align: center; color: #888;">No published photos with missing locations found!</div></div>')
    else:
        for r in photos_missing_location:
            cap_date = r[3][:10] if r[3] else "N/A"
            row_html = (row_s2_template
                        .replace("{{ NAME }}", r[0])
                        .replace("{{ FILENAME }}", r[1])
                        .replace("{{ COLLECTION }}", r[2])
                        .replace("{{ DATE }}", cap_date))
            s2_rows.append("        " + row_html.strip())
            
    s2_html = (section_template
               .replace("{{ SECTION_TITLE }}", "Section 2: Published Photos Needing Location Metadata")
               .replace("{{ SECTION_DESCRIPTION }}", "These published photos have no location information defined in Lightroom (Location, City, State, and Country are all blank).")
               .replace("{{ TABLE_CLASS }}", "grid-s2")
               .replace("{{ HEADERS }}", s2_headers.strip())
               .replace("{{ ROWS }}", "\n".join(s2_rows)))
    sections_html.append(s2_html)

    # --- Section 3 ---
    s3_headers = """
        <div class="table-header">Species Name</div>
        <div class="table-header" style="text-align: right;">Total Published</div>
        <div class="table-header">Earliest Photo</div>
        <div class="table-header">Earliest Date</div>
        <div class="table-header">Earliest Location</div>
    """
    s3_rows = []
    if not published_no_ebird:
        s3_rows.append('        <div class="table-row"><div class="table-cell" style="grid-column: span 5; text-align: center; color: #888;">No published species missing eBird sightings found!</div></div>')
    else:
        for species_name in sorted(published_no_ebird):
            pub_count = next((r["published_count"] for r in merged_rows if r["species_name"] == species_name), 0)
            earliest = earliest_photos.get(species_name, {"filename": "N/A", "date": "N/A", "location": "N/A"})
            row_html = (row_s3_template
                        .replace("{{ NAME }}", species_name)
                        .replace("{{ PUBLISHED }}", str(pub_count))
                        .replace("{{ FILENAME }}", earliest["filename"])
                        .replace("{{ DATE }}", earliest["date"])
                        .replace("{{ LOCATION }}", earliest["location"]))
            s3_rows.append("        " + row_html.strip())
            
    s3_html = (section_template
               .replace("{{ SECTION_TITLE }}", "Section 3: Published Species with No eBird Sightings")
               .replace("{{ SECTION_DESCRIPTION }}", "These species are published in your SmugMug portfolio but have no matching sighting record in your eBird sightings file (ebird.csv). This could represent taxonomy differences, typos, or missing eBird logs.")
               .replace("{{ TABLE_CLASS }}", "grid-s3")
               .replace("{{ HEADERS }}", s3_headers.strip())
               .replace("{{ ROWS }}", "\n".join(s3_rows)))
    sections_html.append(s3_html)

    # 6. Combined content HTML
    content_html = summary_panel + "\n" + "\n".join(sections_html)

    # 7. CSS rules
    styles = """
        /* Dashboard custom styles */
        .dashboard-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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
        .summary-card.primary { border-left-color: #00fa9a; }
        .summary-card.error { border-left-color: #ff4d4d; }
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
        .dashboard-section {
            margin-top: 50px;
            margin-bottom: 50px;
        }
        .section-heading {
            font-size: 1.6em;
            font-weight: bold;
            color: #fff;
            margin-bottom: 10px;
            border-bottom: 1px solid #333;
            padding-bottom: 8px;
        }
        .section-desc {
            color: #aaa;
            margin-bottom: 20px;
            font-size: 0.95em;
        }
        .timeline-table {
            display: grid;
            gap: 1px;
            background-color: #222;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
        }
        .timeline-table.grid-s1 {
            grid-template-columns: 2.2fr 1fr 1fr 1.2fr 1.4fr 1.2fr 1.2fr 1.2fr;
        }
        .timeline-table.grid-s2 {
            grid-template-columns: 1.5fr 1.5fr 1.5fr 1.2fr;
        }
        .timeline-table.grid-s3 {
            grid-template-columns: 1.5fr 1fr 1.5fr 1fr 2fr;
        }
        .table-header {
            background-color: #1a1a1a;
            color: #fff;
            font-weight: bold;
            padding: 12px 16px;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border-bottom: 2px solid #333;
        }
        .table-row {
            display: contents;
        }
        .table-cell {
            background-color: #131313;
            padding: 12px 16px;
            font-size: 0.9em;
            align-self: center;
            border-bottom: 1px solid #1a1a1a;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .table-row:hover .table-cell {
            background-color: #1d1d1d;
        }
        .species-cell {
            font-weight: bold;
            color: #eee;
        }
        .status-cell {
            text-align: center;
            color: #bbb;
        }
        .num-cell {
            text-align: right;
            font-family: monospace;
            font-size: 1em;
            color: #ccc;
        }
        .warning-text { color: #ff9f43; font-weight: bold; }
        .error-text { color: #ff4d4d; font-weight: bold; }
        .file-cell { font-family: monospace; color: #a55eea; }
        .gallery-cell { color: #00fa9a; }
        .date-cell { font-family: monospace; color: #aaa; }
        .location-cell { color: #ccc; }
    """

    # 8. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bird Migration & Publishing Dashboard")
    html = html.replace("{{ HEADER_TITLE }}", "Bird Migration & Publishing Dashboard")
    html = html.replace("{{ STATS_HEADER }}", "")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "photos-ebird-mybird.json")
    ebird_path = os.path.join(script_dir, "ebird.csv")
    
    print("Loading species from JSON list...")
    json_species = load_json_species(json_path)

    print("Loading species from eBird sightings...")
    ebird_sightings = parse_ebird_sightings(ebird_path)

    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        (
            label_stats, 
            keyword_stats, 
            published_stats, 
            missing_location_counts, 
            photos_missing_location, 
            earliest_photos
        ) = fetch_db_statistics(cursor)

    print("Processing and merging statistics...")
    merged_rows = generate_report(
        label_stats, 
        keyword_stats, 
        published_stats, 
        json_species, 
        ebird_sightings, 
        missing_location_counts
    )

    print("Saving dashboard report...")
    # Create reports directory if it doesn't exist
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    save_to_csv(OUTPUT_CSV, merged_rows)
    save_to_html(OUTPUT_HTML, merged_rows, photos_missing_location, earliest_photos)

    # Print summary statistics
    json_unpublished_count = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
    total_needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
    total_missing_loc_count = len(photos_missing_location)
    published_no_ebird_count = sum(1 for r in merged_rows if r["published_count"] > 0 and r["in_ebird"] == "No")
    
    print(f"✅ Success! Reports saved under the '{REPORTS_DIR}/' subfolder:")
    print(f"   • CSV:  {OUTPUT_CSV}")
    print(f"   • HTML: {OUTPUT_HTML}")
    print(f"\nTotal species in dashboard: {len(merged_rows)}")
    print(f"Species in JSON list: {len(json_species)}")
    print(f"Species in eBird: {len(ebird_sightings)}")
    print(f"❌ JSON species NOT yet published to SmugMug: {json_unpublished_count}")
    print(f"⚠️ Species needing Lightroom taxonomy tagging: {total_needs_tagging_count}")
    print(f"📍 Published photos missing location: {total_missing_loc_count}")
    print(f"🐦 Published species with no eBird sighting: {published_no_ebird_count}")

if __name__ == "__main__":
    main()