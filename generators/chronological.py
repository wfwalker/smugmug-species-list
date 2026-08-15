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
        .chrono-year-group {
            margin-bottom: 40px;
        }
        .chrono-year-heading {
            font-size: 1.8em;
            font-weight: bold;
            color: #ff9f43;
            border-bottom: 2px solid #332115;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }
        .chrono-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        .chrono-card {
            background-color: #111;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .chrono-card.text-only {
            padding: 16px 20px;
            border-left: 4px solid #555;
            min-height: 100px;
            justify-content: center;
        }
        .chrono-img-container {
            width: 100%;
            height: 180px;
            background-color: #0b0b0b;
            overflow: hidden;
            position: relative;
            border-bottom: 1px solid #1a1a1a;
        }
        .chrono-img-container img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease;
        }
        .chrono-img-container:hover img {
            transform: scale(1.05);
        }
        .chrono-card-content {
            padding: 16px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .chrono-species-name {
            font-weight: bold;
            font-size: 1.15em;
            margin: 0;
        }
        .chrono-species-name a {
            color: #fff;
            text-decoration: none;
        }
        .chrono-species-name a:hover {
            color: #4db8ff;
        }
        .chrono-meta-label {
            font-size: 0.75em;
            text-transform: uppercase;
            color: #666;
            font-weight: bold;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        }
        .chrono-meta-val {
            font-size: 0.85em;
            color: #ccc;
            margin: 0;
        }
        .chrono-photo-meta {
            border-bottom: 1px solid #1a1a1a;
            padding-bottom: 8px;
            margin-bottom: 4px;
        }
        .chrono-sighting-meta {
            padding-top: 4px;
        }
        .text-date {
            font-weight: bold;
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 4px;
        }
        .text-species {
            font-size: 1.2em;
            font-weight: bold;
            color: #fff;
            margin-top: 0;
            margin-bottom: 8px;
        }
        .text-loc {
            font-size: 0.85em;
            color: #888;
            margin: 0;
        }
    """
    
    # 4. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bill's Chronological Photo Life List")
    html = html.replace("{{ HEADER_TITLE }}", "Bill's Chronological Photo Life List")
    html = html.replace("{{ STATS_HEADER }}", f"({total_seen_count} species seen, {len(chronological_data)} years)")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content)
    
    return html
