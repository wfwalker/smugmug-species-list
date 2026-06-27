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
