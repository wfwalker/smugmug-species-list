#!/usr/bin/env python3
"""
Bird Migration & Publishing Dashboard Orchestrator.
Queries Lightroom, matches against eBird logs, resolves taxonomy mismatches,
and generates unified HTML and CSV reports.
"""

import os
from lrcat_utils import open_catalog
from audit_taxonomy_migration import audit_migration_tasks, SPLIT_MAPS_LOWER

# Import modular components
from dashboard_parser import (
    load_json_species,
    parse_ebird_sightings,
    load_ebird_sightings_by_date,
    load_ebird_locations,
    load_valid_taxonomy_names
)
from dashboard_resolver import build_automatic_resolutions
from dashboard_db import fetch_db_statistics
from dashboard_report import generate_report
from dashboard_writer import save_to_csv, save_to_html

REPORTS_DIR = "reports"
OUTPUT_CSV = os.path.join(REPORTS_DIR, "bird_migration_dashboard.csv")
OUTPUT_HTML = os.path.join(REPORTS_DIR, "bird_migration_dashboard.html")

EXCLUDED_TAGS = ["People", "Wildlife", "Ice", "Landscape", "Plant", "Lichen", "Pet", "Wedding"]

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

    print("Loading eBird checklist locations for recovery dashboard...")
    ebird_locs = load_ebird_locations(ebird_path)

    print("Loading valid taxonomy names from eBird taxonomy CSV...")
    valid_taxonomy_names = load_valid_taxonomy_names(taxonomy_path)
    print(f"Loaded {len(valid_taxonomy_names)} valid taxonomy names.")

    print("Building automatic resolutions for invalid taxonomy names...")
    taxonomy_dir = os.path.join(script_dir, "taxonomy")
    auto_recs, auto_splits, normalized_v2025 = build_automatic_resolutions(taxonomy_dir)

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
        ) = fetch_db_statistics(cursor, EXCLUDED_TAGS)
        
        print("Running active taxonomy migration audit...")
        migration_items = audit_migration_tasks(cursor, ebird_sightings_by_date)

        # Merge hardcoded SPLIT_MAPS with dynamically resolved splits
        all_split_rules = {}
        for k, v in SPLIT_MAPS_LOWER.items():
            all_split_rules[k] = (v[0], v[1])
        for k, v in auto_splits.items():
            all_split_rules[k.lower()] = (k, v)

        print("Pre-calculating eBird date-matched split recommendations for catalog...")
        split_details_by_species = {}
        for name_lower, (original, candidates) in all_split_rules.items():
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
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    save_to_csv(OUTPUT_CSV, merged_rows)
    save_to_html(
        OUTPUT_HTML, 
        merged_rows, 
        photos_missing_location, 
        earliest_photos, 
        migration_items, 
        split_details_by_species, 
        auto_recs, 
        normalized_v2025, 
        ebird_locs
    )

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