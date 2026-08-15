import os
from lrcat_utils import make_relative_url

def generate_html_content(results, root_dir=None):
    """Generates HTML content utilizing the shared base template and partials."""
    if not root_dir:
        # Default to the project root directory
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    with open(os.path.join(root_dir, "templates", "base_layout.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(root_dir, "templates", "row_simple.html"), "r", encoding="utf-8") as f:
        row_template = f.read()
    with open(os.path.join(root_dir, "templates", "row_letter_header.html"), "r", encoding="utf-8") as f:
        header_template = f.read()
        
    # Build species list
    list_items = []
    current_letter = None
    for name, count, url in results:
        first_letter = name[0].upper()
        if first_letter != current_letter:
            current_letter = first_letter
            header_item = header_template.replace("{{ LETTER }}", current_letter)
            list_items.append("        " + header_item.strip())
            
        photo_url = make_relative_url(url)
        if count == 1 and photo_url:
            species_link = photo_url
        else:
            url_name = name.replace(" ", "+")
            species_link = f"/search/?q={url_name}"
            
        row_item = (row_template
                    .replace("{{ LINK }}", species_link)
                    .replace("{{ NAME }}", name)
                    .replace("{{ COUNT }}", str(count)))
        list_items.append("        " + row_item.strip())
        
    content = '<ul class="species-grid">\n' + "\n".join(list_items) + '\n    </ul>'
    
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
    
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Photo Life List")
    html = html.replace("{{ STATS_HEADER }}", f"({len(results)} species)")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html
