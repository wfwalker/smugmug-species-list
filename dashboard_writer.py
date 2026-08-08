import os
import csv
from audit_taxonomy_migration import RENAME_MAPS_LOWER, LUMP_MAPS_LOWER, SPLIT_MAPS_LOWER
from dashboard_resolver import normalize_name, SYNONYMS

def save_to_csv(output_path, merged_rows):
    """Writes the dashboard report rows to a CSV file."""
    headers = [
        "Species Name", 
        "In JSON List", 
        "In eBird", 
        "Total Photos (Label)", 
        "Has Taxonomic Keyword", 
        "Published to SmugMug", 
        "Mismatched/Needs Tagging",
        "Photos Missing Location"
    ]
    
    with open(output_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in merged_rows:
            writer.writerow([
                r["species_name"],
                r["in_json"],
                r["in_ebird"],
                r["total_label"],
                r["total_keyword"],
                r["published_count"],
                r["needs_tagging"],
                r["missing_loc_count"]
            ])

def save_to_html(output_path, merged_rows, photos_missing_location, earliest_photos, migration_items, split_details_by_species, auto_recs, normalized_v2025, ebird_locs, needs_tagging_examples):
    """Writes the unified species-centric dashboard report to an HTML file."""
    base_dir = os.path.dirname(__file__)
    
    # 1. Load layout template
    layout_path = os.path.join(base_dir, "templates", "base_layout.html")
    with open(layout_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 2. Parse stats to generate summary card details
    total_dashboard_species = len(merged_rows)
    json_count = sum(1 for r in merged_rows if r["in_json"] == "Yes")
    ebird_count = sum(1 for r in merged_rows if r["in_ebird"] == "Yes")
    invalid_taxonomy_count = sum(1 for r in merged_rows if r["is_valid_taxonomy"] == "No")
    needs_tagging_count = sum(1 for r in merged_rows if r["needs_tagging"] > 0)
    missing_loc_count = sum(1 for r in merged_rows if r["missing_loc_count"] > 0)
    json_unpublished_count = sum(1 for r in merged_rows if r["in_json"] == "Yes" and r["published_count"] == 0)
    published_not_ebird = sum(1 for r in merged_rows if r["published_count"] > 0 and r["in_ebird"] == "No")

    # 3. Load summary template and render
    summary_path = os.path.join(base_dir, "templates", "dashboard_summary.html")
    with open(summary_path, "r", encoding="utf-8") as f:
        summary_panel = f.read()
        
    summary_panel = (summary_panel
                     .replace("{{ TOTAL_SPECIES }}", str(total_dashboard_species))
                     .replace("{{ JSON_COUNT }}", str(json_count))
                     .replace("{{ EBIRD_COUNT }}", str(ebird_count))
                     .replace("{{ INVALID_TAXONOMY }}", str(invalid_taxonomy_count))
                     .replace("{{ ACTIVE_MIGRATIONS }}", str(len(migration_items)))
                     .replace("{{ JSON_UNPUBLISHED }}", str(json_unpublished_count))
                     .replace("{{ NEEDS_TAGGING }}", str(needs_tagging_count))
                     .replace("{{ MISSING_LOCATION }}", str(missing_loc_count))
                     .replace("{{ MISSING_EBIRD }}", str(published_not_ebird)))

    # 4. Map photos missing locations by species
    photos_missing_by_species = {}
    for r in photos_missing_location:
        spec = r[0]
        if spec not in photos_missing_by_species:
            photos_missing_by_species[spec] = []
        photos_missing_by_species[spec].append(r)

    # 5. Build Unified Master Table Rows
    rows_html = []
    for idx, r in enumerate(merged_rows):
        species_name = r["species_name"]
        toggle_id = f"details-{idx}"
        
        # Determine badges / alerts
        badges = []
        if r["is_valid_taxonomy"] == "No":
            badges.append('<span class="badge error" style="background-color: rgba(255, 63, 63, 0.15); color: #ff3f3f; border: 1px solid rgba(255, 63, 63, 0.3);">Invalid Taxonomy</span>')
        if r["needs_tagging"] > 0:
            badges.append(f'<span class="badge warning">Needs Tagging ({r["needs_tagging"]})</span>')
        if r["missing_loc_count"] > 0:
            badges.append(f'<span class="badge error">Missing Loc ({r["missing_loc_count"]})</span>')
        if r["published_count"] > 0 and r["in_ebird"] == "No":
            badges.append('<span class="badge info">Not in eBird</span>')
        if r["in_json"] == "Yes" and r["published_count"] == 0:
            badges.append('<span class="badge muted">Unpublished</span>')
            
        is_synced = len(badges) == 0
        if is_synced:
            badges.append('<span class="badge success">Synced & Migrated</span>')
        badges_html = " ".join(badges)

        row_class = "species-row synced-row" if is_synced else "species-row"
        drawer_class = "details-row synced-row" if is_synced else "details-row"

        needs_tagging_class = "warning-text" if r["needs_tagging"] > 0 else ""
        missing_loc_class = "error-text" if r["missing_loc_count"] > 0 else ""

        # Earliest Photo details
        earliest = earliest_photos.get(species_name, {})
        earliest_date = earliest.get("date", "N/A")
        earliest_location = earliest.get("location", "N/A")
        earliest_gallery = earliest.get("collection", "N/A")
        earliest_filename = earliest.get("filename", "N/A")

        # Action Details block
        issues_list = []
        if r["is_valid_taxonomy"] == "No":
            name_lower = species_name.lower().strip()
            action_text = ""
            if name_lower in RENAME_MAPS_LOWER:
                action_text = f' Recommended Action: Update to <strong>"{RENAME_MAPS_LOWER[name_lower][1]}"</strong>.'
            elif name_lower in LUMP_MAPS_LOWER:
                action_text = f' Recommended Action: Lump into <strong>"{LUMP_MAPS_LOWER[name_lower][1]}"</strong>.'
            elif name_lower in SPLIT_MAPS_LOWER:
                candidates_str = ", ".join(f'"{c}"' for c in SPLIT_MAPS_LOWER[name_lower][1])
                action_text = f' Recommended Action: Split into one of <strong>{candidates_str}</strong>.'
            elif normalize_name(species_name) in normalized_v2025:
                target = normalized_v2025[normalize_name(species_name)]
                action_text = f' Recommended Action: Update to <strong>"{target}"</strong> (automatically matched via spelling check).'
            elif species_name in auto_recs:
                action_text = auto_recs[species_name]
                
            # Interactive Research button: copies a research prompt to clipboard
            research_prompt = f"What is the taxonomic history and current name for &quot;{species_name}&quot; in the eBird v2025/Clements taxonomy? Was it split, lumped, or renamed?"
            research_btn = f"""<button class="copy-btn" onclick="navigator.clipboard.writeText('{research_prompt}'); const btn = this; const orig = btn.innerHTML; btn.innerHTML = 'Copied!'; btn.style.borderColor = '#2ed573'; btn.style.color = '#2ed573'; setTimeout(function() {{ btn.innerHTML = orig; btn.style.borderColor = '#555'; btn.style.color = '#fff'; }}, 2000)" style="margin-left: 8px; vertical-align: middle;">🔍 Research</button>"""

            issues_list.append(f'<p class="error-text" style="color: #ff3f3f; margin-bottom: 4px;">❌ <strong>Invalid Name:</strong> "{species_name}" is not a valid common name in the eBird v2025 taxonomy. Update this tag/label in Lightroom.{action_text}{research_btn}</p>')
            issues_list.append('<p class="info-text" style="color: #888; font-size: 0.85em; margin-top: 0; margin-bottom: 12px; padding-left: 20px;">💡 <em>Hint:</em> If this is a mammal, plant, landscape, or other non-bird subject, assign the keyword tag <strong>"Wildlife"</strong> or <strong>"Landscape"</strong> to it in Lightroom. The dashboard will then automatically exclude it.</p>')
            
            # Append catalog-wide photo-level split recommendations if available
            split_recs = split_details_by_species.get(species_name)
            if split_recs:
                issues_list.append('<h5 style="margin-top: 15px; margin-bottom: 5px; color: #ff9f43;">📅 eBird Sighting Log Match Recommendations (by photo date):</h5>')
                issues_list.append('<div class="photo-audit-list">')
                issues_list.append('<ul style="list-style-type: none; padding-left: 0; margin: 0; font-size: 0.85em; line-height: 1.6;">')
                issues_list.extend(split_recs)
                issues_list.append('</ul>')
                issues_list.append('</div>')
        if r["needs_tagging"] > 0:
            examples = needs_tagging_examples.get(species_name, [])
            example_str = ""
            if examples:
                valid_example = None
                for ex_file, ex_folder, ex_root in examples:
                    # check both the raw path and join it properly
                    full_path = os.path.join(ex_root, ex_folder, ex_file)
                    if os.path.exists(full_path):
                        valid_example = (ex_file, ex_folder)
                        break
                if not valid_example:
                    valid_example = (examples[0][0], examples[0][1])
                ex_file, ex_folder = valid_example
                example_str = f' (e.g., <span class="file-cell">{ex_file}</span> in <strong>{ex_folder}</strong>)'
            issues_list.append(f'<p class="warning-text">⚠️ <strong>Needs Tagging:</strong> {r["needs_tagging"]} photos have this color label but lack the corresponding taxonomy keyword tag{example_str}.</p>')
        if r["missing_loc_count"] > 0:
            issues_list.append(f'<p class="error-text">📍 <strong>Missing Location:</strong> {r["missing_loc_count"]} published photos have no location details.</p>')
            issues_list.append('<ul class="missing-loc-list" style="list-style-type: none; padding-left: 10px;">')
            spec_photos = photos_missing_by_species.get(species_name, [])
            for pm in spec_photos:
                cap_date = pm[3][:10] if pm[3] else "N/A"
                
                # Check for matching eBird locations
                matched_hotspots = None
                if cap_date != "N/A":
                    name_lower = species_name.lower().strip()
                    candidates = [name_lower]
                    if name_lower in SYNONYMS:
                        candidates.append(SYNONYMS[name_lower])
                    for cand in candidates:
                        key = (cand, cap_date)
                        if key in ebird_locs:
                            matched_hotspots = sorted(ebird_locs[key])
                            break
                            
                if matched_hotspots:
                    color_class = "single-hotspot" if len(matched_hotspots) == 1 else "multi-hotspots"
                    loc_blocks = []
                    for loc in matched_hotspots:
                        escaped_loc = loc.replace("'", "\\'")
                        loc_blocks.append(
                            f'<span class="hotspot-option" style="display: inline-flex; align-items: center; gap: 4px; margin-left: 6px; padding: 2px 6px; background: #0b0b0b; border: 1px solid #222; border-radius: 4px; font-size: 0.9em;">'
                            f'➔ Sighting: <strong class="{color_class}">{loc}</strong>'
                            f'<button class="copy-btn" onclick="copyToClipboard(\'{escaped_loc}\', this)">Copy</button>'
                            f'</span>'
                        )
                    loc_html = " ".join(loc_blocks)
                    issues_list.append(f'<li style="margin-bottom: 6px;"><span class="file-cell">{pm[1]}</span> in <strong>{pm[2]}</strong> (Captured {cap_date}) {loc_html}</li>')
                else:
                    issues_list.append(f'<li style="margin-bottom: 6px;"><span class="file-cell">{pm[1]}</span> in <strong>{pm[2]}</strong> (Captured {cap_date})</li>')
            issues_list.append('</ul>')
        if r["published_count"] > 0 and r["in_ebird"] == "No":
            issues_list.append('<p class="warning-text">🐦 <strong>eBird Discrepancy:</strong> Published in your SmugMug portfolio but has no matching sighting record in your eBird sightings file (ebird.csv).</p>')
        if not issues_list:
            issues_list.append('<p class="success-text">🎉 This species is fully synchronized, labeled, tagged, and matching your eBird logs.</p>')
        issues_html = "\n".join(issues_list)

        # Main row HTML
        main_row = f"""
        <tr class="{row_class}" onclick="toggleDetails('{toggle_id}')">
            <td class="toggle-icon-cell"><span class="toggle-icon" id="icon-{toggle_id}">▶</span></td>
            <td class="species-cell">{species_name}</td>
            <td class="status-cell">{r["in_json"]}</td>
            <td class="status-cell">{r["in_ebird"]}</td>
            <td class="num-cell">{r["total_label"]}</td>
            <td class="num-cell">{r["total_keyword"]}</td>
            <td class="num-cell">{r["published_count"]}</td>
            <td class="num-cell {needs_tagging_class}">{r["needs_tagging"]}</td>
            <td class="num-cell {missing_loc_class}">{r["missing_loc_count"]}</td>
            <td class="actions-cell">{badges_html}</td>
        </tr>
        """
        
        # Details drawer row HTML
        drawer_row = f"""
        <tr class="{drawer_class}" id="{toggle_id}" style="display: none;">
            <td colspan="10" class="details-container-cell">
                <div class="details-container">
                     <div class="details-grid">
                        <div class="details-card earliest-card">
                            <h4>📅 Earliest Photo Sighting</h4>
                            <p><strong>First Photographed:</strong> {earliest_date}</p>
                            <p><strong>Location:</strong> {earliest_location}</p>
                            <p><strong>Gallery:</strong> {earliest_gallery}</p>
                            <p><strong>Filename:</strong> <span class="file-cell">{earliest_filename}</span></p>
                        </div>
                        <div class="details-card issues-card">
                            <h4>⚠️ Active Action Details</h4>
                            {issues_html}
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        """
        rows_html.append(main_row.strip() + "\n" + drawer_row.strip())

    rows_joined = "\n".join(rows_html)
    master_table = f"""
    <div class="dashboard-section">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #222; padding-bottom: 12px; margin-bottom: 18px;">
            <h2 class="section-heading" style="margin: 0; border: none; padding: 0;">Species Library Health Index</h2>
            <label style="display: flex; align-items: center; gap: 8px; color: #eee; font-weight: bold; font-size: 0.9em; cursor: pointer; user-select: none;">
                <input type="checkbox" id="toggle-synced-chk" onchange="toggleSyncedRows(this)" style="width: 16px; height: 16px; cursor: pointer; accent-color: #2ed573;">
                Show Synced & Migrated Species
            </label>
        </div>
        <p class="section-desc">Unified master checklist of all bird species in your photo library. Click any species row to expand and view its earliest photographed details, taxonomy tagging details, or specific file listings needing location recovery.</p>
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th></th>
                    <th>Species Name</th>
                    <th style="text-align: center;">In JSON</th>
                    <th style="text-align: center;">In eBird</th>
                    <th style="text-align: right;">Label Photos</th>
                    <th style="text-align: right;">Taxonomic Tag</th>
                    <th style="text-align: right;">Published</th>
                    <th style="text-align: right;">Needs Tagging</th>
                    <th style="text-align: right;">Missing Loc</th>
                    <th>Action Items</th>
                </tr>
            </thead>
            <tbody>
                {rows_joined}
            </tbody>
        </table>
    </div>
    
    <script>
    function toggleDetails(rowId) {{
        var detailsRow = document.getElementById(rowId);
        var icon = document.getElementById("icon-" + rowId);
        if (detailsRow.style.display === "none") {{
            detailsRow.style.display = "table-row";
            icon.classList.add("expanded");
        }} else {{
            detailsRow.style.display = "none";
            icon.classList.remove("expanded");
        }}
    }}

    function toggleSyncedRows(checkbox) {{
        var show = checkbox.checked;
        var rows = document.querySelectorAll('.synced-row');
        rows.forEach(function(row) {{
            if (show) {{
                if (row.classList.contains('details-row')) {{
                    var icon = document.getElementById("icon-" + row.id);
                    if (icon && icon.classList.contains('expanded')) {{
                        row.style.display = "table-row";
                    }} else {{
                        row.style.display = "none";
                    }}
                }} else {{
                    row.style.display = "table-row";
                }}
            }} else {{
                row.style.display = "none";
            }}
        }});
    }}

    function copyToClipboard(text, btn) {{
        navigator.clipboard.writeText(text).then(function() {{
            var oldText = btn.innerText;
            btn.innerText = "Copied!";
            btn.style.backgroundColor = "#2ed573";
            btn.style.borderColor = "#2ed573";
            setTimeout(function() {{
                btn.innerText = oldText;
                btn.style.backgroundColor = "";
                btn.style.borderColor = "";
            }}, 1200);
        }}).catch(function(err) {{
            console.error("Failed to copy text: ", err);
        }});
    }}
    </script>
    """

    migration_section_html = ""
    if migration_items:
        migration_rows = []
        for item in migration_items:
            migration_rows.append(f"""
            <tr>
                <td class="file-cell">{item["filename"]}</td>
                <td style="font-size: 0.85em; color: #aaa;">{item["lr_path"]}</td>
                <td><span class="badge warning">{item["source"]}</span></td>
                <td class="date-cell">{item["date"]}</td>
                <td class="error-text">{item["old_tag"]}</td>
                <td><span class="badge info">{item["type"]}</span></td>
                <td class="success-text" style="color: #ff9f43;">{item["suggested_action_txt"]}</td>
            </tr>
            """)
        
        migration_rows_joined = "".join(migration_rows)
        migration_section_html = f"""
        <div class="dashboard-section" style="border: 1px solid rgba(255, 159, 67, 0.2); border-radius: 6px; padding: 20px; background-color: #17120e; margin-bottom: 40px;">
            <h2 class="section-heading" style="color: #ff9f43; border-bottom: 2px solid #ff9f43; padding-bottom: 8px; margin-top: 0;">🔄 Active Taxonomic Migrations (Action Required)</h2>
            <p class="section-desc" style="color: #ddd;">The following {len(migration_items)} photos carry obsolete common names or typos in your Lightroom catalog. Correct them in Lightroom to align with the new taxonomy.</p>
            <table class="dashboard-table" style="margin-top: 15px; border: 1px solid #332115;">
                <thead>
                    <tr style="background-color: #241910;">
                        <th style="color: #ff9f43;">Photo Filename</th>
                        <th style="color: #ff9f43;">Lightroom Path</th>
                        <th style="color: #ff9f43;">Tag Source</th>
                        <th style="color: #ff9f43;">Capture Date</th>
                        <th style="color: #ff9f43;">Obsolete Tag</th>
                        <th style="color: #ff9f43;">Type</th>
                        <th style="color: #ff9f43;">Recommended Action</th>
                    </tr>
                </thead>
                <tbody>
                    {migration_rows_joined}
                </tbody>
            </table>
        </div>
        """

    content_html = summary_panel + "\n" + migration_section_html + "\n" + master_table

    # 6. Page CSS rules
    styles = """
        .dashboard-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .summary-card {
            background-color: #1a1a1a;
            border-left: 4px solid #4db8ff;
            padding: 20px;
            border-radius: 6px;
        }
        .summary-card.warning { border-left-color: #ff9f43; }
        .summary-card.primary { border-left-color: #2ed573; }
        .summary-card.error { border-left-color: #ff4d4d; }
        .summary-card.info { border-left-color: #a55eea; }
        .card-title {
            font-size: 0.9em;
            text-transform: uppercase;
            color: #aaa;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .card-val {
            font-size: 2.2em;
            font-weight: bold;
            color: #fff;
        }
        .dashboard-section {
            margin-top: 40px;
            margin-bottom: 50px;
        }
        .section-heading {
            font-size: 1.6em;
            font-weight: bold;
            color: #fff;
            margin-bottom: 10px;
            border-bottom: 1px solid #333;
            padding-bottom: 8px;
        }
        .section-desc {
            color: #aaa;
            margin-bottom: 20px;
            font-size: 0.95em;
        }
        .dashboard-table {
            width: 100%;
            border-collapse: collapse;
            background-color: #131313;
            border: 1px solid #222;
            border-radius: 6px;
            overflow: hidden;
            margin-top: 20px;
        }
        .dashboard-table th {
            background-color: #1a1a1a;
            color: #fff;
            font-weight: bold;
            padding: 12px 16px;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border-bottom: 2px solid #333;
            text-align: left;
        }
        .dashboard-table td {
            padding: 12px 16px;
            font-size: 0.9em;
            border-bottom: 1px solid #1a1a1a;
        }
        .species-row {
            cursor: pointer;
            transition: background-color 0.15s ease;
        }
        .species-row:hover {
            background-color: #1d1d1d;
        }
        .toggle-icon-cell {
            width: 30px;
            text-align: center;
            color: #888;
            font-size: 0.8em;
        }
        .toggle-icon {
            display: inline-block;
            transition: transform 0.15s ease;
        }
        .toggle-icon.expanded {
            transform: rotate(90deg);
        }
        .details-row {
            background-color: #0b0b0b;
        }
        .details-container-cell {
            padding: 0 !important;
            border-bottom: 1px solid #222 !important;
        }
        .details-container {
            padding: 20px 40px;
            background-color: #0d0d0d;
            border-top: 1px solid #1a1a1a;
            border-bottom: 1px solid #1a1a1a;
        }
        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        .details-card {
            background-color: #151515;
            border: 1px solid #222;
            border-radius: 6px;
            padding: 16px 20px;
        }
        .details-card h4 {
            margin-top: 0;
            margin-bottom: 12px;
            border-bottom: 1px solid #333;
            padding-bottom: 6px;
            color: #fff;
            font-size: 1em;
        }
        .details-card h5 {
            margin-top: 10px;
            margin-bottom: 6px;
            color: #aaa;
            font-size: 0.9em;
        }
        .details-card p {
            margin: 6px 0;
            color: #ccc;
            font-size: 0.9em;
        }
        .missing-loc-list {
            margin: 0;
            padding-left: 20px;
            font-size: 0.85em;
            color: #bbb;
        }
        .missing-loc-list li {
            margin-bottom: 4px;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.75em;
            font-weight: bold;
            border-radius: 4px;
            margin-right: 4px;
            text-transform: uppercase;
        }
        .badge.warning { background-color: rgba(255, 159, 67, 0.15); color: #ff9f43; border: 1px solid rgba(255, 159, 67, 0.3); }
        .badge.error { background-color: rgba(255, 77, 77, 0.15); color: #ff4d4d; border: 1px solid rgba(255, 77, 77, 0.3); }
        .badge.info { background-color: rgba(165, 94, 234, 0.15); color: #a55eea; border: 1px solid rgba(165, 94, 234, 0.3); }
        .badge.success { background-color: rgba(46, 213, 115, 0.15); color: #2ed573; border: 1px solid rgba(46, 213, 115, 0.3); }
        .badge.muted { background-color: rgba(136, 136, 136, 0.15); color: #888; border: 1px solid rgba(136, 136, 136, 0.3); }
        .species-cell {
            font-weight: bold;
            color: #eee;
        }
        .status-cell {
            text-align: center;
            color: #bbb;
        }
        .num-cell {
            text-align: right;
            font-family: monospace;
            font-size: 1em;
            color: #ccc;
        }
        .warning-text { color: #ff9f43; font-weight: bold; }
        .error-text { color: #ff4d4d; font-weight: bold; }
        .success-text { color: #2ed573; font-weight: bold; }
        .file-cell { font-family: monospace; color: #a55eea; }
        .gallery-cell { color: #2ed573; }
        .date-cell { font-family: monospace; color: #aaa; }
        .location-cell { color: #ccc; }
        .single-hotspot { color: #2ed573; font-weight: bold; }
        .multi-hotspots { color: #ffd32a; font-weight: bold; }
        .copy-btn {
            background-color: #222;
            color: #fff;
            border: 1px solid #555;
            padding: 2px 6px;
            font-size: 0.8em;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 4px;
            transition: all 0.15s ease;
        }
        .copy-btn:hover {
            background-color: #333;
            border-color: #888;
        }
        .photo-audit-list {
            max-height: 250px;
            overflow-y: auto;
            border: 1px solid #222;
            border-radius: 4px;
            padding: 10px 14px;
            background-color: #0b0b0b;
            margin-top: 8px;
        }
        .synced-row {
            display: none;
        }
    """

    # 7. Perform substitutions
    html = html.replace("{{ PAGE_TITLE }}", "Bird Migration & Publishing Dashboard")
    html = html.replace("{{ HEADER_TITLE }}", "Bird Migration & Publishing Dashboard")
    html = html.replace("{{ STATS_HEADER }}", "")
    html = html.replace("{{ PAGE_SPECIFIC_STYLES }}", styles)
    html = html.replace("{{ CONTENT }}", content_html)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
