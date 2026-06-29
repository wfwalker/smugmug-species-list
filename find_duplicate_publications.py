#!/usr/bin/python3

import sqlite3
import shutil
import os
import sys
from lrcat_utils import open_catalog

def main():
    print("=" * 80)
    print("SMUGMUG MULTIPLE-PUBLICATION DETECTOR")
    print("=" * 80)
    print("This script finds cases where multiple versions of the same capture event")
    print("(e.g., raw files and TIF edits) have been published to SmugMug.")
    print("-" * 80)

    # SQL query using common table expression (CTE) to find duplicate groups
    query = """
    WITH PublishedPhotos AS (
        SELECT 
            rp.id_local as remote_photo_id,
            rp.remoteId as remote_uri_id,
            rp.url,
            i.captureTime,
            f.baseName || '.' || f.extension as filename,
            c.name as collection_name,
            CASE 
                WHEN INSTR(f.baseName, '-') > 0 
                THEN SUBSTR(f.baseName, 1, INSTR(f.baseName, '-') - 1) 
                ELSE f.baseName 
            END as file_prefix
        FROM AgRemotePhoto rp
        JOIN Adobe_images i ON rp.photo = i.id_local
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        JOIN AgLibraryPublishedCollection c ON rp.collection = c.id_local
        WHERE rp.remoteId LIKE '/image/%'
    )
    SELECT 
        p1.captureTime, 
        p1.file_prefix,
        GROUP_CONCAT(p1.filename, ' | '),
        GROUP_CONCAT(p1.collection_name, ' | '),
        GROUP_CONCAT(p1.url, ' | '),
        COUNT(*) as cnt
    FROM PublishedPhotos p1
    GROUP BY p1.captureTime, p1.file_prefix
    HAVING cnt > 1
    ORDER BY p1.captureTime DESC;
    """

    try:
        with open_catalog() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
    except Exception as e:
        print(f"❌ Error querying Lightroom database: {e}")
        sys.exit(1)

    if not rows:
        print("✅ No duplicate publications found! Every published capture is unique.")
        sys.exit(0)

    # Classify the rows into categories
    raw_tif_groups = []
    multi_edit_groups = []
    cross_post_groups = []
    
    raw_exts = {'.cr2', '.cr3', '.nef', '.dng'}
    
    for r in rows:
        capture_time = r[0]
        prefix = r[1]
        filenames = r[2].split(' | ')
        collections = r[3].split(' | ')
        urls = r[4].split(' | ')
        count = r[5]
        
        group_info = {
            "capture_time": capture_time,
            "prefix": prefix,
            "filenames": filenames,
            "collections": collections,
            "urls": urls,
            "count": count
        }
        
        # Check if all filenames are identical
        if len(set(filenames)) == 1:
            cross_post_groups.append(group_info)
            continue
            
        # Check if it has raw and edit
        has_raw = False
        has_edit = False
        for f in filenames:
            ext = os.path.splitext(f.lower())[1]
            if ext in raw_exts:
                has_raw = True
            if '-edit' in f.lower() or ext in {'.tif', '.tiff'}:
                has_edit = True
                
        if has_raw and has_edit:
            raw_tif_groups.append(group_info)
        else:
            multi_edit_groups.append(group_info)

    # Compile markdown report
    report_lines = []
    report_lines.append("# SmugMug Duplicate Publications Report")
    report_lines.append(f"Generated on: {os.popen('date').read().strip()}")
    report_lines.append(f"Found **{len(rows)}** total capture events with multiple publications, categorized below:\n")
    
    # Section 1: RAW + TIF Edit Duplicates
    print("=" * 80)
    print(f"SECTION 1: RAW + TIF EDIT DUPLICATES ({len(raw_tif_groups)} events)")
    print("=" * 80)
    print("These are cases where both the original RAW/DNG file and an edited TIF version are published to SmugMug.")
    report_lines.append(f"## Section 1: RAW + TIF Edit Duplicates ({len(raw_tif_groups)} events)")
    report_lines.append("These are cases where both the original RAW/DNG file and an edited TIF version are published to SmugMug.\n")
    
    for idx, g in enumerate(raw_tif_groups):
        header = f"\n[{idx + 1}] Capture Prefix: {g['prefix']} ({g['count']} versions) | Date: {g['capture_time'][:10]} {g['capture_time'][11:19]}"
        print(header)
        print("-" * 80)
        report_lines.append(f"### {idx + 1}. Capture: `{g['prefix']}`")
        report_lines.append(f"* **Capture Time**: `{g['capture_time']}`")
        report_lines.append("| Filename | SmugMug Collection | SmugMug URL |")
        report_lines.append("| --- | --- | --- |")
        for f_name, coll_name, url in zip(g['filenames'], g['collections'], g['urls']):
            print(f"  • {f_name:<30} | Coll: {coll_name:<20} | URL: {url}")
            report_lines.append(f"| `{f_name}` | {coll_name} | [{url.split('/')[-1]}]({url}) |")
        report_lines.append("")
        
    # Section 2: Multiple TIF/DNG Edits
    print("\n" + "=" * 80)
    print(f"SECTION 2: MULTIPLE DIFFERENT EDITS ({len(multi_edit_groups)} events)")
    print("=" * 80)
    print("These are cases where different edited versions (e.g. standard vs Enhanced NR) are published to SmugMug, but no raw file.")
    report_lines.append(f"## Section 2: Multiple Different Edits ({len(multi_edit_groups)} events)")
    report_lines.append("These are cases where different edited versions (e.g. standard edit vs noise-reduced edit) are published to SmugMug, but no raw file is published.\n")
    
    for idx, g in enumerate(multi_edit_groups):
        header = f"\n[{idx + 1}] Capture Prefix: {g['prefix']} ({g['count']} versions) | Date: {g['capture_time'][:10]} {g['capture_time'][11:19]}"
        print(header)
        print("-" * 80)
        report_lines.append(f"### {idx + 1}. Capture: `{g['prefix']}`")
        report_lines.append(f"* **Capture Time**: `{g['capture_time']}`")
        report_lines.append("| Filename | SmugMug Collection | SmugMug URL |")
        report_lines.append("| --- | --- | --- |")
        for f_name, coll_name, url in zip(g['filenames'], g['collections'], g['urls']):
            print(f"  • {f_name:<30} | Coll: {coll_name:<20} | URL: {url}")
            report_lines.append(f"| `{f_name}` | {coll_name} | [{url.split('/')[-1]}]({url}) |")
        report_lines.append("")

    # Section 3: Identical File Cross-Posts (omit detailed list in stdout to save terminal clutter)
    print("\n" + "=" * 80)
    print(f"SECTION 3: IDENTICAL FILE CROSS-POSTS ({len(cross_post_groups)} events)")
    print("=" * 80)
    print("  (Detailed lists for identical cross-posts are saved to the markdown report to keep terminal output clean.)")
    
    report_lines.append(f"## Section 3: Identical File Cross-Posts ({len(cross_post_groups)} events)")
    report_lines.append("These are cases where the exact same file (same filename) was published to multiple galleries (e.g. a trip gallery and a calendar gallery).\n")
    
    for idx, g in enumerate(cross_post_groups):
        report_lines.append(f"### {idx + 1}. Capture: `{g['prefix']}`")
        report_lines.append(f"* **Capture Time**: `{g['capture_time']}`")
        report_lines.append("| Filename | SmugMug Collection | SmugMug URL |")
        report_lines.append("| --- | --- | --- |")
        for f_name, coll_name, url in zip(g['filenames'], g['collections'], g['urls']):
            report_lines.append(f"| `{f_name}` | {coll_name} | [{url.split('/')[-1]}]({url}) |")
        report_lines.append("")

    # Save report
    report_path = "duplicate_publications_report.md"
    try:
        with open(report_path, "w", encoding="utf-8") as f_report:
            f_report.write("\n".join(report_lines))
        print("\n" + "=" * 80)
        print(f"📝 Full list saved to report file: [duplicate_publications_report.md](file://{os.path.abspath(report_path)})")
        print("=" * 80)
    except Exception as e:
        print(f"❌ Error saving report file: {e}")

if __name__ == "__main__":
    main()
