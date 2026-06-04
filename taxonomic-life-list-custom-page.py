import sqlite3
import shutil
import os
import urllib.request
import json

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
    "Southern-Storm-Petrels": "Storm-Petrels",
    "Asian-Barbets": "Toucans-and-Barbets",
    "New-World-Barbets": "Toucans-and-Barbets",
    "Toucan-Barbets": "Toucans-and-Barbets",
    "Toucans": "Toucans-and-Barbets",
    "Asian-and-Grauer's-Broadbills": "Broadbills",
    "Hawks-Eagles-and-Kites": "Birds-of-Prey",
    "Falcons-and-Caracaras": "Birds-of-Prey",
    "Osprey": "Birds-of-Prey",
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

# query smugmug API to find which bird family galleries we have right now

smugmug_api_key = os.getenv("SMUGMUG_API_KEY")

smugmug_galleries_query = f"""https://api.smugmug.com/api/v2/node/Rgm3dH!children?APIKey={smugmug_api_key}&count=100"""

smugmug_req = urllib.request.Request(smugmug_galleries_query)
smugmug_req.add_header('Accept', 'application/json')

smugmug_gallery_names = []

with urllib.request.urlopen(smugmug_req) as response:
    # Read response body and parse JSON string
    data = json.loads(response.read().decode())
    for gallery in data["Response"]["Node"]:
        smugmug_gallery_names.append(gallery["UrlName"])

print(f"""Found {len(smugmug_gallery_names)} SmugMug galleries""")
print(smugmug_gallery_names)

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
        .sm-user-ui h3 {{ padding-bottom: 16px; padding-top: 8px; }}
    </style>
</head>
<body>
    <h1>Bill's Taxonomic Photo Life List ({len(results)} species)</h1>
    <ul class="species-grid">
"""


# iterate through all the species in taxonomic order
# for each one we have a family name, species name and photo count
for raw_family, species, count in results:
    # by default we'll use the eBird family name with hyphens as the family gallery URL
    gallery_name = raw_family
    raw_family_with_hypens = raw_family.replace(' ', '-')
    hyphen_gallery = raw_family_with_hypens

    # we have a few galleries that don't follow the eBird family names
    # for those, we have a custom mapping here from eBird family hyphen name to Bill hyphen gallery name
    if raw_family_with_hypens in gallery_mapping:
        hyphen_gallery = gallery_mapping[raw_family_with_hypens]
        gallery_name = hyphen_gallery.replace('-', ' ')

    # If we hit a new family, close the previous list and start a new one
    # TODO -- UHOH not all the species in a given gallery are contiguous in the sort.
    if hyphen_gallery != current_family:
        if current_family is not None:
            html_content += "</ul>\n"

        if hyphen_gallery not in smugmug_gallery_names:
            print(f"""unknown family gallery name {hyphen_gallery}""")

        family_link = "https://billwalker.smugmug.com/Bird-Families/" + hyphen_gallery

        html_content += f'<h3><a href="{family_link}">{gallery_name}</a></h3>\n<ul>\n'
        current_family = hyphen_gallery
    
    url_name = species.replace(" ", "+")
    html_content += f'  <li><a href="https://billwalker.smugmug.com/search/?q={url_name}">{species} ({count})</a></li>\n'

html_content += "    </ul>\n</body>\n</html>"

conn.close()

# 5. Save to file
with open(output_html, "w") as f:
    f.write(html_content)

print(f"Success! {output_html} has been created.")