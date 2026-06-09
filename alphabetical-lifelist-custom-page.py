import sqlite3
import shutil
import os

# 1. Path Configuration
lrcat_path = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat"
temp_db = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"
output_html = "html/alphabetical_life_list.html"

# 2. Copy the DB (Prevents "Database Locked" error if LrC is open)
shutil.copy2(lrcat_path, temp_db)

# 3. Connect and Query
conn = sqlite3.connect(temp_db)
cursor = conn.cursor()

query = """
SELECT k.name, COUNT(DISTINCT i.id_local)
FROM AgLibraryKeyword k
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
WHERE k.genealogy LIKE "/41240/825689457%"
  AND parent_coll.name LIKE '%SmugMug%'
GROUP BY k.name
ORDER BY k.name ASC;
"""

cursor.execute(query)
results = cursor.fetchall()
conn.close()

# 4. Wrap in HTML and CSS
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
    <h1>Bill's Photo Life List ({len(results)} species)</h1>
    <ul class="species-grid">
"""

for name, count in results:
    url_name = name.replace(" ", "+")
    link = f'<li><a href="https://billwalker.smugmug.com/search/?q={url_name}">{name} ({count})</a></li>\n'
    html_content += link

html_content += "    </ul>\n</body>\n</html>"

# 5. Save to file
with open(output_html, "w") as f:
    f.write(html_content)

print(f"Success! {output_html} has been created.")