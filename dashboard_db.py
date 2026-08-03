from lrcat_utils import BIRD_ROOT, format_location

def fetch_db_statistics(cursor, excluded_tags):
    """
    Queries the Lightroom database and returns:
    - label_stats: dict of label -> {total_label, keyword_on_label, needs_tagging}
    - keyword_stats: dict of keyword -> count
    - published_stats: dict of species -> published_count
    - missing_location_counts: dict of species -> count of photos missing locations
    - photos_missing_location: list of tuples (Species, Filename, Collection, Date)
    - earliest_photos: dict of Species -> {filename, collection, date, location}
    - fully_migrated_species: set of species names that have at least one fully migrated published photo
    """
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
      AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
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
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
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

    # Query D: Count of published photos missing location details per species
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
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
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
          AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
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
    ORDER BY SpeciesName, CaptureTime;
    """

    # Query F: Details of the earliest photo for all published species
    query_earliest_photos = """
    WITH RankedPhotos AS (
        SELECT 
            SpeciesName,
            Filename,
            CollectionName,
            CaptureTime,
            Location,
            City,
            State,
            Country,
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
              AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
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
    SELECT 
        SpeciesName,
        Filename,
        CollectionName,
        CaptureTime,
        Location,
        City,
        State,
        Country
    FROM RankedPhotos
    WHERE rn = 1;
    """

    # Query G: Find species with at least one published photo having label + keyword + location
    query_fully_migrated = """
    SELECT DISTINCT
        k.name AS SpeciesName
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
    JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
    JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
        AND parent_coll.name LIKE '%SmugMug%'
    LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
    WHERE k.genealogy LIKE ?
      AND i.colorLabels = k.name
      AND (
          (iptc.locationRef IS NOT NULL AND iptc.locationRef != '') OR
          (iptc.cityRef IS NOT NULL AND iptc.cityRef != '') OR
          (iptc.stateRef IS NOT NULL AND iptc.stateRef != '') OR
          (iptc.countryRef IS NOT NULL AND iptc.countryRef != '')
      )
      {exclude_clause};
    """

    # Bulk replacement of placeholders
    query_label = query_label.replace("{exclude_clause}", exclude_clause)
    query_keyword = query_keyword.replace("{exclude_clause}", exclude_clause)
    query_published = query_published.replace("{exclude_clause}", exclude_clause)
    query_missing_location_counts = query_missing_location_counts.replace("{exclude_clause}", exclude_clause)
    query_photos_missing_location = query_photos_missing_location.replace("{exclude_clause}", exclude_clause)
    query_earliest_photos = query_earliest_photos.replace("{exclude_clause}", exclude_clause)
    query_fully_migrated = query_fully_migrated.replace("{exclude_clause}", exclude_clause)

    # Fetch label data
    cursor.execute(query_label, (BIRD_ROOT,))
    label_stats = {
        row[0]: {
            "total_label": row[1],
            "keyword_on_label": row[2],
            "needs_tagging": row[3]
        }
        for row in cursor.fetchall()
    }

    # Fetch keyword data
    cursor.execute(query_keyword, (BIRD_ROOT,))
    keyword_stats = {row[0]: row[1] for row in cursor.fetchall()}

    # Fetch published data
    cursor.execute(query_published, (BIRD_ROOT,))
    published_stats = {row[0]: row[1] for row in cursor.fetchall()}

    # Fetch missing location counts
    cursor.execute(query_missing_location_counts, (BIRD_ROOT,))
    missing_location_counts = {row[0]: row[1] for row in cursor.fetchall()}

    # Fetch detailed missing location photos list
    cursor.execute(query_photos_missing_location, (BIRD_ROOT,))
    photos_missing_location = cursor.fetchall()

    # Fetch earliest photo details
    cursor.execute(query_earliest_photos, (BIRD_ROOT,))
    earliest_photos = {}
    for r in cursor.fetchall():
        species = r[0]
        filename = r[1]
        collection = r[2]
        capture_time = r[3]
        formatted_loc = format_location(r[4], r[5], r[6], r[7])
        earliest_photos[species] = {
            "filename": filename,
            "collection": collection,
            "date": capture_time[:10] if capture_time else "N/A",
            "location": formatted_loc
        }

    # Execute query G for fully migrated species
    cursor.execute(query_fully_migrated, (BIRD_ROOT,))
    fully_migrated_species = {row[0] for row in cursor.fetchall()}

    return (
        label_stats, 
        keyword_stats, 
        published_stats, 
        missing_location_counts, 
        photos_missing_location, 
        earliest_photos,
        fully_migrated_species
    )
