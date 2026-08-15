# SmugMug & eBird Metadata Sync Tools

This repository contains a suite of automation tools designed to manage your bird photography library, synchronize metadata between your **Lightroom Classic catalog**, **eBird checklists**, and **SmugMug portfolio**, and generate custom lifelist pages.

---

## 🗂️ Project Architecture & Data Flow

```mermaid
graph TD
    A["Lightroom Catalog (.lrcat)"] -->|Queries| B["Python Scripts"]
    C["eBird checklists (ebird.csv)"] -->|Cross-references| B
    B -->|Generates HTML| D["SmugMug Custom Life Lists"]
    B -->|Generates Dashboard| E["Unified Dashboard (reports/bird_migration_dashboard.html)"]
    E -->|Copy Suggestion| F["tools/apply-location-matches.py (ExifTool)"]
    F -->|Updates Raw/XMP| G["Photo Files on Disk"]
    G -->|Read Metadata| A
```

---

## 📂 Directory Structure

The codebase is organized into modular layers to promote maintainability and code deduplication:

* **`lib/`**: Shared core code containing connection utilities (`lrcat_utils.py`), shared SQL database queries (`shared_queries.py`), JSON/CSV parsing engines, and statistical processors.
* **`generators/`**: Database-agnostic HTML and SVG layout formatting builders (alphabetical, taxonomic, chronological, growth timeline, and dashboard).
* **`tools/`**: Standalone CLI utilities and recovery tools that run independently.
* **`templates/`**: Shared HTML and section templates used by page builders.
* **`tests/`**: Parity unit tests validated against an in-memory mock catalog.

---

## 🐍 Script Catalog

### 1. Main Pipeline Orchestrator
* **`update_reports.py`**
  * *Purpose*: The primary command center. Runs the entire compilation chain in a single Lightroom session, generating all life lists, charts, and dashboards in about 12 seconds.
  * *Commands*: Run `python3 update_reports.py --help` for specific page target flags.

