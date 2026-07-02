#!/usr/bin/python3

import os
import urllib.request
import json
from lrcat_utils import open_catalog, fetch_published_species

OUTPUT_HTML = "html/taxonomic_life_list.html"

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

def generate_html_content(results, smugmug_gallery_names):
    """Generates complete HTML content matching the original formatting and grouping logic exactly."""
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
        .letter-heading a {{ color: #fff; text-decoration: none; }}
        .letter-heading a:hover {{ text-decoration: underline; }}
        a {{ text-decoration: none; color: #4db8ff; }}
        a:hover {{ text-decoration: underline; }}
        .sm-user-ui h3 {{ padding-bottom: 16px; padding-top: 8px; }}
    </style>
</head>
<body>
    <h1>Bill's Taxonomic Photo Life List ({len(results)} species)</h1>
    <ul class="species-grid">
"""
    
    current_family = None
    
    for raw_family, species, count in results:
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
            html_content += f'        <li class="letter-heading"><a href="{family_link}">{gallery_name}</a></li>\n'
            current_family = hyphen_gallery
            
        url_name = species.replace(" ", "+")
        html_content += f'        <li><a href="https://billwalker.smugmug.com/search/?q={url_name}">{species} ({count})</a></li>\n'
        
    html_content += "    </ul>\n</body>\n</html>"
    return html_content

def main():
    # Ensure html directory exists
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        results = fetch_published_species(cursor)
        
    print("Fetching SmugMug galleries list...")
    smugmug_galleries = fetch_smugmug_galleries()
    
    print(f"Generating taxonomic lifelist custom page for {len(results)} species...")
    html_content = generate_html_content(results, smugmug_galleries)
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Success! {OUTPUT_HTML} has been created.")

if __name__ == "__main__":
    main()