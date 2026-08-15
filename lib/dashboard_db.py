from lib.lrcat_utils import BIRD_ROOT

def fetch_db_statistics(cursor, excluded_tags):
    """
    Queries Lightroom catalog database for keyword, color labels, and location status info.
    Returns: (label_stats, keyword_stats, published_stats, missing_location_counts, missing_location_photos)
    """
    # Exclude tags
    excluded_tags_sql = ", ".join(f"'{tag}'" for tag in excluded_tags)
    exclude_clause = f"""
      AND i.id_local NOT IN (
          SELECT ki_ex.image 
          FROM AgLibraryKeywordImage ki_ex
          JOIN AgLibraryKeyword k_ex ON ki_ex.tag = k_ex.id_local
          WHERE k_ex.name IN ({excluded_tags_sql})
      )
    """

    # Query A: Label-based statistics (Legacy color label info)
    query_label = """
    SELECT 
        i.colorLabels AS SpeciesName,
        COUNT(DISTINCT i.id_local) AS Total_With_This_Label,
        COUNT(DISTINCT ki.image) AS Total_With_Keyword,
        (COUNT(DISTINCT i.id_local) - COUNT(DISTINCT ki.image)) AS Needs_Tagging
    FROM Adobe_images i
    LEFT JOIN AgLibraryKeyword k 
        ON i.colorLabels = k.name 
        AND k.genealogy LIKE ?
    LEFT JOIN AgLibraryKeywordImage ki 
        ON i.id_local = ki.image AND k.id_local = ki.tag
    WHERE i.colorLabels != '' 
      AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
      {exclude_clause}
    GROUP BY i.colorLabels;
    """

    # Query B: Keyword-based statistics (Taxonomic keyword info)
    query_keyword = """
    SELECT 
        k.name AS SpeciesName,
        COUNT(DISTINCT i.id_local) AS Total_With_Keyword
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    WHERE k.genealogy LIKE ?
      {exclude_clause}
    GROUP BY k.name;
    """

    # Query C: De-duplicated SmugMug published counts (Keyword + Label published photos)
    query_published = """
    SELECT 
        SpeciesName,
        COUNT(DISTINCT ImageId) AS PublishedCount
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            i.id_local AS ImageId
        FROM Adobe_images i
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        WHERE i.colorLabels != '' 
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
          {exclude_clause}
        
        UNION
        
        SELECT 
            k.name AS SpeciesName,
            i.id_local AS ImageId
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        WHERE k.genealogy LIKE ?
          {exclude_clause}
    )
    GROUP BY SpeciesName;
    """

    # Query D: Count of published photos missing locations (grouped by species)
    query_missing_location_counts = """
    SELECT 
        SpeciesName,
        COUNT(DISTINCT ImageId) AS MissingCount
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            i.id_local AS ImageId
        FROM Adobe_images i
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        WHERE i.colorLabels != '' 
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
          AND (iptc.locationRef IS NULL OR iptc.locationRef = '')
          AND (iptc.cityRef IS NULL OR iptc.cityRef = '')
          AND (iptc.stateRef IS NULL OR iptc.stateRef = '')
          AND (iptc.countryRef IS NULL OR iptc.countryRef = '')
          {exclude_clause}
        
        UNION ALL
        
        SELECT 
            k.name AS SpeciesName,
            i.id_local AS ImageId
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        WHERE k.genealogy LIKE ?
          AND (iptc.locationRef IS NULL OR iptc.locationRef = '')
          AND (iptc.cityRef IS NULL OR iptc.cityRef = '')
          AND (iptc.stateRef IS NULL OR iptc.stateRef = '')
          AND (iptc.countryRef IS NULL OR iptc.countryRef = '')
          {exclude_clause}
    )
    GROUP BY SpeciesName;
    """

    # Query E: Specific detailed published photos missing locations
    query_photos_missing_location = """
    SELECT DISTINCT
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime
    FROM (
        SELECT 
            i.colorLabels AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime
        FROM Adobe_images i
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        WHERE i.colorLabels != '' 
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
          AND (iptc.locationRef IS NULL OR iptc.locationRef = '')
          AND (iptc.cityRef IS NULL OR iptc.cityRef = '')
          AND (iptc.stateRef IS NULL OR iptc.stateRef = '')
          AND (iptc.countryRef IS NULL OR iptc.countryRef = '')
          {exclude_clause}
          
        UNION ALL
        
        SELECT 
            k.name AS SpeciesName,
            f.baseName || '.' || f.extension AS Filename,
            parent_coll.name AS CollectionName,
            i.captureTime AS CaptureTime
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
            AND parent_coll.name LIKE '%SmugMug%'
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        WHERE k.genealogy LIKE ?
          AND (iptc.locationRef IS NULL OR iptc.locationRef = '')
          AND (iptc.cityRef IS NULL OR iptc.cityRef = '')
          AND (iptc.stateRef IS NULL OR iptc.stateRef = '')
          AND (iptc.countryRef IS NULL OR iptc.countryRef = '')
          {exclude_clause}
    )
    ORDER BY SpeciesName, CaptureTime DESC;
    """

    # Query F: Earliest photos for each species (with full location text)
    query_earliest_photos = """
    SELECT 
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime,
        Location, City, State, Country
    FROM (
        SELECT 
            SpeciesName,
            Filename,
            CollectionName,
            CaptureTime,
            Location, City, State, Country,
            ROW_NUMBER() OVER (PARTITION BY SpeciesName ORDER BY CaptureTime ASC) as rn
        FROM (
            SELECT 
                i.colorLabels AS SpeciesName,
                f.baseName || '.' || f.extension AS Filename,
                parent_coll.name AS CollectionName,
                i.captureTime AS CaptureTime,
                loc.value AS Location,
                city.value AS City,
                state.value AS State,
                country.value AS Country
            FROM Adobe_images i
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
            JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
            JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
                AND parent_coll.name LIKE '%SmugMug%'
            LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
            LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
            LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
            LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
            LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
            WHERE i.colorLabels != '' 
              AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
              {exclude_clause}
              
            UNION ALL
            
            SELECT 
                k.name AS SpeciesName,
                f.baseName || '.' || f.extension AS Filename,
                parent_coll.name AS CollectionName,
                i.captureTime AS CaptureTime,
                loc.value AS Location,
                city.value AS City,
                state.value AS State,
                country.value AS Country
            FROM AgLibraryKeyword k
            JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
            JOIN Adobe_images i ON ki.image = i.id_local
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
            JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
            JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
                AND parent_coll.name LIKE '%SmugMug%'
            LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
            LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
            LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
            LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
            LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
            WHERE k.genealogy LIKE ?
              {exclude_clause}
        )
    )
    WHERE rn = 1;
    """

    # Query G: Fully migrated check (contains keyword but NO color labels)
    query_fully_migrated = """
    SELECT DISTINCT k.name AS SpeciesName
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    LEFT JOIN Adobe_images i_lbl 
      ON i.id_local = i_lbl.id_local 
      AND i_lbl.colorLabels = k.name
    WHERE k.genealogy LIKE ?
      AND i_lbl.id_local IS NULL
      {exclude_clause};
    """

    # Query H: Color-labeled photos needing to be tagged in Lightroom (label exists, keyword missing)
    query_needs_tagging_examples = """
    SELECT 
        i.colorLabels AS SpeciesName,
        f.baseName || '.' || f.extension AS Filename,
        fol.pathFromRoot AS FolderPath,
        i.captureTime AS CaptureTime
    FROM Adobe_images i
    JOIN AgLibraryFile f ON i.rootFile = f.id_local
    JOIN AgLibraryFolder fol ON f.folder = fol.id_local
    LEFT JOIN AgLibraryKeyword k 
        ON i.colorLabels = k.name 
        AND k.genealogy LIKE ?
    LEFT JOIN AgLibraryKeywordImage ki 
        ON i.id_local = ki.image AND k.id_local = ki.tag
    WHERE i.colorLabels != '' 
      AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple', {excluded_tags_sql})
      AND ki.image IS NULL
      {exclude_clause}
    ORDER BY SpeciesName, Filename;
    """

    # Bulk replacement of placeholders
    query_label = query_label.replace("{exclude_clause}", exclude_clause).replace("{excluded_tags_sql}", excluded_tags_sql)
    query_keyword = query_keyword.replace("{exclude_clause}", exclude_clause)
    query_published = query_published.replace("{exclude_clause}", exclude_clause).replace("{excluded_tags_sql}", excluded_tags_sql)
    query_missing_location_counts = query_missing_location_counts.replace("{exclude_clause}", exclude_clause).replace("{excluded_tags_sql}", excluded_tags_sql)
    query_photos_missing_location = query_photos_missing_location.replace("{exclude_clause}", exclude_clause).replace("{excluded_tags_sql}", excluded_tags_sql)
    query_earliest_photos = query_earliest_photos.replace("{exclude_clause}", exclude_clause).replace("{excluded_tags_sql}", excluded_tags_sql)
    query_fully_migrated = query_fully_migrated.replace("{exclude_clause}", exclude_clause)
    query_needs_tagging_examples = query_needs_tagging_examples.replace("{exclude_clause}", exclude_clause).replace("{excluded_tags_sql}", excluded_tags_sql)

    # Fetch label data
    cursor.execute(query_label, (BIRD_ROOT,))
    label_stats = {
        row[0]: {
            "Total_With_This_Label": row[1],
            "Total_With_Keyword": row[2],
            "Needs_Tagging": row[3]
        }
        for row in cursor.fetchall()
    }

    # Fetch keyword data
    cursor.execute(query_keyword, (BIRD_ROOT,))
    keyword_stats = {
        row[0]: {
            "Total_With_Keyword": row[1]
        }
        for row in cursor.fetchall()
    }

    # Fetch published counts
    cursor.execute(query_published, (BIRD_ROOT,))
    published_stats = {
        row[0]: row[1]
        for row in cursor.fetchall()
    }

    # Fetch missing location counts
    cursor.execute(query_missing_location_counts, (BIRD_ROOT,))
    missing_location_counts = {
        row[0]: row[1]
        for row in cursor.fetchall()
    }

    # Fetch specific photos missing location details
    cursor.execute(query_photos_missing_location, (BIRD_ROOT,))
    missing_location_photos = {}
    for spec, filename, coll, cap_time in cursor.fetchall():
        if spec not in missing_location_photos:
            missing_location_photos[spec] = []
        missing_location_photos[spec].append({
            "filename": filename,
            "collection": coll,
            "capture_time": cap_time
        })

    # Fetch earliest photos for each species
    cursor.execute(query_earliest_photos, (BIRD_ROOT,))
    earliest_photos = {}
    for spec, filename, coll, cap_time, loc, city, state, country in cursor.fetchall():
        from lib.lrcat_utils import format_location
        formatted_loc = format_location(loc, city, state, country)
        earliest_photos[spec] = {
            "filename": filename,
            "collection": coll,
            "capture_time": cap_time,
            "location": formatted_loc
        }

    # Fetch fully migrated species set
    cursor.execute(query_fully_migrated, (BIRD_ROOT,))
    fully_migrated = {row[0] for row in cursor.fetchall()}

    # Fetch needs tagging examples
    cursor.execute(query_needs_tagging_examples, (BIRD_ROOT,))
    needs_tagging_examples = {}
    for spec, filename, folder_path, cap_time in cursor.fetchall():
        if spec not in needs_tagging_examples:
            needs_tagging_examples[spec] = []
        needs_tagging_examples[spec].append({
            "filename": filename,
            "folder_path": folder_path,
            "capture_time": cap_time
        })

    return (
        label_stats,
        keyword_stats,
        published_stats,
        missing_location_counts,
        missing_location_photos,
        earliest_photos,
        fully_migrated,
        needs_tagging_examples
    )