### 2. Location & Publishing Dashboard
* **`migration-and-publishing-dashboard.py`**
  * *Purpose*: CLI wrapper running only the Migration & Publishing Dashboard pipeline (`lib/dashboard_pipeline.py`).
  * *Features*:
    * *Dynamic Location Suggester*: Displays date-matched eBird checklist hotspots directly inside the species details drawer for location recovery, complete with confidence color-coding (green/yellow) and click-to-copy buttons.
    * *Automated Taxonomy Resolver*: Programmatically traces obsolete species tags and typos to official v2025 names using case-insensitive/spacing normalization and historical scientific name/species code mapping.
    * *Synced Filter Toggle*: A browser-based checkbox dynamically hides/shows fully migrated species rows to keep focus on remaining cleanups.
    * *Exclusions*: Automatically ignores tags specified in `EXCLUDED_TAGS` (e.g., `"People"`, `"Wildlife"`, `"Garden"`, `"Wedding"`).
  * *Outputs*: Master interactive HTML dashboard ([reports/bird_migration_dashboard.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/bird_migration_dashboard.html)) and [reports/bird_migration_dashboard.csv](file:///Users/walker/Dropbox/smugmug-species-list/reports/bird_migration_dashboard.csv).
* **`tools/apply-location-matches.py`**
  * *Purpose*: Automation loop that runs `exiftool` to write location details (sub-location, city, state, country) directly back to raw image files or `.xmp` sidecars based on matched eBird checklist locations.

### 3. Custom Life List Page Generators (in `generators/`)
These modules format the data retrieved by the centralized SQL query library to generate custom SmugMug lifelist indexes:
* **`taxonomic.py`** ➔ Generates [html/taxonomic_life_list.html](file:///Users/walker/Dropbox/smugmug-species-list/html/taxonomic_life_list.html) (indexed taxonomically by Order and Family).
* **`alphabetical.py`** ➔ Generates [html/alphabetical_life_list.html](file:///Users/walker/Dropbox/smugmug-species-list/html/alphabetical_life_list.html) (indexed alphabetically by English common name).
* **`chronological.py`** ➔ Generates [html/chronological_life_list.html](file:///Users/walker/Dropbox/smugmug-species-list/html/chronological_life_list.html) (indexed chronologically by date first photographed).
* **`growth_chart.py`** ➔ Generates the interactive timeline growth dashboard [html/photo_lifelist_growth.html](file:///Users/walker/Dropbox/smugmug-species-list/html/photo_lifelist_growth.html) and static SVG chart [html/photo_growth_chart.svg](file:///Users/walker/Dropbox/smugmug-species-list/html/photo_growth_chart.svg).

### 4. Taxonomy & Maintenance Utilities (in `tools/`)
* **`tools/ebird-keyword-list-generator.py`**
  * *Purpose*: Parses eBird taxonomy CSVs (`taxonomy/eBird_taxonomy_vYYYY.csv`) to generate a hierarchical Lightroom keyword list tree.
  * *Outputs*: `ebird-vYYYY-keyword-list.txt` (importable into Lightroom).
* **`tools/audit_taxonomy_migration.py`**
  * *Purpose*: Audits your catalog for obsolete taxonomy keywords, mapping them to the latest standard. For split species, it cross-references photo capture dates with your `ebird.csv` checklists to auto-recommend the correct split species.
  * *Outputs*: [reports/taxonomy_migration_audit.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/taxonomy_migration_audit.html) & [reports/taxonomy_migration_audit.csv](file:///Users/walker/Dropbox/smugmug-species-list/reports/taxonomy_migration_audit.csv).
* **`tools/get_oauth_tokens.py`**: Handles OAuth 1.0a handshake to fetch SmugMug API access tokens.
* **`tools/update_on_this_date.py`**: Updates the "On This Date" widget on your SmugMug homepage.
* **`tools/generate_ebird_kml.py`**: Generates KML files of your sightings for Google Earth mapping.

---

## 🏁 Operational Workflows

### Workflow A: Daily Location Update & Sync
1. Run `python3 update_reports.py --dashboard` to compile the library health status.
2. Open [reports/bird_migration_dashboard.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/bird_migration_dashboard.html) in your browser. Expand any species carrying the red **`Missing Loc`** badge to see their files and date-matched eBird hotspot suggestions.
3. Click the **Copy** button next to the desired suggested location to capture it to your clipboard.
4. Run `python3 tools/apply-location-matches.py` to write those copied location matches back to your raw files/sidecars.
5. Inside Lightroom: Select the modified photos and run **Metadata ➔ Read Metadata from Files** to update your catalog.

### Workflow B: Rebuilding Custom Lifelists
1. Ensure your latest catalog changes are published to SmugMug.
2. Run the pipeline compiler to regenerate all custom lifelist pages:
   ```bash
   python3 update_reports.py --lifelists --growth
   ```
3. Copy the compiled HTML content from the `html/` directory to update your custom SmugMug lifelist pages.

### Workflow C: eBird Taxonomy Update & Dashboard Health Checks
1. Download the new eBird taxonomy CSV and place it in the `taxonomy/` folder.
2. Run the pipeline compiler:
   ```bash
   python3 update_reports.py
   ```
3. Open [reports/bird_migration_dashboard.html](file:///Users/walker/Dropbox/smugmug-species-list/reports/bird_migration_dashboard.html) in your browser. Active taxonomic migrations will automatically float to the very top of the dashboard as a dedicated checklist.
   * *(Note: You can still run `python3 tools/audit_taxonomy_migration.py` standalone if you prefer a separate report).*
4. In Lightroom, manually rename obsolete keywords (e.g. rename `Squirrel Cuckoo` to `Common Squirrel-Cuckoo`) and resolve splits using the report's recommendations.
5. Generate the new keyword tree file using `python3 tools/ebird-keyword-list-generator.py` and import it into Lightroom using **Metadata ➔ Import Keywords...**.
6. Delete the old empty parent keyword folder from Lightroom's Keyword List panel.

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
3. **ExifTool**: Ensure `exiftool` is installed on your system path (required for location writing).
