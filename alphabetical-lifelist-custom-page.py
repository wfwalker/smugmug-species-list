#!/usr/bin/python3

import os
from lrcat_utils import open_catalog, fetch_published_species

OUTPUT_HTML = "html/alphabetical_life_list.html"

def generate_html_content(results):
    """Generates HTML content utilizing the shared base template and partials."""
    # 1. Load layout template and partials
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "templates", "base_layout.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(base_dir, "templates", "row_simple.html"), "r", encoding="utf-8") as f:
        row_template = f.read()
    with open(os.path.join(base_dir, "templates", "row_letter_header.html"), "r", encoding="utf-8") as f:
        header_template = f.read()
        
    # 2. Build species list
    list_items = []
    current_letter = None
    for name, count in results:
        first_letter = name[0].upper()
        if first_letter != current_letter:
            current_letter = first_letter
            header_item = header_template.replace("{{ LETTER }}", current_letter)
            list_items.append("        " + header_item.strip())
            
        url_name = name.replace(" ", "+")
        search_link = f"https://billwalker.smugmug.com/search/?q={url_name}"
        row_item = (row_template
                    .replace("{{ LINK }}", search_link)
                    .replace("{{ NAME }}", name)
                    .replace("{{ COUNT }}", str(count)))
        list_items.append("        " + row_item.strip())
        
    content = '<ul class="species-grid">\n' + "\n".join(list_items) + '\n    </ul>'
    
    # 3. Page-specific CSS rules
    styles = """
        .species-grid { 
            column-count: 3; column-gap: 40px; 
            list-style: none; padding: 0; margin: 0;
        }
        .species-grid li { margin-bottom: 8px; break-inside: avoid; }
        .letter-heading { 
            font-size: 1.3em; 
            font-weight: bold; 
            margin-top: 20px; 
            margin-bottom: 10px; 
            border-bottom: 2px solid #444;
            padding-bottom: 4px;
            color: #fff;
            break-inside: avoid;
        }
        .letter-heading:first-child { margin-top: 0; }
        a { color: #4db8ff; }
        .sm-user-ui h3 { padding-bottom: 16px; padding-top: 8px; }
    """
    
    # 4. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Photo Life List")
    html = html.replace("{{ STATS_HEADER }}", f"({len(results)} species)")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html

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