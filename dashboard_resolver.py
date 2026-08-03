import os
import csv

SYNONYMS = {
    "northern yellow warbler": "yellow warbler",
    "hudsonian whimbrel": "whimbrel",
    "american gannet": "northern gannet",
    "common house-martin": "western house-martin",
    "gray-breasted wood-wren": "grey-breasted wood-wren",
    "american barn owl": "barn owl",
    "northern house wren": "house wren",
    "western whimbrel": "whimbrel",
    "white-headed stilt": "pied stilt",
    "american black oystercatcher": "black oystercatcher",
}

def normalize_name(name):
    """Helper to remove hyphens, double spaces, punctuation, convert grey->gray, and lowercase strings for match comparison."""
    name_clean = name.lower().replace("grey", "gray")
    return "".join(c for c in name_clean if c.isalnum())

def build_automatic_resolutions(taxonomy_dir):
    """Attempts to automatically resolve invalid names using spelling normalization,
    scientific name tracking, and species code split/lump detection."""
    v2025_names = {}
    v2025_sci_to_names = {}
    v2025_code_to_names = {}
    normalized_v2025 = {}
    
    # 1. Load v2025 taxonomy
    v2025_path = os.path.join(taxonomy_dir, "eBird_taxonomy_v2025.csv")
    if os.path.exists(v2025_path):
        try:
            with open(v2025_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    com_name = row.get("PRIMARY_COM_NAME")
                    sci_name = row.get("SCI_NAME")
                    code = row.get("SPECIES_CODE")
                    if com_name and sci_name:
                        v2025_names[com_name] = row
                        normalized_v2025[normalize_name(com_name)] = com_name
                        if sci_name not in v2025_sci_to_names:
                            v2025_sci_to_names[sci_name] = []
                        v2025_sci_to_names[sci_name].append(com_name)
                        if code:
                            v2025_code_to_names[code] = com_name
        except Exception as e:
            print(f"⚠️ Error reading 2025 taxonomy: {e}")

    # 2. Load historical taxonomy data from all other files in directory
    historical_names = {}
    if os.path.exists(taxonomy_dir):
        for filename in sorted(os.listdir(taxonomy_dir), reverse=True):
            if filename.startswith("eBird_") and filename.endswith(".csv") and "2025" not in filename:
                path = os.path.join(taxonomy_dir, filename)
                try:
                    with open(path, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            com_name = row.get("PRIMARY_COM_NAME")
                            sci_name = row.get("SCI_NAME")
                            code = row.get("SPECIES_CODE")
                            if com_name and com_name not in v2025_names:
                                historical_names[com_name] = {
                                    "sci_name": sci_name,
                                    "species_code": code
                                }
                except Exception:
                    pass

    # 3. Resolve each invalid name
    auto_recs = {}
    auto_splits = {}
    for name_clean, hist_info in historical_names.items():
        sci = hist_info["sci_name"]
        code = hist_info["species_code"]
        
        # Match by scientific name
        v2025_matches = v2025_sci_to_names.get(sci, [])
        if len(v2025_matches) == 1:
            target = v2025_matches[0]
            auto_recs[name_clean] = f' Recommended Action: Update to <strong>"{target}"</strong> (automatically matched via scientific name <em>{sci}</em>).'
            continue
        elif len(v2025_matches) > 1:
            candidates_str = ", ".join(f'"{c}"' for c in sorted(v2025_matches))
            auto_recs[name_clean] = f' Recommended Action: Split into one of <strong>{candidates_str}</strong> (taxonomic split of <em>{sci}</em>).'
            auto_splits[name_clean] = sorted(v2025_matches)
            continue
            
        # Match by species code prefix / suffix split (e.g. categr -> Western Cattle-Egret / Eastern Cattle-Egret)
        if code:
            v2025_split_candidates = []
            for v2025_name, row in v2025_names.items():
                v_code = row.get("SPECIES_CODE", "")
                if v_code.startswith(code) and v_code != code and row.get("CATEGORY") == "species":
                    v2025_split_candidates.append(v2025_name)
                    
            if len(v2025_split_candidates) == 1:
                target = v2025_split_candidates[0]
                auto_recs[name_clean] = f' Recommended Action: Update to <strong>"{target}"</strong> (automatically matched via species code <em>{code}</em>).'
                continue
            elif len(v2025_split_candidates) > 1:
                candidates_str = ", ".join(f'"{c}"' for c in sorted(v2025_split_candidates))
                auto_recs[name_clean] = f' Recommended Action: Split into one of <strong>{candidates_str}</strong> (taxonomic split of code <em>{code}</em>).'
                auto_splits[name_clean] = sorted(v2025_split_candidates)
                continue
                
            # Match by exact species code
            if code in v2025_code_to_names:
                target = v2025_code_to_names[code]
                auto_recs[name_clean] = f' Recommended Action: Update to <strong>"{target}"</strong> (automatically matched via species code <em>{code}</em>).'
                continue
                
    return auto_recs, auto_splits, normalized_v2025
