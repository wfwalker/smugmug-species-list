import sqlite3
import shutil
import os

# 1. Path Configuration
lrcat_path = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat"
temp_db = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"
output_html = "taxonomic_life_list.html"

# 2. Copy the DB (Prevents "Database Locked" error if LrC is open)
shutil.copy2(lrcat_path, temp_db)

# 3. Connect and Query
conn = sqlite3.connect(temp_db)
cursor = conn.cursor()

# When I created the smugmug smart galleries by hand I shortened some of the names
# we need to capture those here.

gallery_mapping = {
    "Vireos-Shrike-Babblers-and-Erpornis": "Vireos-and-Allies",
}

query = """
SELECT 
    parent_k.name AS FamilyGroup,
    k.name AS SpeciesName,
    COUNT(DISTINCT i.id_local) AS SpeciesCount
FROM AgLibraryKeyword k
-- Join to find the parent (Family/Group)
JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
-- Link to images and SmugMug as before
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
WHERE k.genealogy LIKE "/41240/825689457%"
  AND parent_coll.name LIKE '%SmugMug%'
  -- Ensure we are only getting species (not the scientific names or the groups themselves)
  -- This assumes your species are exactly 2 levels deep from the bird root
  AND k.name NOT LIKE '{%' 
GROUP BY k.name
ORDER BY parent_k.id_local, k.id_local;
"""

cursor.execute(query)
results = cursor.fetchall()
current_family = None

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; padding: 40px; }}
        .species-grid {{ 
            column-count: 3; column-gap: 40px; 
            list-style: none; padding: 0; 
        }}
        .species-grid li {{ margin-bottom: 8px; break-inside: avoid; }}
        a {{ text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Bill's Taxonomic Photo Life List ({len(results)} species)</h1>
    <ul class="species-grid">
"""

for family, species, count in results:
    # If we hit a new family, close the previous list and start a new one
    if family != current_family:
        if current_family is not None:
            html_content += "</ul>\n"

        # family link is family name with hyphens, run through the mapping
        family_with_hypens = family.replace(' ', '-')
        if family_with_hypens in gallery_mapping:
            family_with_hypens = gallery_mapping[family_with_hypens]
        family_link = "https://billwalker.smugmug.com/Bird-Families/" + family_with_hypens

        html_content += f'<h3><a href="{family_link}">{family}</a></h3>\n<ul>\n'
        current_family = family
    
    url_name = species.replace(" ", "+")
    html_content += f'  <li><a href="https://billwalker.smugmug.com/search/?q={url_name}">{species} ({count})</a></li>\n'

html_content += "    </ul>\n</body>\n</html>"

conn.close()

# 5. Save to file
with open(output_html, "w") as f:
    f.write(html_content)

print(f"Success! {output_html} has been created.")