def generate_report(label_stats, keyword_stats, published_stats, json_species, ebird_sightings, missing_location_counts, fully_migrated_species, valid_taxonomy_names):
    """Merges all stats sources into a unified list of species records, sorted alphabetically."""
    # 1. Combine all species names from label, keyword, JSON, eBird sightings, and published stats
    all_species = set(label_stats.keys()) | set(keyword_stats.keys()) | set(published_stats.keys()) | json_species | ebird_sightings
    
    # Filter out empty or None values
    all_species = {s for s in all_species if s}
    
    valid_names_lower = {n.lower() for n in valid_taxonomy_names}
    
    # 2. Build rows
    merged_rows = []
    for species_name in all_species:
        # Check presence in main datasets
        in_json = "Yes" if species_name in json_species else "No"
        in_ebird = "Yes" if species_name in ebird_sightings else "No"
        
        # Get count stats
        # Note: in fetch_db_statistics, the dictionary keys for label_stats are:
        # "Total_With_This_Label", "Total_With_Keyword", "Needs_Tagging"
        # and for keyword_stats are "Total_With_Keyword"
        total_label = label_stats.get(species_name, {}).get("Total_With_This_Label", 0)
        
        kw_stat = keyword_stats.get(species_name, {})
        if isinstance(kw_stat, dict):
            total_keyword = kw_stat.get("Total_With_Keyword", 0)
        else:
            total_keyword = kw_stat
            
        published_count = published_stats.get(species_name, 0)
        needs_tagging = label_stats.get(species_name, {}).get("Needs_Tagging", 0)
        missing_loc_count = missing_location_counts.get(species_name, 0)
        
        # Exclude placeholder rows: we only want rows for species that actually have photos in the Lightroom catalog.
        # This is defined as having total_label > 0 OR total_keyword > 0 OR published_count > 0.
        if total_label == 0 and total_keyword == 0 and published_count == 0:
            continue
            
        # Taxonomy validity check
        is_valid_taxonomy = "Yes" if species_name.lower() in valid_names_lower else "No"
        
        merged_rows.append({
            "species_name": species_name,
            "in_json": in_json,
            "in_ebird": in_ebird,
            "is_valid_taxonomy": is_valid_taxonomy,
            "total_label": total_label,
            "total_keyword": total_keyword,
            "published_count": published_count,
            "needs_tagging": needs_tagging,
            "missing_loc_count": missing_loc_count
        })

    merged_rows.sort(key=lambda x: x["species_name"].lower())
    return merged_rows
