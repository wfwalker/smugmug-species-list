#!/usr/bin/python3

import os
import sys
import urllib.request
import json
from lrcat_utils import open_catalog, BIRD_ROOT

OUTPUT_HTML = "html/taxonomic_life_list.html"

def make_relative_url(url):
    """Converts absolute SmugMug URLs into site-relative paths to optimize HTML size."""
    if not url:
        return ""
    for domain in ["https://billwalker.smugmug.com", "https://www.birdwalker.com"]:
        if url.startswith(domain):
            return url[len(domain):]
    return url

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
    """Generates HTML content utilizing the shared base template and partials."""
    # 1. Load layout template and partials
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "templates", "base_layout.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(base_dir, "templates", "row_simple.html"), "r", encoding="utf-8") as f:
        row_template = f.read()
    with open(os.path.join(base_dir, "templates", "row_family_header.html"), "r", encoding="utf-8") as f:
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
    
    # 2. Build species list
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
        .letter-heading a { color: #fff; text-decoration: none; }
        .letter-heading a:hover { text-decoration: underline; }
        a { color: #4db8ff; }
        .sm-user-ui h3 { padding-bottom: 16px; padding-top: 8px; }
    """
    
    # 4. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Taxonomic Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Taxonomic Photo Life List")
    html = html.replace("{{ STATS_HEADER }}", f"({len(results)} species)")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html

def main():
    # Ensure html directory exists
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    query = """
    WITH RankedPhotos AS (
        SELECT 
            parent_k.id_local AS FamilyId,
            k.id_local AS SpeciesId,
            parent_k.name AS FamilyGroup,
            k.name AS SpeciesName,
            rp.url AS SmugMugUrl,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.url LIKE '%smugmug.com%'
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        FamilyGroup,
        SpeciesName,
        photo_count,
        SmugMugUrl
    FROM RankedPhotos
    WHERE rn = 1
    ORDER BY FamilyId, SpeciesId;
    """
    
    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        cursor.execute(query, (BIRD_ROOT,))
        results = cursor.fetchall()
        
    print("Fetching SmugMug galleries list...")
    smugmug_galleries = fetch_smugmug_galleries()
    
    print(f"Generating taxonomic lifelist custom page for {len(results)} species...")
    html_content = generate_html_content(results, smugmug_galleries)
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"✅ Success! {OUTPUT_HTML} has been created.")

if __name__ == "__main__":
    main()