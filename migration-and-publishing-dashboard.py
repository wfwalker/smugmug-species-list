#!/usr/bin/python3

import csv
import json
import os
from lrcat_utils import open_catalog, BIRD_ROOT

REPORTS_DIR = "reports"
OUTPUT_CSV = os.path.join(REPORTS_DIR, "bird_migration_dashboard.csv")
OUTPUT_MD = os.path.join(REPORTS_DIR, "bird_migration_dashboard.md")

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

def fetch_db_statistics(cursor):
    """
    Queries the database and returns:
    - label_stats: dict of label -> {total_label, keyword_on_label, needs_tagging}
    - keyword_stats: dict of keyword -> count
    - published_stats: dict of species -> published_count
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

    return label_stats, keyword_stats, published_stats

def generate_report(label_stats, keyword_stats, published_stats, json_species):
    """Merges all sources into a unified list of species dicts, sorted in priority order."""
    all_species = set(label_stats.keys()).union(json_species)

    merged_rows = []
    for species in all_species:
        in_json = "Yes" if species in json_species else "No"
        
        l_stats = label_stats.get(species, {})
        total_label = l_stats.get("total_label", 0)
        needs_tagging = l_stats.get("needs_tagging", 0)
        
        total_keyword = keyword_stats.get(species, 0)
        published_count = published_stats.get(species, 0)
        
        merged_rows.append({
            "species_name": species,
            "in_json": in_json,
            "total_label": total_label,
            "total_keyword": total_keyword,
            "published_count": published_count,
            "needs_tagging": needs_tagging
        })

    # Sorting logic:
    # 1. Species in JSON but not published to SmugMug first (high priority action item)
    # 2. Species that need tagging (needs_tagging > 0)
    # 3. Total label photos descending
    # 4. Species name alphabetical
    def sort_key(item):
        is_json_unpublished = 1 if (item["in_json"] == "Yes" and item["published_count"] == 0) else 0
        return (-is_json_unpublished, -item["needs_tagging"], -item["total_label"], item["species_name"])

    merged_rows.sort(key=sort_key)
    return merged_rows

def save_to_csv(output_path, merged_rows):
    """Writes the dashboard report rows to a CSV file."""
    headers = [
        "Species Name", 
        "In JSON List", 
        "Total Photos (Label)", 
        "Has Taxonomic Keyword", 
        "Published to SmugMug", 
        "Mismatched/Needs Tagging"
    ]

    with open(output_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in merged_rows:
            writer.writerow([
                r["species_name"],
                r["in_json"],
                r["total_label"],
                r["total_keyword"],
                r["published_count"],
                r["needs_tagging"]
            ])

def save_to_markdown(output_path, merged_rows):
    """Writes the dashboard report rows to a Markdown file."""
    headers = [
        "Species Name", 
        "In JSON List", 
        "Total Photos (Label)", 
        "Has Taxonomic Keyword", 
        "Published to SmugMug", 
        "Mismatched/Needs Tagging"
    ]
    
    lines = []
    lines.append("# Bird Migration & Publishing Dashboard")
    lines.append(f"Generated on: {os.popen('date').read().strip()}\n")
    
    # Summary statistics
    total_species = len(merged_rows)
    json_unpublished = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
    needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
    
    lines.append("## Summary Statistics")
    lines.append(f"- **Total Species in Dashboard**: {total_species}")
    lines.append(f"- **Species Needing Lightroom Tagging**: {needs_tagging_count}")
    lines.append(f"- **JSON Species NOT Yet Published to SmugMug**: {json_unpublished}\n")
    
    # Table headers
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    for r in merged_rows:
        row_parts = [
            r["species_name"],
            r["in_json"],
            str(r["total_label"]),
            str(r["total_keyword"]),
            str(r["published_count"]),
            str(r["needs_tagging"])
        ]
        lines.append("| " + " | ".join(row_parts) + " |")
        
    with open(output_path, mode='w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "photos-ebird-mybird.json")
    
    print("Loading species from JSON list...")
    json_species = load_json_species(json_path)

    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        label_stats, keyword_stats, published_stats = fetch_db_statistics(cursor)

    print("Processing and merging statistics...")
    merged_rows = generate_report(label_stats, keyword_stats, published_stats, json_species)

    print("Saving dashboard report...")
    # Create reports directory if it doesn't exist
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    save_to_csv(OUTPUT_CSV, merged_rows)
    save_to_markdown(OUTPUT_MD, merged_rows)

    # Print summary statistics
    json_unpublished_count = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
    total_needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
    
    print(f"✅ Success! Reports saved under the '{REPORTS_DIR}/' subfolder:")
    print(f"   • CSV: {OUTPUT_CSV}")
    print(f"   • MD:  {OUTPUT_MD}")
    print(f"\nTotal species in dashboard: {len(merged_rows)}")
    print(f"Species in JSON list: {len(json_species)}")
    print(f"❌ JSON species NOT yet published to SmugMug: {json_unpublished_count}")
    print(f"⚠️ Species needing Lightroom taxonomy tagging: {total_needs_tagging_count}")

if __name__ == "__main__":
    main()