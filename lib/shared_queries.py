import os
from lrcat_utils import BIRD_ROOT, format_location

def query_alphabetical_species(cursor):
    """
    Fetches published species sorted alphabetically.
    Returns: list of tuples (SpeciesName, photo_count, SmugMugUrl)
    """
    query = """
    WITH RankedPhotos AS (
        SELECT 
            parent_k.id_local AS FamilyId,
            k.id_local AS SpeciesId,
            k.name AS SpeciesName,
            rp.url AS SmugMugUrl,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.collection = pci.collection
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        SpeciesName,
        photo_count,
        SmugMugUrl
    FROM RankedPhotos
    WHERE rn = 1;
    """
    cursor.execute(query, (BIRD_ROOT,))
    raw_results = cursor.fetchall()
    return sorted(raw_results, key=lambda x: x[0].lower())

def query_taxonomic_species(cursor):
    """
    Fetches published species sorted taxonomically.
    Returns: list of tuples (FamilyGroup, SpeciesName, photo_count, SmugMugUrl)
    """
    query = """
    WITH RankedPhotos AS (
        SELECT 
            CASE 
                WHEN parent_k.name LIKE 'eBird taxonomy%' THEN k.id_local 
                ELSE parent_k.id_local 
            END AS FamilyId,
            k.id_local AS SpeciesId,
            CASE 
                WHEN parent_k.name LIKE 'eBird taxonomy%' THEN k.name 
                ELSE parent_k.name 
            END AS FamilyGroup,
            k.name AS SpeciesName,
            rp.url AS SmugMugUrl,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.collection = pci.collection
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        FamilyGroup,
        SpeciesName,
        photo_count,
        SmugMugUrl
    FROM RankedPhotos
    WHERE rn = 1
    ORDER BY FamilyId, SpeciesId;
    """
    cursor.execute(query, (BIRD_ROOT,))
    return cursor.fetchall()

def query_chronological_photos(cursor):
    """
    Queries Lightroom for the earliest published SmugMug photo details of each species.
    Returns: dict of species_name_lower -> {name, date, location, url, photo_count}
    """
    query = """
    WITH PublishedPhotos AS (
        SELECT 
            k.name AS SpeciesName,
            i.captureTime AS CaptureTime,
            loc.value AS Location,
            city.value AS City,
            state.value AS State,
            country.value AS Country,
            rp.url AS SmugMugUrl,
            COUNT(*) OVER (PARTITION BY k.name) as photo_count,
            ROW_NUMBER() OVER (PARTITION BY k.name ORDER BY i.captureTime ASC) as rn
        FROM AgLibraryKeyword k
        JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
        JOIN Adobe_images i ON ki.image = i.id_local
        JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
        JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
        JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
        LEFT JOIN AgRemotePhoto rp ON i.id_local = rp.photo AND rp.collection = pci.collection
        LEFT JOIN AgHarvestedIptcMetadata iptc ON i.id_local = iptc.image
        LEFT JOIN AgInternedIptcLocation loc ON iptc.locationRef = loc.id_local
        LEFT JOIN AgInternedIptcCity city ON iptc.cityRef = city.id_local
        LEFT JOIN AgInternedIptcState state ON iptc.stateRef = state.id_local
        LEFT JOIN AgInternedIptcCountry country ON iptc.countryRef = country.id_local
        WHERE k.genealogy LIKE ?
          AND parent_coll.name LIKE '%SmugMug%'
          AND k.name NOT LIKE '{%'
    )
    SELECT 
        SpeciesName,
        CaptureTime,
        Location, City, State, Country,
        SmugMugUrl,
        photo_count
    FROM PublishedPhotos
    WHERE rn = 1;
    """
    cursor.execute(query, (BIRD_ROOT,))
    rows = cursor.fetchall()
    
    published_photos = {}
    for r in rows:
        species_name = r[0]
        capture_time = r[1]
        loc = r[2]
        city = r[3]
        state = r[4]
        country = r[5]
        url = r[6]
        photo_count = r[7]
        
        formatted_loc = format_location(loc, city, state, country)
        date_only = capture_time[:10] if capture_time else "Unknown Date"
        
        published_photos[species_name.lower().strip()] = {
            "name": species_name.strip(),
            "date": date_only,
            "location": formatted_loc,
            "url": url,
            "photo_count": photo_count
        }
    return published_photos
