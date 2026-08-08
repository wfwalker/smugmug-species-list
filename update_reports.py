#!/usr/bin/env python3
"""
Unified CLI for Updating SmugMug Life Lists, Migration Dashboard, and Growth Chart.

Orchestrates:
1. Migration & Publishing Dashboard (reports/bird_migration_dashboard.html & .csv)
2. Alphabetical Life List (html/alphabetical_life_list.html)
3. Taxonomic Life List (html/taxonomic_life_list.html)
4. Chronological Life List (html/chronological_life_list.html)
5. Photographic Life List Growth Chart (html/photo_lifelist_growth.html & .svg)

Optimized with a single Lightroom catalog copy/session for fast execution.
"""

import os
import sys
import time
import argparse
import importlib.util

from lrcat_utils import open_catalog, BIRD_ROOT

# Dynamic import helpers for hyphenated module files
def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run_migration_dashboard(cursor, base_dir):
    print("\n" + "="*60)
    print("🚀 [1/5] Building Migration & Publishing Dashboard...")
    print("="*60)
    
    # Import dashboard modules
    from audit_taxonomy_migration import audit_migration_tasks, SPLIT_MAPS_LOWER
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
    
    excluded_tags = ["People", "Wildlife", "Ice", "Landscape", "Plant", "Lichen", "Pet", "Zoo", "Wedding"]
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
                rec = f'<span class="success-text" style="color: #2ed573;">Update to: {list(matches)[0]} (confirmed via eBird log)</span>'
            elif len(matches) > 1:
                rec = f'<span class="warning-text" style="color: #ff9f43;">Choose: {", ".join(sorted(matches))} (multiple logged)</span>'
            else:
                rec = f'<span class="error-text" style="color: #ff4d4d;">Manual Review: {", ".join(candidates)} (none logged)</span>'
                
            photo_recs.append(f'<li><span class="file-cell">{filename}</span> in <strong style="color: #aaa;">{folder_path}</strong> ({capture_date}) ➔ {rec}</li>')
            
        split_details_by_species[original] = photo_recs
        
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
        needs_tagging_examples
    )
    
    print(f"✅ Dashboard generated: {output_html}")
    return output_html

