import os
import sys
import json
import urllib.request
from lrcat_utils import make_relative_url

def fetch_smugmug_galleries():
    """Queries SmugMug API to get currently active bird family gallery UrlNames."""
    smugmug_api_key = os.getenv("SMUGMUG_API_KEY")
    if not smugmug_api_key:
        print("⚠️ Warning: SMUGMUG_API_KEY environment variable is not set. SmugMug gallery existence checks will be skipped.")
        return []
        
    url = f"https://api.smugmug.com/api/v2/node/Rgm3dH!children?APIKey={smugmug_api_key}&count=100"
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            galleries = [gallery["UrlName"] for gallery in data["Response"]["Node"]]
            print(f"Successfully loaded {len(galleries)} galleries from SmugMug API.")
            return galleries
    except Exception as e:
        print(f"⚠️ Error calling SmugMug API: {e}")
        return []

def generate_html_content(results, smugmug_gallery_names, root_dir=None):
    """Generates HTML content utilizing the shared base template and partials."""
    if not root_dir:
        # Default to the project root directory
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    with open(os.path.join(root_dir, "templates", "base_layout.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(root_dir, "templates", "row_simple.html"), "r", encoding="utf-8") as f:
        row_template = f.read()
    with open(os.path.join(root_dir, "templates", "row_family_header.html"), "r", encoding="utf-8") as f:
        family_template = f.read()
        
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
    
    list_items = []
    current_family = None
    
    for raw_family, species, count, url in results:
        # eBird family name with hyphens by default
        gallery_name = raw_family
        raw_family_with_hyphens = raw_family.replace(' ', '-')
        hyphen_gallery = raw_family_with_hyphens
        
        # custom mapping checks
        if raw_family_with_hyphens in gallery_mapping:
            hyphen_gallery = gallery_mapping[raw_family_with_hyphens]
            gallery_name = hyphen_gallery.replace('-', ' ')
            
        if hyphen_gallery != current_family:
            if smugmug_gallery_names and hyphen_gallery not in smugmug_gallery_names:
                print(f"unknown family gallery name {hyphen_gallery}")
                
            family_link = "https://billwalker.smugmug.com/Bird-Families/" + hyphen_gallery
            family_item = (family_template
                           .replace("{{ LINK }}", family_link)
                           .replace("{{ NAME }}", gallery_name))
            list_items.append("        " + family_item.strip())
            current_family = hyphen_gallery
            
        photo_url = make_relative_url(url)
        if count == 1 and photo_url:
            species_link = photo_url
        else:
            url_name = species.replace(" ", "+")
            species_link = f"/search/?q={url_name}"
            
        row_item = (row_template
                    .replace("{{ LINK }}", species_link)
                    .replace("{{ NAME }}", species)
                    .replace("{{ COUNT }}", str(count)))
        list_items.append("        " + row_item.strip())
        
    content = '<ul class="species-grid">\n' + "\n".join(list_items) + '\n    </ul>'
    
    styles = """
        .species-grid { 
            column-count: 3; column-gap: 40px; 
            list-style: none; padding: 0; margin: 0;
        }
        .species-grid li { margin-bottom: 8px; break-inside: avoid; }
        .family-heading { 
            font-size: 1.3em; 
            font-weight: bold; 
            margin-top: 20px; 
            margin-bottom: 10px; 
            border-bottom: 2px solid #444;
            padding-bottom: 4px;
            break-inside: avoid;
        }
        .family-heading:first-child { margin-top: 0; }
        a { color: #4db8ff; }
        .sm-user-ui h3 { padding-bottom: 16px; padding-top: 8px; }
    """
    
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Taxonomic Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Taxonomic Photo Life List")
    html = html.replace("{{ STATS_HEADER }}", f"({len(results)} species)")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html
