# SmugMug & eBird Metadata Sync Tools

This repository contains a suite of automation tools designed to manage your bird photography library, synchronize metadata between your **Lightroom Classic catalog**, **eBird checklists**, and **SmugMug portfolio**, and generate custom lifelist pages.

---

## 🗂️ Project Architecture & Data Flow

```mermaid
graph TD
    A["Lightroom Catalog (.lrcat)"] -->|Queries| B["Python Scripts"]
    C["eBird checklists (ebird.csv)"] -->|Cross-references| B
    B -->|Generates HTML| D["SmugMug Custom Life Lists"]
    B -->|Generates Todo| E["Location To-Do Lists"]
    E -->|Writes EXIF| F["apply-location-matches.py (ExifTool)"]
    F -->|Updates Raw/XMP| G["Photo Files on Disk"]
    G -->|Read Metadata| A
```

---

## 🐍 Script Catalog

### 1. Location & Publishing Dashboard
* **`migration-and-publishing-dashboard.py`**
  * *Purpose*: The main dashboard showing species publication status, missing locations, missing taxonomic tags, and global exclusions.
  * *Exclusions*: Automatically ignores tags specified in `EXCLUDED_TAGS` (e.g., `"People"`, `"Wildlife"`).
  * *Outputs*: Terminal summary report and the interactive dashboard [reports/bird_migration_dashboard.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/bird_migration_dashboard.html).
* **`generate-location-todo.py`**
  * *Purpose*: Generates an interactive checklist of published photos that lack location tags. It cross-references capture dates with your eBird checklist history to auto-suggest eBird hotspots.
  * *Color Coding*: Highlights unique hotspots in green (`#2ed573`) and multiple candidate options in yellow (`#ffd32a`).
  * *Outputs*: [reports/location_todo_list.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/location_todo_list.html) & [reports/location_todo_list.csv](file:///Users/walker/Dropbox/smugmug-species-list/reports/location_todo_list.csv).
* **`apply-location-matches.py`**
  * *Purpose*: Automation loop that runs `exiftool` to write location details (sub-location, city, state, country) directly back to your raw image files or `.xmp` sidecars based on matched eBird checklist locations.

### 2. Custom Life List Page Generators
These scripts query your Lightroom database to find your earliest published photos of each species and compile customized SmugMug lifelist indexes:
* **`taxonomic-life-list-custom-page.py`**
  * *Generates*: [html/taxonomic_life_list.html](file:///Users/walker/Dropbox/smugmug-species-list/html/taxonomic_life_list.html) (indexed taxonomically by Order and Family).
* **`alphabetical-lifelist-custom-page.py`**
  * *Generates*: [html/alphabetical_life_list.html](file:///Users/walker/Dropbox/smugmug-species-list/html/alphabetical_life_list.html) (indexed alphabetically by English common name).
* **`chronological-lifelist-custom-page.py`**
  * *Generates*: [html/chronological_life_list.html](file:///Users/walker/Dropbox/smugmug-species-list/html/chronological_life_list.html) (indexed chronologically by date first photographed).

### 3. Annual Taxonomy Migration
* **`ebird-keyword-list-generator.py`**
  * *Purpose*: Parses eBird taxonomy CSVs (`taxonomy/eBird_taxonomy_vYYYY.csv`) to generate a hierarchical Lightroom keyword list tree.
  * *Outputs*: `ebird-vYYYY-keyword-list.txt` (importable into Lightroom).
* **`audit-taxonomy-migration.py`**
  * *Purpose*: Audits your catalog for obsolete taxonomy keywords, mapping them to the latest standard. For split species, it cross-references photo capture dates with your `ebird.csv` checklists to auto-recommend the correct split species.
  * *Outputs*: [reports/taxonomy_migration_audit.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/taxonomy_migration_audit.html) & [reports/taxonomy_migration_audit.csv](file:///Users/walker/Dropbox/smugmug-species-list/reports/taxonomy_migration_audit.csv).

### 4. Utilities
* **`lrcat_utils.py`**: Central library containing database connections, catalog copying logic, relative URL formatters, and location string formatting helpers.
* **`get_oauth_tokens.py`**: Handles OAuth 1.0a handshake to fetch SmugMug API access tokens.
* **`update_on_this_date.py`**: Updates the "On This Date" widget on your SmugMug homepage.

---

## 🏁 Operational Workflows

### Workflow A: Daily Location Update & Sync
1. Run `python3 generate-location-todo.py` to compile the list of published photos lacking location details.
2. Review suggestions in [reports/location_todo_list.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/location_todo_list.html). Click the **Copy** button next to the desired location match to save it to your clipboard.
3. Run `python3 apply-location-matches.py` to write those copied location matches back to your raw files/sidecars.
4. Inside Lightroom: Select the modified photos and run **Metadata ➔ Read Metadata from Files** to update your catalog.

### Workflow B: Rebuilding Custom Lifelists
1. Ensure your latest library changes are published.
2. Run the compiler chain:
   ```bash
   python3 taxonomic-life-list-custom-page.py
   python3 alphabetical-lifelist-custom-page.py
   python3 chronological-lifelist-custom-page.py
   ```
3. Copy the compiled HTML content from the `html/` directory to update your custom SmugMug lifelist pages.

### Workflow C: Annual eBird Taxonomy Update
1. Download the new eBird taxonomy CSV and place it in the `taxonomy/` folder.
2. Run `audit-taxonomy-migration.py` to generate the migration checklists.
3. Open [reports/taxonomy_migration_audit.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/taxonomy_migration_audit.html) in your browser.
4. In Lightroom, manually rename obsolete keywords (e.g. rename `Squirrel Cuckoo` to `Common Squirrel-Cuckoo`) and resolve splits using the report's recommendations.
5. Generate the new keyword tree file using `ebird-keyword-list-generator.py` and import it into Lightroom using **Metadata ➔ Import Keywords...**.
6. Delete the old empty `[eBird taxonomy v2024]` parent folder from Lightroom's Keyword List panel.

---

## ⚙️ Prerequisites & Setup

1. **Python Dependencies**:
   * Standard library modules (`sqlite3`, `csv`, `urllib`).
2. **Environment Variables**:
   Create a `.env` file at the project root:
   ```env
   SMUGMUG_API_KEY=your_developer_key
   SMUGMUG_API_SECRET=your_developer_secret
   OAUTH_TOKEN=your_oauth_token
   OAUTH_TOKEN_SECRET=your_oauth_token_secret
   ```
3. **ExifTool**: Ensure `exiftool` is installed on your system path (required for `apply-location-matches.py`).
