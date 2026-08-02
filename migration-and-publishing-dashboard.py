#!/usr/bin/python3

import csv
import json
import os
from lrcat_utils import open_catalog, BIRD_ROOT, format_location
from audit_taxonomy_migration import audit_migration_tasks, load_ebird_sightings_by_date, RENAME_MAPS_LOWER, LUMP_MAPS_LOWER, SPLIT_MAPS_LOWER

REPORTS_DIR = "reports"
OUTPUT_CSV = os.path.join(REPORTS_DIR, "bird_migration_dashboard.csv")
OUTPUT_HTML = os.path.join(REPORTS_DIR, "bird_migration_dashboard.html")

EXCLUDED_TAGS = ["People", "Wildlife", "Ice", "Landscape", "Plant", "Lichen"]

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

def load_valid_taxonomy_names(taxonomy_path):
    """Loads all valid English common names from the eBird taxonomy CSV file."""
    valid_names = set()
    if not os.path.exists(taxonomy_path):
        print(f"⚠️ Warning: Taxonomy file not found at {taxonomy_path}")
        return valid_names
        
    try:
        with open(taxonomy_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                com_name = row.get("PRIMARY_COM_NAME")
                if com_name:
                    valid_names.add(com_name.strip())
    except Exception as e:
        print(f"⚠️ Error parsing taxonomy CSV: {e}")
    return valid_names

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
    - fully_migrated_species: set of species names that have at least one fully migrated published photo
    """
    
    excluded_tags_sql = ", ".join(f"'{tag}'" for tag in EXCLUDED_TAGS)
    exclude_clause = f"""
      AND i.id_local NOT IN (
          SELECT ki_ex.image 
          FROM AgLibraryKeywordImage ki_ex
          JOIN AgLibraryKeyword k_ex ON ki_ex.tag = k_ex.id_local
          WHERE k_ex.name IN ({excluded_tags_sql})
      )
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
      {exclude_clause}
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
      {exclude_clause}
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
          {exclude_clause}
        
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
          {exclude_clause}
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
          {exclude_clause}
        
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
          {exclude_clause}
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
          {exclude_clause}
          
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
          {exclude_clause}
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
              {exclude_clause}
              
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
              {exclude_clause}
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

    # Query G: Find species with at least one published photo having label + keyword + location
    query_fully_migrated = """
    SELECT DISTINCT
        k.name AS SpeciesName
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
    JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
    JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
        AND parent_coll.name LIKE '%SmugMug%'
    LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
    WHERE k.genealogy LIKE ?
      AND i.colorLabels = k.name
      AND (
          (iptc.locationRef IS NOT NULL AND iptc.locationRef != '') OR
          (iptc.cityRef IS NOT NULL AND iptc.cityRef != '') OR
          (iptc.stateRef IS NOT NULL AND iptc.stateRef != '') OR
          (iptc.countryRef IS NOT NULL AND iptc.countryRef != '')
      )
      {exclude_clause};
    """

    # Bulk replacement of placeholders
    query_label = query_label.replace("{exclude_clause}", exclude_clause)
    query_keyword = query_keyword.replace("{exclude_clause}", exclude_clause)
    query_published = query_published.replace("{exclude_clause}", exclude_clause)
    query_missing_location_counts = query_missing_location_counts.replace("{exclude_clause}", exclude_clause)
    query_photos_missing_location = query_photos_missing_location.replace("{exclude_clause}", exclude_clause)
    query_earliest_photos = query_earliest_photos.replace("{exclude_clause}", exclude_clause)
    query_fully_migrated = query_fully_migrated.replace("{exclude_clause}", exclude_clause)

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

    # Query G: Find species with at least one published photo having label + keyword + location
    query_fully_migrated = """
    SELECT DISTINCT
        k.name AS SpeciesName
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
    JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
    JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
        AND parent_coll.name LIKE '%SmugMug%'
    LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
    WHERE k.genealogy LIKE ?
      AND i.colorLabels = k.name
      AND (
          (iptc.locationRef IS NOT NULL AND iptc.locationRef != '') OR
          (iptc.cityRef IS NOT NULL AND iptc.cityRef != '') OR
          (iptc.stateRef IS NOT NULL AND iptc.stateRef != '') OR
          (iptc.countryRef IS NOT NULL AND iptc.countryRef != '')
      );
    """

    cursor.execute(query_fully_migrated, (BIRD_ROOT,))
    fully_migrated_species = {row[0] for row in cursor.fetchall()}

    return (
        label_stats, 
        keyword_stats, 
        published_stats, 
        missing_location_counts, 
        photos_missing_location, 
        earliest_photos,
        fully_migrated_species
    )

def generate_report(label_stats, keyword_stats, published_stats, json_species, ebird_sightings, missing_location_counts, fully_migrated_species, valid_taxonomy_names):
    """Merges all sources into a unified list of species dicts, sorted in priority order."""
    all_species = set(label_stats.keys()).union(json_species).union(published_stats.keys())
    
    # Omit fully migrated species from the main table in Section 1
    all_species = all_species - fully_migrated_species

    valid_names_lower = {n.lower() for n in valid_taxonomy_names} if valid_taxonomy_names else set()

    merged_rows = []
    for species in all_species:
        in_json = "Yes" if species in json_species else "No"
        in_ebird = "Yes" if species in ebird_sightings else "No"
        is_valid_taxonomy = "Yes" if (not valid_taxonomy_names or species.lower() in valid_names_lower) else "No"
        
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
            "is_valid_taxonomy": is_valid_taxonomy,
            "total_label": total_label,
            "total_keyword": total_keyword,
            "published_count": published_count,
            "needs_tagging": needs_tagging,
            "missing_loc_count": missing_loc_count
        })

    # Sorting logic:
    # 1. Obsolete or typo names (not in eBird taxonomy)
    # 2. Species in JSON but not published to SmugMug first (high priority action item)
    # 3. Species published to SmugMug but not in eBird (taxonomic name mismatches)
    # 4. Species with published photos missing location details
    # 5. Species needing Lightroom tagging (needs_tagging > 0)
    # 6. Total label photos descending
    # 7. Species name alphabetical
    def sort_key(item):
        is_invalid_tax = 1 if item["is_valid_taxonomy"] == "No" else 0
        is_json_unpublished = 1 if (item["in_json"] == "Yes" and item["published_count"] == 0) else 0
        is_published_no_ebird = 1 if (item["published_count"] > 0 and item["in_ebird"] == "No") else 0
        has_missing_location = 1 if (item["missing_loc_count"] > 0) else 0
        return (
            -is_invalid_tax,
            -is_json_unpublished,
            -is_published_no_ebird,
            -has_missing_location,
            -item["needs_tagging"],
            -item["total_label"],
            item["species_name"].lower()
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

def save_to_html(output_path, merged_rows, photos_missing_location, earliest_photos, migration_items, split_details_by_species):
    """Writes the unified species-centric dashboard report to an HTML file."""
    base_dir = os.path.dirname(__file__)
    
    # 1. Load layout template
    layout_path = os.path.join(base_dir, "templates", "base_layout.html")
    with open(layout_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    # 2. Load summary panel template
    with open(os.path.join(base_dir, "templates", "dashboard_summary.html"), "r") as f:
        summary_template = f.read()

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
    invalid_taxonomy_count = sum(1 for r in merged_rows if r["is_valid_taxonomy"] == "No")

    # 4. Render Summary Cards panel
    summary_panel = (summary_template
                     .replace("{{ TOTAL_SPECIES }}", f"{total_species:,}")
                     .replace("{{ NEEDS_TAGGING }}", f"{needs_tagging_count:,}")
                     .replace("{{ JSON_UNPUBLISHED }}", f"{json_unpublished:,}")
                     .replace("{{ MISSING_LOCATION }}", f"{total_missing_loc:,}")
                     .replace("{{ MISSING_EBIRD }}", f"{no_ebird_count:,}")
                     .replace("{{ INVALID_TAXONOMY }}", f"{invalid_taxonomy_count:,}"))

    # Group photos missing location by species
    photos_missing_by_species = {}
    for r in photos_missing_location:
        spec = r[0]
        if spec not in photos_missing_by_species:
            photos_missing_by_species[spec] = []
        photos_missing_by_species[spec].append(r)

    # 5. Build Unified Master Table Rows
    rows_html = []
    for idx, r in enumerate(merged_rows):
        species_name = r["species_name"]
        toggle_id = f"details-{idx}"
        
        # Determine badges / alerts
        badges = []
        if r["is_valid_taxonomy"] == "No":
            badges.append('<span class="badge error" style="background-color: rgba(255, 63, 63, 0.15); color: #ff3f3f; border: 1px solid rgba(255, 63, 63, 0.3);">Invalid Taxonomy</span>')
        if r["needs_tagging"] > 0:
            badges.append(f'<span class="badge warning">Needs Tagging ({r["needs_tagging"]})</span>')
        if r["missing_loc_count"] > 0:
            badges.append(f'<span class="badge error">Missing Loc ({r["missing_loc_count"]})</span>')
        if r["published_count"] > 0 and r["in_ebird"] == "No":
            badges.append('<span class="badge info">Not in eBird</span>')
        if r["in_json"] == "Yes" and r["published_count"] == 0:
            badges.append('<span class="badge muted">Unpublished</span>')
        if not badges:
            badges.append('<span class="badge success">Synced & Migrated</span>')
        badges_html = " ".join(badges)

        needs_tagging_class = "warning-text" if r["needs_tagging"] > 0 else ""
        missing_loc_class = "error-text" if r["missing_loc_count"] > 0 else ""

        # Earliest Photo details
        earliest = earliest_photos.get(species_name, {})
        earliest_date = earliest.get("date", "N/A")
        earliest_location = earliest.get("location", "N/A")
        earliest_gallery = earliest.get("collection", "N/A")
        earliest_filename = earliest.get("filename", "N/A")

        # Action Details block
        issues_list = []
        if r["is_valid_taxonomy"] == "No":
            name_lower = species_name.lower().strip()
            action_text = ""
            if name_lower in RENAME_MAPS_LOWER:
                action_text = f' Recommended Action: Update to <strong>"{RENAME_MAPS_LOWER[name_lower][1]}"</strong>.'
            elif name_lower in LUMP_MAPS_LOWER:
                action_text = f' Recommended Action: Lump into <strong>"{LUMP_MAPS_LOWER[name_lower][1]}"</strong>.'
            elif name_lower in SPLIT_MAPS_LOWER:
                candidates_str = ", ".join(f'"{c}"' for c in SPLIT_MAPS_LOWER[name_lower][1])
                action_text = f' Recommended Action: Split into one of <strong>{candidates_str}</strong>.'
                
            issues_list.append(f'<p class="error-text" style="color: #ff3f3f; margin-bottom: 4px;">❌ <strong>Invalid Name:</strong> "{species_name}" is not a valid common name in the eBird v2025 taxonomy. Update this tag/label in Lightroom.{action_text}</p>')
            issues_list.append('<p class="info-text" style="color: #888; font-size: 0.85em; margin-top: 0; margin-bottom: 12px; padding-left: 20px;">💡 <em>Hint:</em> If this is a mammal, plant, landscape, or other non-bird subject, assign the keyword tag <strong>"Wildlife"</strong> or <strong>"Landscape"</strong> to it in Lightroom. The dashboard will then automatically exclude it.</p>')
            
            # Append catalog-wide photo-level split recommendations if available
            split_recs = split_details_by_species.get(species_name)
            if split_recs:
                issues_list.append('<h5 style="margin-top: 15px; margin-bottom: 5px; color: #ff9f43;">📅 eBird Sighting Log Match Recommendations (by photo date):</h5>')
                issues_list.append('<div class="photo-audit-list">')
                issues_list.append('<ul style="list-style-type: none; padding-left: 0; margin: 0; font-size: 0.85em; line-height: 1.6;">')
                issues_list.extend(split_recs)
                issues_list.append('</ul>')
                issues_list.append('</div>')
        if r["needs_tagging"] > 0:
            issues_list.append(f'<p class="warning-text">⚠️ <strong>Needs Tagging:</strong> {r["needs_tagging"]} photos have this color label but lack the corresponding taxonomy keyword tag.</p>')
        if r["missing_loc_count"] > 0:
            issues_list.append(f'<p class="error-text">📍 <strong>Missing Location:</strong> {r["missing_loc_count"]} published photos have no location details.</p>')
            issues_list.append('<ul class="missing-loc-list">')
            spec_photos = photos_missing_by_species.get(species_name, [])
            for pm in spec_photos:
                cap_date = pm[3][:10] if pm[3] else "N/A"
                issues_list.append(f'<li><span class="file-cell">{pm[1]}</span> in <strong>{pm[2]}</strong> (Captured {cap_date})</li>')
            issues_list.append('</ul>')
        if r["published_count"] > 0 and r["in_ebird"] == "No":
            issues_list.append('<p class="warning-text">🐦 <strong>eBird Discrepancy:</strong> Published in your SmugMug portfolio but has no matching sighting record in your eBird sightings file (ebird.csv).</p>')
        if not issues_list:
            issues_list.append('<p class="success-text">🎉 This species is fully synchronized, labeled, tagged, and matching your eBird logs.</p>')
        issues_html = "\n".join(issues_list)

        # Main row HTML
        main_row = f"""
        <tr class="species-row" onclick="toggleDetails('{toggle_id}')">
            <td class="toggle-icon-cell"><span class="toggle-icon" id="icon-{toggle_id}">▶</span></td>
            <td class="species-cell">{species_name}</td>
            <td class="status-cell">{r["in_json"]}</td>
            <td class="status-cell">{r["in_ebird"]}</td>
            <td class="num-cell">{r["total_label"]}</td>
            <td class="num-cell">{r["total_keyword"]}</td>
            <td class="num-cell">{r["published_count"]}</td>
            <td class="num-cell {needs_tagging_class}">{r["needs_tagging"]}</td>
            <td class="num-cell {missing_loc_class}">{r["missing_loc_count"]}</td>
            <td class="actions-cell">{badges_html}</td>
        </tr>
        """
        
        # Details drawer row HTML
        drawer_row = f"""
        <tr class="details-row" id="{toggle_id}" style="display: none;">
            <td colspan="10" class="details-container-cell">
                <div class="details-container">
                    <div class="details-grid">
                        <div class="details-card earliest-card">
                            <h4>📅 Earliest Photo Sighting</h4>
                            <p><strong>First Photographed:</strong> {earliest_date}</p>
                            <p><strong>Location:</strong> {earliest_location}</p>
                            <p><strong>Gallery:</strong> {earliest_gallery}</p>
                            <p><strong>Filename:</strong> <span class="file-cell">{earliest_filename}</span></p>
                        </div>
                        <div class="details-card issues-card">
                            <h4>⚠️ Active Action Details</h4>
                            {issues_html}
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        """
        rows_html.append(main_row.strip() + "\n" + drawer_row.strip())

    rows_joined = "\n".join(rows_html)
    master_table = f"""
    <div class="dashboard-section">
        <h2 class="section-heading">Species Library Health Index</h2>
        <p class="section-desc">Unified master checklist of all bird species in your photo library. Click any species row to expand and view its earliest photographed details, taxonomy tagging details, or specific file listings needing location recovery.</p>
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th></th>
                    <th>Species Name</th>
                    <th style="text-align: center;">In JSON</th>
                    <th style="text-align: center;">In eBird</th>
                    <th style="text-align: right;">Label Photos</th>
                    <th style="text-align: right;">Taxonomic Tag</th>
                    <th style="text-align: right;">Published</th>
                    <th style="text-align: right;">Needs Tagging</th>
                    <th style="text-align: right;">Missing Loc</th>
                    <th>Action Items</th>
                </tr>
            </thead>
            <tbody>
                {rows_joined}
            </tbody>
        </table>
    </div>
    
    <script>
    function toggleDetails(rowId) {{
        var detailsRow = document.getElementById(rowId);
        var icon = document.getElementById("icon-" + rowId);
        if (detailsRow.style.display === "none") {{
            detailsRow.style.display = "table-row";
            icon.classList.add("expanded");
        }} else {{
            detailsRow.style.display = "none";
            icon.classList.remove("expanded");
        }}
    }}
    </script>
    """

    migration_section_html = ""
    if migration_items:
        migration_rows = []
        for item in migration_items:
            migration_rows.append(f"""
            <tr>
                <td class="file-cell">{item["filename"]}</td>
                <td style="font-size: 0.85em; color: #aaa;">{item["lr_path"]}</td>
                <td><span class="badge warning">{item["source"]}</span></td>
                <td class="date-cell">{item["date"]}</td>
                <td class="error-text">{item["old_tag"]}</td>
                <td><span class="badge info">{item["type"]}</span></td>
                <td class="success-text" style="color: #ff9f43;">{item["suggested_action_txt"]}</td>
            </tr>
            """)
        
        migration_rows_joined = "".join(migration_rows)
        migration_section_html = f"""
        <div class="dashboard-section" style="border: 1px solid rgba(255, 159, 67, 0.2); border-radius: 6px; padding: 20px; background-color: #17120e; margin-bottom: 40px;">
            <h2 class="section-heading" style="color: #ff9f43; border-bottom: 2px solid #ff9f43; padding-bottom: 8px; margin-top: 0;">🔄 Active Taxonomic Migrations (Action Required)</h2>
            <p class="section-desc" style="color: #ddd;">The following {len(migration_items)} photos carry obsolete common names or typos in your Lightroom catalog. Correct them in Lightroom to align with the new taxonomy.</p>
            <table class="dashboard-table" style="margin-top: 15px; border: 1px solid #332115;">
                <thead>
                    <tr style="background-color: #241910;">
                        <th style="color: #ff9f43;">Photo Filename</th>
                        <th style="color: #ff9f43;">Lightroom Path</th>
                        <th style="color: #ff9f43;">Tag Source</th>
                        <th style="color: #ff9f43;">Capture Date</th>
                        <th style="color: #ff9f43;">Obsolete Tag</th>
                        <th style="color: #ff9f43;">Type</th>
                        <th style="color: #ff9f43;">Recommended Action</th>
                    </tr>
                </thead>
                <tbody>
                    {migration_rows_joined}
                </tbody>
            </table>
        </div>
        """

    content_html = summary_panel + "\n" + migration_section_html + "\n" + master_table

    # 6. Page CSS rules
    styles = """
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
        .summary-card.primary { border-left-color: #2ed573; }
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
            margin-top: 40px;
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
        .dashboard-table {
            width: 100%;
            border-collapse: collapse;
            background-color: #131313;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
            margin-top: 20px;
        }
        .dashboard-table th {
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
        .dashboard-table td {
            padding: 12px 16px;
            font-size: 0.9em;
            border-bottom: 1px solid #1a1a1a;
        }
        .species-row {
            cursor: pointer;
            transition: background-color 0.15s ease;
        }
        .species-row:hover {
            background-color: #1d1d1d;
        }
        .toggle-icon-cell {
            width: 30px;
            text-align: center;
            color: #888;
            font-size: 0.8em;
        }
        .toggle-icon {
            display: inline-block;
            transition: transform 0.15s ease;
        }
        .toggle-icon.expanded {
            transform: rotate(90deg);
        }
        .details-row {
            background-color: #0b0b0b;
        }
        .details-container-cell {
            padding: 0 !important;
            border-bottom: 1px solid #222 !important;
        }
        .details-container {
            padding: 20px 40px;
            background-color: #0d0d0d;
            border-top: 1px solid #1a1a1a;
            border-bottom: 1px solid #1a1a1a;
        }
        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        .details-card {
            background-color: #151515;
            border: 1px solid #222;
            border-radius: 6px;
            padding: 16px 20px;
        }
        .details-card h4 {
            margin-top: 0;
            margin-bottom: 12px;
            border-bottom: 1px solid #333;
            padding-bottom: 6px;
            color: #fff;
            font-size: 1em;
        }
        .details-card h5 {
            margin-top: 10px;
            margin-bottom: 6px;
            color: #aaa;
            font-size: 0.9em;
        }
        .details-card p {
            margin: 6px 0;
            color: #ccc;
            font-size: 0.9em;
        }
        .missing-loc-list {
            margin: 0;
            padding-left: 20px;
            font-size: 0.85em;
            color: #bbb;
        }
        .missing-loc-list li {
            margin-bottom: 4px;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.75em;
            font-weight: bold;
            border-radius: 4px;
            margin-right: 4px;
            text-transform: uppercase;
        }
        .badge.warning { background-color: rgba(255, 159, 67, 0.15); color: #ff9f43; border: 1px solid rgba(255, 159, 67, 0.3); }
        .badge.error { background-color: rgba(255, 77, 77, 0.15); color: #ff4d4d; border: 1px solid rgba(255, 77, 77, 0.3); }
        .badge.info { background-color: rgba(165, 94, 234, 0.15); color: #a55eea; border: 1px solid rgba(165, 94, 234, 0.3); }
        .badge.success { background-color: rgba(46, 213, 115, 0.15); color: #2ed573; border: 1px solid rgba(46, 213, 115, 0.3); }
        .badge.muted { background-color: rgba(136, 136, 136, 0.15); color: #888; border: 1px solid rgba(136, 136, 136, 0.3); }
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
        .success-text { color: #2ed573; font-weight: bold; }
        .file-cell { font-family: monospace; color: #a55eea; }
        .gallery-cell { color: #2ed573; }
        .date-cell { font-family: monospace; color: #aaa; }
        .location-cell { color: #ccc; }
        .photo-audit-list {
            max-height: 250px;
            overflow-y: auto;
            border: 1px solid #222;
            border-radius: 4px;
            padding: 10px 14px;
            background-color: #0b0b0b;
            margin-top: 8px;
        }
    """

    # 7. Perform substitutions
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
    taxonomy_path = os.path.join(script_dir, "taxonomy", "eBird_taxonomy_v2025.csv")
    
    print("Loading species from JSON list...")
    json_species = load_json_species(json_path)

    print("Loading species from eBird sightings...")
    ebird_sightings = parse_ebird_sightings(ebird_path)

    print("Loading eBird checklists by date for migration audit...")
    ebird_sightings_by_date = load_ebird_sightings_by_date(ebird_path)

    print("Loading valid taxonomy names from eBird taxonomy CSV...")
    valid_taxonomy_names = load_valid_taxonomy_names(taxonomy_path)
    print(f"Loaded {len(valid_taxonomy_names)} valid taxonomy names.")

    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        (
            label_stats, 
            keyword_stats, 
            published_stats, 
            missing_location_counts, 
            photos_missing_location, 
            earliest_photos,
            fully_migrated_species
        ) = fetch_db_statistics(cursor)
        
        print("Running active taxonomy migration audit...")
        migration_items = audit_migration_tasks(cursor, ebird_sightings_by_date)

        print("Pre-calculating eBird date-matched split recommendations for catalog...")
        split_details_by_species = {}
        for name_lower, (original, candidates) in SPLIT_MAPS_LOWER.items():
            cursor.execute("""
                SELECT DISTINCT
                    f.baseName || '.' || f.extension AS Filename,
                    i.captureTime AS CaptureTime,
                    fold.pathFromRoot AS FolderPath
                FROM Adobe_images i
                JOIN AgLibraryFile f ON i.rootFile = f.id_local
                JOIN AgLibraryFolder fold ON f.folder = fold.id_local
                LEFT JOIN AgLibraryKeywordImage ki ON i.id_local = ki.image
                LEFT JOIN AgLibraryKeyword k ON ki.tag = k.id_local
                WHERE LOWER(i.colorLabels) = ? OR LOWER(k.name) = ?
                ORDER BY i.captureTime;
            """, (name_lower, name_lower))
            
            photos = cursor.fetchall()
            if not photos:
                continue
                
            photo_recs = []
            for pr in photos:
                filename = pr[0]
                cap_time = pr[1]
                folder_path = pr[2]
                capture_date = cap_time[:10] if cap_time else "N/A"
                
                logged = ebird_sightings_by_date.get(capture_date, set())
                matches = logged.intersection(candidates)
                
                if len(matches) == 1:
                    rec = f'<span class="success-text" style="color: #2ed573;">Update to: {list(matches)[0]} (confirmed via eBird log)</span>'
                elif len(matches) > 1:
                    rec = f'<span class="warning-text" style="color: #ff9f43;">Choose: {", ".join(sorted(matches))} (multiple logged)</span>'
                else:
                    rec = f'<span class="error-text" style="color: #ff4d4d;">Manual Review: {", ".join(candidates)} (none logged)</span>'
                    
                photo_recs.append(f'<li><span class="file-cell">{filename}</span> in <strong style="color: #aaa;">{folder_path}</strong> ({capture_date}) ➔ {rec}</li>')
                
            split_details_by_species[original] = photo_recs

    print("Processing and merging statistics...")
    merged_rows = generate_report(
        label_stats, 
        keyword_stats, 
        published_stats, 
        json_species, 
        ebird_sightings, 
        missing_location_counts,
        fully_migrated_species,
        valid_taxonomy_names
    )

    print("Saving dashboard report...")
    # Create reports directory if it doesn't exist
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    save_to_csv(OUTPUT_CSV, merged_rows)
    save_to_html(OUTPUT_HTML, merged_rows, photos_missing_location, earliest_photos, migration_items, split_details_by_species)

    # Print summary statistics
    json_unpublished_count = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
    total_needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
    total_missing_loc_count = len(photos_missing_location)
    published_no_ebird_count = sum(1 for r in merged_rows if r["published_count"] > 0 and r["in_ebird"] == "No")
    invalid_taxonomy_count = sum(1 for r in merged_rows if r["is_valid_taxonomy"] == "No")
    
    print(f"✅ Success! Reports saved under the '{REPORTS_DIR}/' subfolder:")
    print(f"   • CSV:  {OUTPUT_CSV}")
    print(f"   • HTML: {OUTPUT_HTML}")
    print(f"\nTotal species in dashboard: {len(merged_rows)}")
    print(f"Species in JSON list: {len(json_species)}")
    print(f"Species in eBird: {len(ebird_sightings)}")
    print(f"❌ Invalid taxonomy names in library: {invalid_taxonomy_count}")
    print(f"❌ Active taxonomic migrations (rename/split): {len(migration_items)}")
    print(f"❌ JSON species NOT yet published to SmugMug: {json_unpublished_count}")
    print(f"⚠️ Species needing Lightroom taxonomy tagging: {total_needs_tagging_count}")
    print(f"📍 Published photos missing location: {total_missing_loc_count}")
    print(f"🐦 Published species with no eBird sighting: {published_no_ebird_count}")

if __name__ == "__main__":
    main()