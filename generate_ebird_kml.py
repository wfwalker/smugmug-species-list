#!/usr/bin/env python3
import csv
import os
import xml.sax.saxutils as saxutils

def generate_kml(workspace_root):
    ebird_path = os.path.join(workspace_root, "ebird.csv")
    output_kml = os.path.join(workspace_root, "reports", "ebird_hotspots.kml")
    
    if not os.path.exists(ebird_path):
        print("❌ Error: ebird.csv not found in the workspace root.")
        return
        
    print("Reading eBird sightings from ebird.csv...")
    
    # Aggregation dictionaries
    # loc_id -> {name, lat, lon, checklists: set, species: set, dates: list}
    location_data = {}
    
    with open(ebird_path, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print("❌ Error: ebird.csv is empty.")
            return
            
        # Dynamically locate columns
        loc_id_idx = -1
        name_idx = -1
        lat_idx = -1
        lon_idx = -1
        sub_id_idx = -1
        species_idx = -1
        date_idx = -1
        
        for i, col in enumerate(header):
            col_l = col.lower()
            if "location id" in col_l:
                loc_id_idx = i
            elif "location" in col_l:
                name_idx = i
            elif "latitude" in col_l:
                lat_idx = i
            elif "longitude" in col_l:
                lon_idx = i
            elif "submission" in col_l or "checklist" in col_l:
                sub_id_idx = i
            elif "common name" in col_l:
                species_idx = i
            elif "date" in col_l:
                date_idx = i
                
        # Validate critical columns
        if -1 in (loc_id_idx, name_idx, lat_idx, lon_idx, date_idx):
            print("❌ Error: Could not find required columns in ebird.csv header.")
            return
            
        for row in reader:
            if len(row) > max(loc_id_idx, name_idx, lat_idx, lon_idx, date_idx):
                loc_id = row[loc_id_idx].strip()
                name = row[name_idx].strip()
                lat_val = row[lat_idx].strip()
                lon_val = row[lon_idx].strip()
                date_val = row[date_idx].strip()
                
                # Checklists and species (fallbacks if index missing)
                sub_id = row[sub_id_idx].strip() if sub_id_idx != -1 and sub_id_idx < len(row) else ""
                species = row[species_idx].strip() if species_idx != -1 and species_idx < len(row) else ""
                
                if not (loc_id and name and lat_val and lon_val):
                    continue
                    
                try:
                    lat = float(lat_val)
                    lon = float(lon_val)
                except ValueError:
                    continue  # skip invalid coordinates
                    
                if loc_id not in location_data:
                    location_data[loc_id] = {
                        "name": name,
                        "lat": lat,
                        "lon": lon,
                        "checklists": set(),
                        "species": set(),
                        "dates": []
                    }
                    
                # Aggregate metrics
                if sub_id:
                    location_data[loc_id]["checklists"].add(sub_id)
                if species:
                    location_data[loc_id]["species"].add(species)
                if date_val:
                    location_data[loc_id]["dates"].append(date_val)
                    
    print(f"Aggregated {len(location_data)} unique locations. Generating KML...")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_kml), exist_ok=True)
    
    # Build KML XML
    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        '    <name>My eBird Locations Map</name>',
        '    <description>Visual map of hotspots and birding locations from ebird.csv</description>',
        '    <Style id="ebirdMarker">',
        '      <IconStyle>',
        '        <color>ff00aaff</color>',  # orange/yellow marker
        '        <scale>1.1</scale>',
        '        <Icon>',
        '          <href>http://maps.google.com/mapfiles/kml/paddle/orange-circle.png</href>',
        '        </Icon>',
        '        <hotSpot x="32" y="1" xunits="pixels" yunits="pixels"/>',
        '      </IconStyle>',
        '    </Style>'
    ]
    
    for loc_id, data in sorted(location_data.items(), key=lambda x: x[1]["name"]):
        esc_name = saxutils.escape(data["name"])
        visits = len(data["checklists"]) if data["checklists"] else 1
        species_count = len(data["species"])
        
        # Sort dates to find first and last visits
        sorted_dates = sorted(data["dates"])
        first_visit = sorted_dates[0] if sorted_dates else "Unknown"
        last_visit = sorted_dates[-1] if sorted_dates else "Unknown"
        
        description_cdata = f"""<![CDATA[
<div style="font-family: Arial, sans-serif; font-size: 13px; line-height: 1.5;">
  <h3 style="margin-top: 0; color: #2c3e50;">{esc_name}</h3>
  <table style="width: 100%; border-collapse: collapse;">
    <tr style="background: #f8f9fa;">
      <td style="padding: 4px; font-weight: bold; border-bottom: 1px solid #eee;">eBird Location ID:</td>
      <td style="padding: 4px; border-bottom: 1px solid #eee;">{loc_id}</td>
    </tr>
    <tr>
      <td style="padding: 4px; font-weight: bold; border-bottom: 1px solid #eee;">Total Checklists:</td>
      <td style="padding: 4px; border-bottom: 1px solid #eee;">{visits}</td>
    </tr>
    <tr style="background: #f8f9fa;">
      <td style="padding: 4px; font-weight: bold; border-bottom: 1px solid #eee;">Species Recorded:</td>
      <td style="padding: 4px; border-bottom: 1px solid #eee;">{species_count}</td>
    </tr>
    <tr>
      <td style="padding: 4px; font-weight: bold; border-bottom: 1px solid #eee;">First Visit:</td>
      <td style="padding: 4px; border-bottom: 1px solid #eee;">{first_visit}</td>
    </tr>
    <tr style="background: #f8f9fa;">
      <td style="padding: 4px; font-weight: bold; border-bottom: 1px solid #eee;">Last Visit:</td>
      <td style="padding: 4px; border-bottom: 1px solid #eee;">{last_visit}</td>
    </tr>
  </table>
  <p style="margin-bottom: 0; font-size: 11px; color: #7f8c8d; text-align: right;">Coordinates: {data['lat']:.5f}, {data['lon']:.5f}</p>
</div>
]]>"""

        kml_parts.append('    <Placemark>')
        kml_parts.append(f'      <name>{esc_name}</name>')
        kml_parts.append(f'      <description>{description_cdata}</description>')
        kml_parts.append('      <styleUrl>#ebirdMarker</styleUrl>')
        kml_parts.append('      <Point>')
        kml_parts.append(f'        <coordinates>{data["lon"]},{data["lat"]},0</coordinates>')
        kml_parts.append('      </Point>')
        kml_parts.append('    </Placemark>')
        
    kml_parts.append('  </Document>')
    kml_parts.append('</kml>')
    
    with open(output_kml, "w", encoding="utf-8") as f:
        f.write("\n".join(kml_parts))
        
    print(f"✅ Success! KML file saved to: {output_kml}")

if __name__ == "__main__":
    generate_kml("/Users/walker/Dropbox/smugmug-species-list")
