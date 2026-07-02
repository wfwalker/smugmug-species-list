#!/usr/bin/python3

import os
from lrcat_utils import open_catalog, fetch_published_species

OUTPUT_HTML = "html/alphabetical_life_list.html"

def generate_html_content(results):
    """Generates complete HTML content matching the original formatting exactly."""
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; padding: 40px; background-color: #111; color: #eee; }}
        .species-grid {{ 
            column-count: 3; column-gap: 40px; 
            list-style: none; padding: 0; 
        }}
        .species-grid li {{ margin-bottom: 8px; break-inside: avoid; }}
        .letter-heading {{ 
            font-size: 1.3em; 
            font-weight: bold; 
            margin-top: 20px; 
            margin-bottom: 10px; 
            border-bottom: 2px solid #444;
            padding-bottom: 4px;
            color: #fff;
            break-inside: avoid;
        }}
        .letter-heading:first-child {{ margin-top: 0; }}
        a {{ text-decoration: none; color: #4db8ff; }}
        a:hover {{ text-decoration: underline; }}
        .sm-user-ui h3 {{ padding-bottom: 16px; padding-top: 8px; }}
    </style>
</head>
<body>
    <h1>Bill's Photo Life List ({len(results)} species)</h1>
    <ul class="species-grid">
"""
    current_letter = None
    for name, count in results:
        first_letter = name[0].upper()
        if first_letter != current_letter:
            current_letter = first_letter
            html_content += f'        <li class="letter-heading">{current_letter}</li>\n'
            
        url_name = name.replace(" ", "+")
        html_content += f'        <li><a href="https://billwalker.smugmug.com/search/?q={url_name}">{name} ({count})</a></li>\n'
        
    html_content += "    </ul>\n</body>\n</html>"
    return html_content

def main():
    # Ensure html directory exists
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        raw_results = fetch_published_species(cursor)
        
    # Extract (SpeciesName, SpeciesCount) and sort alphabetically
    results = [(row[1], row[2]) for row in raw_results]
    results.sort(key=lambda x: x[0])
        
    print(f"Generating alphabetical lifelist custom page for {len(results)} species...")
    html_content = generate_html_content(results)
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Success! {OUTPUT_HTML} has been created.")

if __name__ == "__main__":
    main()