def run_alphabetical_lifelist(cursor, base_dir):
    print("\n" + "="*60)
    print("🔤 [2/5] Building Alphabetical Photo Life List...")
    print("="*60)
    
    alpha_mod = load_module("alpha_lifelist", os.path.join(base_dir, "alphabetical-lifelist-custom-page.py"))
    output_html = os.path.join(base_dir, "html", "alphabetical_life_list.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    query = """
    WITH RankedPhotos AS (
        SELECT 
            parent_k.id_local AS FamilyId,
            k.id_local AS SpeciesId,
            k.name AS SpeciesName,
            rp.url AS SmugMugUrl,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.collection = pci.collection
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        SpeciesName,
        photo_count,
        SmugMugUrl
    FROM RankedPhotos
    WHERE rn = 1;
    """
    cursor.execute(query, (BIRD_ROOT,))
    raw_results = cursor.fetchall()
    results = sorted(raw_results, key=lambda x: x[0])
    
    html_content = alpha_mod.generate_html_content(results)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Alphabetical life list generated: {output_html} ({len(results)} species)")
    return output_html

def run_taxonomic_lifelist(cursor, base_dir):
    print("\n" + "="*60)
    print("🌿 [3/5] Building Taxonomic Photo Life List...")
    print("="*60)
    
    tax_mod = load_module("tax_lifelist", os.path.join(base_dir, "taxonomic-life-list-custom-page.py"))
    output_html = os.path.join(base_dir, "html", "taxonomic_life_list.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    query = """
    WITH RankedPhotos AS (
        SELECT 
            parent_k.id_local AS FamilyId,
            k.id_local AS SpeciesId,
            parent_k.name AS FamilyGroup,
            k.name AS SpeciesName,
            rp.url AS SmugMugUrl,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.collection = pci.collection
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        FamilyGroup,
        SpeciesName,
        photo_count,
        SmugMugUrl
    FROM RankedPhotos
    WHERE rn = 1
    ORDER BY FamilyId, SpeciesId;
    """
    cursor.execute(query, (BIRD_ROOT,))
    results = cursor.fetchall()
    
    smugmug_galleries = tax_mod.fetch_smugmug_galleries()
    html_content = tax_mod.generate_html_content(results, smugmug_galleries)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Taxonomic life list generated: {output_html} ({len(results)} species)")
    return output_html

def run_chronological_lifelist(cursor, base_dir, show_all=False):
    print("\n" + "="*60)
    print("📅 [4/5] Building Chronological Photo Life List...")
    print("="*60)
    
    chrono_mod = load_module("chrono_lifelist", os.path.join(base_dir, "chronological-lifelist-custom-page.py"))
    output_html = os.path.join(base_dir, "html", "chronological_life_list.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    ebird_csv = os.path.join(base_dir, "ebird.csv")
    ebird_sightings = chrono_mod.parse_ebird_sightings(ebird_csv)
    published_photos = chrono_mod.fetch_earliest_published_photos(cursor)
    
    from collections import defaultdict
    chronological_data = defaultdict(list)
    matched_photo_species = set()
    
    for name, sighting in ebird_sightings.items():
        date_str = sighting["date"]
        loc = sighting["location"]
        photo_info = published_photos.get(name.lower().strip())
        
        if photo_info:
            matched_photo_species.add(name.lower().strip())
        elif not show_all:
            continue
            
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
        
    unmatched_count = 0
    for name_lower, photo_info in published_photos.items():
        if name_lower not in matched_photo_species:
            unmatched_count += 1
            orig_name = photo_info["name"]
            date_str = photo_info["date"]
            loc = photo_info["location"]
            
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
            
    for year in chronological_data:
        chronological_data[year].sort(key=lambda x: (x["ebird_date"], x["name"]), reverse=True)
        
    total_seen_count = len(ebird_sightings) + unmatched_count
    html_content = chrono_mod.generate_html_content(chronological_data, total_seen_count)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Chronological life list generated: {output_html}")
    return output_html

def run_growth_chart(cursor, base_dir):
    print("\n" + "="*60)
    print("📈 [5/5] Building Photographic Species Life List Growth Chart...")
    print("="*60)
    
    growth_mod = load_module("growth_chart", os.path.join(base_dir, "generate_photo_growth_chart.py"))
    chrono_mod = load_module("chrono_lifelist", os.path.join(base_dir, "chronological-lifelist-custom-page.py"))
    
    output_html = os.path.join(base_dir, "html", "photo_lifelist_growth.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    photos = chrono_mod.fetch_earliest_published_photos(cursor)
    species_list = []
    for k, v in photos.items():
        d = v.get("date")
        if d and d != "Unknown Date":
            species_list.append({
                "name": v["name"],
                "date": d,
                "location": v.get("location", "Unknown Location"),
                "url": v.get("url", ""),
                "photo_count": v.get("photo_count", 1)
            })
    species_list.sort(key=lambda x: (x["date"], x["name"]))
    
    summary, timeline = growth_mod.process_timeline(species_list)
    html_content = growth_mod.build_html(summary, timeline)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Growth chart dashboard generated: {output_html} ({summary['total_species']} species)")
    return output_html

def main():
    parser = argparse.ArgumentParser(
        description="Unified SmugMug & Lightroom Life Lists and Migration Dashboard CLI."
    )
    parser.add_argument("--all", action="store_true", help="Generate all reports and life lists (default behavior)")
    parser.add_argument("--dashboard", "--migration", action="store_true", help="Generate only the Migration & Publishing Dashboard")
    parser.add_argument("--lifelists", "--lists", action="store_true", help="Generate all 3 photo life lists (Alpha, Tax, Chrono)")
    parser.add_argument("--alphabetical", action="store_true", help="Generate only the Alphabetical Life List")
    parser.add_argument("--taxonomic", action="store_true", help="Generate only the Taxonomic Life List")
    parser.add_argument("--chronological", action="store_true", help="Generate only the Chronological Life List")
    parser.add_argument("--growth", "--chart", action="store_true", help="Generate only the Photographic Life List Growth Chart")
    parser.add_argument("--all-ebird", action="store_true", help="Include unphotographed eBird sightings in Chronological list")
    
    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine what tasks to run
    specific_flags = [args.dashboard, args.lifelists, args.alphabetical, args.taxonomic, args.chronological, args.growth]
    run_all = args.all or not any(specific_flags)
    
    do_dashboard = run_all or args.dashboard
    do_alpha = run_all or args.lifelists or args.alphabetical
    do_tax = run_all or args.lifelists or args.taxonomic
    do_chrono = run_all or args.lifelists or args.chronological
    do_growth = run_all or args.growth
    
    start_time = time.time()
    generated_outputs = []
    
    print("\n" + "="*70)
    print("🦅 UNIFIED SMUGMUG & LIGHTROOM BIRD REPORT PIPELINE")
    print("="*70)
    print("Connecting to Lightroom Catalog (single catalog session)...")
    
    with open_catalog() as cursor:
        if do_dashboard:
            out = run_migration_dashboard(cursor, base_dir)
            generated_outputs.append(("Migration Dashboard", out))
            
        if do_alpha:
            out = run_alphabetical_lifelist(cursor, base_dir)
            generated_outputs.append(("Alphabetical Life List", out))
            
        if do_tax:
            out = run_taxonomic_lifelist(cursor, base_dir)
            generated_outputs.append(("Taxonomic Life List", out))
            
        if do_chrono:
            out = run_chronological_lifelist(cursor, base_dir, show_all=args.all_ebird)
            generated_outputs.append(("Chronological Life List", out))
            
        if do_growth:
            out = run_growth_chart(cursor, base_dir)
            generated_outputs.append(("Photo Growth Chart", out))
            
    elapsed = time.time() - start_time
    
    print("\n" + "="*70)
    print(f"🎉 PIPELINE COMPLETED IN {elapsed:.2f}s")
    print("="*70)
    for title, out_path in generated_outputs:
        rel_path = os.path.relpath(out_path, base_dir)
        print(f"  • {title:30s} ➔ [{rel_path}](file://{os.path.abspath(out_path)})")
    
    index_path = os.path.join(base_dir, "index.html")
    if os.path.exists(index_path):
        print(f"\n🌐 Local Hub Portal: [index.html](file://{os.path.abspath(index_path)})")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
