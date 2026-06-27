#!/usr/bin/python3

import sqlite3
import shutil
import csv
import json
import os

# --- CONFIGURATION ---
# Replace with your actual path
lrcat_path = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat" 
temp_db = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"
output_csv = "bird_migration_dashboard.csv"

# The Bird Taxonomy Root ID (from your genealogy)
BIRD_ROOT = "/41240/825689457%"

def run_dashboard():
    # 0. Load JSON file if available
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "photos-ebird-mybird.json")
    
    json_species = set()
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                json_species = {item["Common Name"] for item in json_data if "Common Name" in item}
        except Exception as e:
            print(f"⚠️ Error loading JSON file: {e}")
    else:
        print(f"⚠️ Warning: JSON file not found at {json_path}")

    # 1. Create a temporary copy of the catalog
    if os.path.exists(temp_db):
        os.remove(temp_db)
    shutil.copy2(lrcat_path, temp_db)

    # 2. Connect to the database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # 3. Queries to gather statistics
    
    # Query A: Label-based statistics (Legacy color label info)
    query_label = f"""
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
    query_keyword = f"""
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
    query_published = f"""
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

    try:
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

        # 4. Merge results in Python
        # The union of all species names in legacy labels and the JSON list
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

        # 5. Save to CSV
        headers = [
            "Species Name", 
            "In JSON List", 
            "Total Photos (Label)", 
            "Has Taxonomic Keyword", 
            "Published to SmugMug", 
            "Mismatched/Needs Tagging"
        ]

        with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
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

        # Summary statistics
        json_unpublished_count = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
        total_needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
        
        print(f"✅ Success! Dashboard saved to: {output_csv}")
        print(f"Total species in dashboard: {len(merged_rows)}")
        print(f"Species in JSON list: {len(json_species)}")
        print(f"❌ JSON species NOT yet published to SmugMug: {json_unpublished_count}")
        print(f"⚠️ Species needing Lightroom taxonomy tagging: {total_needs_tagging_count}")

    except sqlite3.Error as e:
        print(f"❌ SQL Error: {e}")
    finally:
        conn.close()
        # Clean up the temp database
        if os.path.exists(temp_db):
            os.remove(temp_db)

if __name__ == "__main__":
    run_dashboard()