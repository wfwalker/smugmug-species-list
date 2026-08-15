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
from collections import defaultdict

from lib.lrcat_utils import open_catalog, make_relative_url
from lib.shared_queries import (
    query_alphabetical_species,
    query_taxonomic_species,
    query_chronological_photos
)
from lib.dashboard_pipeline import run_migration_dashboard_pipeline
from lib.dashboard_parser import parse_ebird_earliest_sightings

import generators.alphabetical
import generators.taxonomic
import generators.chronological
import generators.growth_chart

def run_migration_dashboard(cursor, base_dir):
    print("\n" + "="*60)
    print("🚀 [1/5] Building Migration & Publishing Dashboard...")
    print("="*60)
    return run_migration_dashboard_pipeline(cursor, base_dir)

def run_alphabetical_lifelist(cursor, base_dir):
    print("\n" + "="*60)
    print("🔤 [2/5] Building Alphabetical Photo Life List...")
    print("="*60)
    
    output_html = os.path.join(base_dir, "html", "alphabetical_life_list.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    results = query_alphabetical_species(cursor)
    html_content = generators.alphabetical.generate_html_content(results, root_dir=base_dir)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Alphabetical life list generated: {output_html} ({len(results)} species)")
    return output_html

def run_taxonomic_lifelist(cursor, base_dir):
    print("\n" + "="*60)
    print("🌿 [3/5] Building Taxonomic Photo Life List...")
    print("="*60)
    
    output_html = os.path.join(base_dir, "html", "taxonomic_life_list.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    results = query_taxonomic_species(cursor)
    smugmug_galleries = generators.taxonomic.fetch_smugmug_galleries()
    html_content = generators.taxonomic.generate_html_content(results, smugmug_galleries, root_dir=base_dir)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Taxonomic life list generated: {output_html} ({len(results)} species)")
    return output_html

def run_chronological_lifelist(cursor, base_dir, show_all=False):
    print("\n" + "="*60)
    print("📅 [4/5] Building Chronological Photo Life List...")
    print("="*60)
    
    output_html = os.path.join(base_dir, "html", "chronological_life_list.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    ebird_csv = os.path.join(base_dir, "ebird.csv")
    ebird_sightings = parse_ebird_earliest_sightings(ebird_csv)
    published_photos = query_chronological_photos(cursor)
    
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
            
        # Parse year for grouping (based on photo date if available, else ebird date)
        sort_date = photo_info["date"] if photo_info else date_str
        try:
            year = sort_date.split("-")[0]
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
            
    # Sort sightings within each year by photo date descending (latest photographed first)
    for year in chronological_data:
        chronological_data[year].sort(
            key=lambda x: (x["photo"]["date"] if x["photo"] else x["ebird_date"], x["name"]),
            reverse=True
        )
        
    total_seen_count = len(ebird_sightings) + unmatched_count
    html_content = generators.chronological.generate_html_content(chronological_data, total_seen_count, root_dir=base_dir)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Chronological life list generated: {output_html}")
    return output_html

def run_growth_chart(cursor, base_dir):
    print("\n" + "="*60)
    print("📈 [5/5] Building Photographic Species Life List Growth Chart...")
    print("="*60)
    
    output_html = os.path.join(base_dir, "html", "photo_lifelist_growth.html")
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    photos = query_chronological_photos(cursor)
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
    
    summary, timeline = generators.growth_chart.process_timeline(species_list)
    html_content = generators.growth_chart.build_html(summary, timeline)
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    # Also write static SVG chart
    svg_content = generators.growth_chart.build_svg(summary, timeline)
    output_svg = os.path.join(os.path.dirname(output_html), "photo_growth_chart.svg")
    with open(output_svg, "w", encoding="utf-8") as f:
        f.write(svg_content)
        
    print(f"✅ Growth chart dashboard generated: {output_html} ({summary['total_species']} species)")
    print(f"✅ Static SVG chart generated: {output_svg}")
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
            
        if do_growth:
            out = run_growth_chart(cursor, base_dir)
            generated_outputs.append(("Photo Growth Chart", out))
            
        if do_alpha:
            out = run_alphabetical_lifelist(cursor, base_dir)
            generated_outputs.append(("Alphabetical Life List", out))
            
        if do_tax:
            out = run_taxonomic_lifelist(cursor, base_dir)
            generated_outputs.append(("Taxonomic Life List", out))
            
        if do_chrono:
            out = run_chronological_lifelist(cursor, base_dir, show_all=args.all_ebird)
            generated_outputs.append(("Chronological Life List", out))
            
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
