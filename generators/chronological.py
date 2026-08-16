import os
from lib.lrcat_utils import make_relative_url

def generate_html_content(chronological_data, total_seen_count, root_dir=None):
    """Generates HTML content utilizing the shared base template and partials."""
    if not root_dir:
        # Default to the project root directory
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    # 1. Load layout template and partials
    with open(os.path.join(root_dir, "templates", "base_layout.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(root_dir, "templates", "chronological_section.html"), "r", encoding="utf-8") as f:
        section_template = f.read()
    with open(os.path.join(root_dir, "templates", "chronological_row_photo.html"), "r", encoding="utf-8") as f:
        row_photo_template = f.read()
    with open(os.path.join(root_dir, "templates", "chronological_row_text.html"), "r", encoding="utf-8") as f:
        row_text_template = f.read()

    # 2. Build grid content
    content_sections = []
    sorted_years = sorted(chronological_data.keys(), reverse=True)
    
    for year in sorted_years:
        row_items = []
        for item in chronological_data[year]:
            species_name = item["name"]
            ebird_date = item["ebird_date"]
            ebird_loc = item["ebird_location"]
            photo = item["photo"]
            
            if photo:
                photo_url = make_relative_url(photo.get("url"))
                
                # Check link type
                if photo.get("photo_count", 0) == 1 and photo_url:
                    species_link = photo_url
                else:
                    url_name = species_name.replace(" ", "+")
                    species_link = f"/search/?q={url_name}"
                    
                photo_link = make_relative_url(photo["url"])
                # Only show eBird date/location if it differs from the photo date
                if ebird_date != photo["date"]:
                    sighting_info = f"Seen {ebird_date} @ {ebird_loc}"
                else:
                    sighting_info = '<span style="color: #444;">—</span>'
                    
                row_item = (row_photo_template
                            .replace("{{ SPECIES_LINK }}", species_link)
                            .replace("{{ SPECIES_NAME }}", species_name)
                            .replace("{{ PHOTO_LINK }}", photo_link)
                            .replace("{{ PHOTO_DATE }}", photo["date"])
                            .replace("{{ PHOTO_LOCATION }}", photo["location"])
                            .replace("{{ SIGHTING_INFO }}", sighting_info))
            else:
                row_item = (row_text_template
                            .replace("{{ DATE }}", ebird_date)
                            .replace("{{ SPECIES_NAME }}", species_name)
                            .replace("{{ SIGHTING_LOCATION }}", ebird_loc))
            row_items.append("            " + row_item.strip())
            
        # Combine section template
        section_html = (section_template
                        .replace("{{ YEAR }}", year)
                        .replace("{{ ROWS }}", "\n".join(row_items)))
        content_sections.append(section_html)
        
    content = "\n".join(content_sections)
    
    # 3. Page-specific CSS rules
    styles = """
        .year-section { margin-bottom: 50px; }
        .year-heading { 
            font-size: 1.8em; 
            font-weight: bold; 
            margin-top: 40px; 
            margin-bottom: 20px; 
            border-bottom: 2px solid #ff9f43;
            padding-bottom: 8px;
            color: #fff;
        }
        .timeline-table {
            display: grid;
            grid-template-columns: 120px 1.2fr 1.5fr 1.8fr;
            gap: 1px;
            background-color: #222;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
        }
        .table-header {
            background-color: #1a1a1a;
            color: #fff;
            font-weight: bold;
            padding: 14px 18px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border-bottom: 2px solid #333;
        }
        .table-row {
            display: contents; /* Allows grid alignment */
        }
        .table-cell {
            background-color: #131313;
            padding: 14px 18px;
            font-size: 0.95em;
            border-bottom: 1px solid #1a1a1a;
            line-height: 1.4;
            display: flex;
            align-items: center;
        }
        .table-row:hover .table-cell {
            background-color: #1d1d1d;
        }
        .date-cell {
            font-family: monospace;
            font-size: 1.05em;
            color: #ff9f43; /* Warm orange to emphasize dates */
            font-weight: bold;
            white-space: nowrap;
        }
        .species-cell {
            font-weight: 500;
        }
        .species-link { color: #4db8ff; text-decoration: none; }
        .species-link:hover { text-decoration: underline; }
        .species-text { color: #aaa; font-weight: normal; }
        
        .photo-cell {
            color: #ccc;
        }
        .photo-link {
            color: #00fa9a;
            text-decoration: none;
            font-weight: 500;
        }
        .photo-link:hover {
            text-decoration: underline;
        }
        .location-cell {
            color: #ccc;
        }
    """
    
    # 4. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Chronological Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Chronological Photo Life List")
    total_photographed = sum(
        1 for species_list in chronological_data.values() 
        for s in species_list if s.get("photo")
    )
    html = html.replace("{{ STATS_HEADER }}", f"({total_photographed} species)")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html
