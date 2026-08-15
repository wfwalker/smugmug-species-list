import os
from tools.audit_taxonomy_migration import audit_migration_tasks, SPLIT_MAPS_LOWER
from lib.dashboard_parser import (
    load_json_species,
    parse_ebird_sightings,
    load_ebird_sightings_by_date,
    load_ebird_locations,
    load_valid_taxonomy_names
)
from lib.dashboard_resolver import build_automatic_resolutions
from lib.dashboard_db import fetch_db_statistics
from lib.dashboard_report import generate_report
from generators.migration_dashboard import save_to_csv, save_to_html
from lib.lrcat_utils import BIRD_ROOT

def run_migration_dashboard_pipeline(cursor, base_dir):
    """
    Unified pipeline execution for building the Migration and Publishing Dashboard.
    Reads inputs, queries Lightroom catalog via cursor, audits taxonomy, resolves splits, and writes output files.
    """
    reports_dir = os.path.join(base_dir, "reports")
    output_csv = os.path.join(reports_dir, "bird_migration_dashboard.csv")
    output_html = os.path.join(reports_dir, "bird_migration_dashboard.html")
    
    json_path = os.path.join(base_dir, "photos-ebird-mybird.json")
    ebird_path = os.path.join(base_dir, "ebird.csv")
    taxonomy_path = os.path.join(base_dir, "taxonomy", "eBird_taxonomy_v2025.csv")
    taxonomy_dir = os.path.join(base_dir, "taxonomy")
    
    json_species = load_json_species(json_path)
    ebird_sightings = parse_ebird_sightings(ebird_path)
    ebird_sightings_by_date = load_ebird_sightings_by_date(ebird_path)
    ebird_locs = load_ebird_locations(ebird_path)
    valid_taxonomy_names = load_valid_taxonomy_names(taxonomy_path)
    auto_recs, auto_splits, normalized_v2025 = build_automatic_resolutions(taxonomy_dir)
    
    excluded_tags = ["People", "Wildlife", "Ice", "Landscape", "Plant", "Lichen", "Pet", "Zoo", "Wedding", "Garden"]
    (
        label_stats, 
        keyword_stats, 
        published_stats, 
        missing_location_counts, 
        photos_missing_location, 
        earliest_photos,
        fully_migrated_species,
        needs_tagging_examples
    ) = fetch_db_statistics(cursor, excluded_tags)
    
    migration_items = audit_migration_tasks(cursor, ebird_sightings_by_date)
    
    all_split_rules = {}
    for k, v in SPLIT_MAPS_LOWER.items():
        all_split_rules[k] = (v[0], v[1])
    for k, v in auto_splits.items():
        all_split_rules[k.lower()] = (k, v)
        
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
                match_name = list(matches)[0]
                if match_name.lower() == original.lower():
                    rec = f'<span class="success-text" style="color: #2ed573;">Already correct: {match_name} (confirmed via eBird log)</span>'
                else:
                    rec = f'<span class="success-text" style="color: #2ed573;">Update to: {match_name} (confirmed via eBird log)</span>'
            elif len(matches) > 1:
                rec = f'<span class="warning-text" style="color: #ff9f43;">Choose: {", ".join(sorted(matches))} (multiple logged)</span>'
            else:
                rec = f'<span class="error-text" style="color: #ff4d4d;">Manual Review: {", ".join(candidates)} (none logged)</span>'
                
            photo_recs.append(f'<li><span class="file-cell">{filename}</span> in <strong style="color: #aaa;">{folder_path}</strong> ({capture_date}) ➔ {rec}</li>')
            
        split_details_by_species[original] = photo_recs
        
    print("Querying photo capture dates to augment research prompts...")
    excluded_tags_sql = ", ".join(f"'{tag}'" for tag in excluded_tags)
    exclude_clause = f"""
      AND i.id_local NOT IN (
          SELECT ki_ex.image 
          FROM AgLibraryKeywordImage ki_ex
          JOIN AgLibraryKeyword k_ex ON ki_ex.tag = k_ex.id_local
          WHERE k_ex.name IN ({excluded_tags_sql})
      )
    """
    cursor.execute(f"""
        SELECT SpeciesName, CaptureTime
        FROM (
            SELECT 
                k.name AS SpeciesName,
                i.captureTime AS CaptureTime
            FROM AgLibraryKeyword k
            JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
            JOIN Adobe_images i ON ki.image = i.id_local
            WHERE k.genealogy LIKE ?
              {exclude_clause}
            
            UNION ALL
            
            SELECT 
                i.colorLabels AS SpeciesName,
                i.captureTime AS CaptureTime
            FROM Adobe_images i
            WHERE i.colorLabels != '' 
              AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
              {exclude_clause}
        )
    """, (BIRD_ROOT,))
    
    photo_dates_by_species = {}
    for spec, cap_time in cursor.fetchall():
        if not spec or not cap_time:
            continue
        date_str = cap_time[:10]
        if spec not in photo_dates_by_species:
            photo_dates_by_species[spec] = set()
        photo_dates_by_species[spec].add(date_str)

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
    
    os.makedirs(reports_dir, exist_ok=True)
    save_to_csv(output_csv, merged_rows)
    save_to_html(
        output_html, 
        merged_rows, 
        photos_missing_location, 
        earliest_photos, 
        migration_items, 
        split_details_by_species, 
        auto_recs, 
        normalized_v2025, 
        ebird_locs,
        needs_tagging_examples,
        photo_dates_by_species=photo_dates_by_species,
        root_dir=base_dir
    )
    
    print(f"✅ Dashboard generated: {output_html}")
    return output_html
