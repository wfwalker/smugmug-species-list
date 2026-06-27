import sqlite3
import shutil
import os
from contextlib import contextmanager

# --- CENTRALIZED CONFIGURATION ---
LRCAT_PATH = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat" 
TEMP_DB_PATH = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"
BIRD_ROOT = "/41240/825689457%"

@contextmanager
def open_catalog(lrcat_path=LRCAT_PATH, temp_db=TEMP_DB_PATH):
    """
    Context manager that creates a temporary copy of the Lightroom catalog,
    establishes a connection, and yields a database cursor.
    Automatically cleans up the temporary file on exit.
    """
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except OSError as e:
            print(f"⚠️ Warning: Could not remove existing temporary database copy: {e}")
            
    shutil.copy2(lrcat_path, temp_db)
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        conn.close()
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except OSError as e:
                print(f"⚠️ Warning: Could not clean up temporary database copy: {e}")

def fetch_published_species(cursor):
    """
    Fetches the taxonomic list of all published bird species.
    Returns list of tuples: (FamilyGroup, SpeciesName, SpeciesCount)
    ordered taxonomically.
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
