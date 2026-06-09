#!/usr/bin/python3

import sqlite3
import shutil
import csv
import os

# --- CONFIGURATION ---
# Replace with your actual path
lrcat_path = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat" 
temp_db = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"
output_csv = "bird_migration_dashboard.csv"

# The Bird Taxonomy Root ID (from your genealogy)
BIRD_ROOT = "/41240/825689457%"

def run_dashboard():
    # 1. Create a temporary copy of the catalog
    if os.path.exists(temp_db):
        os.remove(temp_db)
    shutil.copy2(lrcat_path, temp_db)

    # 2. Connect to the database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # 3. The Dashboard Query
    query = f"""
    SELECT 
        i.colorLabels AS SpeciesName,
        COUNT(DISTINCT i.id_local) AS Total_With_This_Label,
        COUNT(DISTINCT ki.image) AS Total_With_Keyword,
        COUNT(DISTINCT pci.image) AS Total_On_SmugMug,
        (COUNT(DISTINCT i.id_local) - COUNT(DISTINCT ki.image)) AS Needs_Tagging
    FROM Adobe_images i
    -- Check for matching Keywords within the bird taxonomy tree
    LEFT JOIN AgLibraryKeyword k 
        ON i.colorLabels = k.name 
        AND k.genealogy LIKE '{BIRD_ROOT}'
    LEFT JOIN AgLibraryKeywordImage ki 
        ON i.id_local = ki.image AND k.id_local = ki.tag
    -- Check for SmugMug publishing via the self-joining table logic
    LEFT JOIN AgLibraryPublishedCollectionImage pci 
        ON i.id_local = pci.image
    LEFT JOIN AgLibraryPublishedCollection child_coll 
        ON pci.collection = child_coll.id_local
    LEFT JOIN AgLibraryPublishedCollection parent_coll 
        ON child_coll.parent = parent_coll.id_local 
        AND parent_coll.name LIKE '%SmugMug%'
    WHERE i.colorLabels != '' 
      AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
    GROUP BY i.colorLabels
    ORDER BY Needs_Tagging DESC, Total_With_This_Label DESC;
    """

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # 4. Save to CSV
        headers = [
            "Species Name (Label)", 
            "Total Photos", 
            "Has Taxonomic Keyword", 
            "Published to SmugMug", 
            "Mismatched/Needs Tagging"
        ]

        with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        print(f"✅ Success! Dashboard saved to: {output_csv}")
        print(f"Found {len(rows)} unique species labels to process.")

    except sqlite3.Error as e:
        print(f"❌ SQL Error: {e}")
    finally:
        conn.close()
        # Clean up the temp database
        if os.path.exists(temp_db):
            os.remove(temp_db)

if __name__ == "__main__":
    run_dashboard()