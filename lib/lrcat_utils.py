import os
import sqlite3
from contextlib import contextmanager

# Catalog file paths
LRCAT_PATH = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat"
TEMP_DB_PATH = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"

# Bird taxonomy root keyword tag genealogy prefix
BIRD_ROOT = "/41240/825689457%"

@contextmanager
def open_catalog(db_path=TEMP_DB_PATH, src_path=LRCAT_PATH):
    """
    Safely opens a read-only copy of the Lightroom catalog file in a transaction.
    Copies the original .lrcat file to a temp location before reading to prevent locking/corruption.
    """
    if not os.path.exists(src_path):
        # Fallback to local subdirectory check for portability / tests
        alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Lightroom Catalog-v13-3.lrcat")
        if os.path.exists(alt_path):
            src_path = alt_path
        else:
            raise FileNotFoundError(f"Lightroom catalog not found at {src_path}")
            
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Copy catalog to temp path
    import shutil
    shutil.copy2(src_path, db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        conn.close()
        # Clean up temp file
        try:
            os.remove(db_path)
        except OSError:
            pass

def fetch_published_species(cursor):
    """
    Fetches all bird species from the Lightroom database that have at least one photo
    published in a SmugMug collection.
    Returns: list of tuples (FamilyGroup, SpeciesName, SpeciesCount)
    """
    query = """
    SELECT 
        parent_k.name AS FamilyGroup,
        k.name AS SpeciesName,
        COUNT(DISTINCT i.id_local) AS SpeciesCount
    FROM AgLibraryKeyword k
    JOIN AgLibraryKeyword parent_k ON k.parent = parent_k.id_local
    JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
    JOIN Adobe_images i ON ki.image = i.id_local
    JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
    JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
    JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
    WHERE k.genealogy LIKE ?
      AND parent_coll.name LIKE '%SmugMug%'
      AND k.name NOT LIKE '{%'
    GROUP BY k.name
    ORDER BY parent_k.id_local, k.id_local;
    """
    cursor.execute(query, (BIRD_ROOT,))
    return cursor.fetchall()

def make_relative_url(url):
    """Converts absolute SmugMug URLs into site-relative paths to optimize HTML size."""
    if not url:
        return ""
    for domain in ["https://billwalker.smugmug.com", "https://www.birdwalker.com"]:
        if url.startswith(domain):
            return url[len(domain):]
    return url

def format_location(loc, city, state, country):
    """Formats Lightroom location components into a readable string."""
    parts = []
    if loc and loc != 'No Location':
        parts.append(loc)
    if city and city != 'No City' and city != loc:
        parts.append(city)
    if state:
        parts.append(state)
    if country:
        parts.append(country)
    return ", ".join(parts) if parts else "Unknown Location"
