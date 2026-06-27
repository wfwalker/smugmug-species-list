#!/usr/bin/python3

import os
from lrcat_utils import open_catalog, BIRD_ROOT

OUTPUT_HTML = "html/alphabetical_life_list.html"

def fetch_alphabetical_list(cursor):
    """Queries the database to fetch alphabetical list of published species."""
    query = """
    SELECT k.name, COUNT(DISTINCT i.id_local)
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
    JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
    JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
    WHERE k.genealogy LIKE ?
      AND parent_coll.name LIKE '%SmugMug%'
    GROUP BY k.name
    ORDER BY k.name ASC;
    """
    cursor.execute(query, (BIRD_ROOT,))
    return cursor.fetchall()

def generate_html_content(results):
    """Generates complete HTML content matching the original formatting exactly."""
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
        html_content += f'<li><a href="https://billwalker.smugmug.com/search/?q={url_name}">{name} ({count})</a></li>\n'
        
    html_content += "    </ul>\n</body>\n</html>"
    return html_content

def main():
    # Ensure html directory exists
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        results = fetch_alphabetical_list(cursor)
        
    print(f"Generating alphabetical lifelist custom page for {len(results)} species...")
    html_content = generate_html_content(results)
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Success! {OUTPUT_HTML} has been created.")

if __name__ == "__main__":
    main()