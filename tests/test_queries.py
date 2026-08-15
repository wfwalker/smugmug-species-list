import unittest
import sqlite3
import sys
import os

# Add project root to path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.shared_queries import (
    query_alphabetical_species,
    query_taxonomic_species,
    query_chronological_photos
)

class TestSharedQueries(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        
        # Create mock tables
        self.cursor.executescript("""
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            colorLabels TEXT,
            rootFile INTEGER,
            captureTime TEXT
        );
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            baseName TEXT,
            extension TEXT,
            folder INTEGER
        );
        CREATE TABLE AgLibraryFolder (
            id_local INTEGER PRIMARY KEY,
            pathFromRoot TEXT,
            rootFolder INTEGER
        );
        CREATE TABLE AgLibraryRootFolder (
            id_local INTEGER PRIMARY KEY,
            absolutePath TEXT
        );
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            name TEXT,
            genealogy TEXT,
            parent INTEGER
        );
        CREATE TABLE AgLibraryKeywordImage (
            id_local INTEGER PRIMARY KEY,
            image INTEGER,
            tag INTEGER
        );
        CREATE TABLE AgLibraryPublishedCollectionImage (
            image INTEGER,
            collection INTEGER
        );
        CREATE TABLE AgLibraryPublishedCollection (
            id_local INTEGER PRIMARY KEY,
            name TEXT,
            parent INTEGER
        );
        CREATE TABLE AgRemotePhoto (
            id_local INTEGER PRIMARY KEY,
            photo INTEGER,
            collection INTEGER,
            url TEXT
        );
        CREATE TABLE AgHarvestedIptcMetadata (
            image INTEGER PRIMARY KEY,
            locationRef INTEGER,
            cityRef INTEGER,
            stateRef INTEGER,
            countryRef INTEGER
        );
        CREATE TABLE AgInternedIptcLocation (
            id_local INTEGER PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE AgInternedIptcCity (
            id_local INTEGER PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE AgInternedIptcState (
            id_local INTEGER PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE AgInternedIptcCountry (
            id_local INTEGER PRIMARY KEY,
            value TEXT
        );
        """)
        self.conn.commit()

        # Insert generic mock items for published photos
        # BIRD_ROOT = "/41240/825689457%"
        # House Wren has ID 1 and parent ID 1000 (which acts as a family group keyword)
        self.cursor.execute("INSERT INTO AgLibraryKeyword VALUES (1000, 'Troglodytidae', '/41240/825689457/', NULL)")
        self.cursor.execute("INSERT INTO AgLibraryKeyword VALUES (1, 'House Wren', '/41240/825689457/1000/1/', 1000)")
        self.cursor.execute("INSERT INTO AgLibraryKeyword VALUES (2, 'American Robin', '/41240/825689457/1000/2/', 1000)")
        
        self.cursor.execute("INSERT INTO AgLibraryRootFolder VALUES (10, '/photos/')")
        self.cursor.execute("INSERT INTO AgLibraryFolder VALUES (20, '2026/', 10)")
        self.cursor.execute("INSERT INTO AgLibraryFile VALUES (30, 'file1', 'jpg', 20)")
        self.cursor.execute("INSERT INTO AgLibraryFile VALUES (31, 'file2', 'jpg', 20)")
        
        self.cursor.execute("INSERT INTO Adobe_images VALUES (100, 'House Wren', 30, '2026-05-12T10:30:00')")
        self.cursor.execute("INSERT INTO Adobe_images VALUES (101, 'American Robin', 31, '2026-05-13T11:00:00')")
        
        self.cursor.execute("INSERT INTO AgLibraryKeywordImage VALUES (1, 100, 1)")
        self.cursor.execute("INSERT INTO AgLibraryKeywordImage VALUES (2, 101, 2)")
        
        # SmugMug published collection needs parent named 'SmugMug'
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollection VALUES (60, 'SmugMug', NULL)")
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollection VALUES (50, 'SmugMug Portfolio', 60)")
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollectionImage VALUES (100, 50)")
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollectionImage VALUES (101, 50)")
        
        self.cursor.execute("INSERT INTO AgRemotePhoto VALUES (1, 100, 50, 'https://billwalker.smugmug.com/wren')")
        self.cursor.execute("INSERT INTO AgRemotePhoto VALUES (2, 101, 50, 'https://billwalker.smugmug.com/robin')")
        
        self.cursor.execute("INSERT INTO AgHarvestedIptcMetadata VALUES (100, 200, 300, 400, 500)")
        self.cursor.execute("INSERT INTO AgInternedIptcLocation VALUES (200, 'My Yard')")
        self.cursor.execute("INSERT INTO AgInternedIptcCity VALUES (300, 'San Jose')")
        self.cursor.execute("INSERT INTO AgInternedIptcState VALUES (400, 'California')")
        self.cursor.execute("INSERT INTO AgInternedIptcCountry VALUES (500, 'USA')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_query_alphabetical_species(self):
        results = query_alphabetical_species(self.cursor)
        self.assertEqual(len(results), 2)
        # Should be sorted alphabetically: American Robin, then House Wren
        self.assertEqual(results[0][0], "American Robin")
        self.assertEqual(results[1][0], "House Wren")
        self.assertEqual(results[0][1], 1)
        self.assertEqual(results[0][2], "https://billwalker.smugmug.com/robin")

    def test_query_taxonomic_species(self):
        results = query_taxonomic_species(self.cursor)
        self.assertEqual(len(results), 2)
        # Sorted by FamilyId (1 then 2)
        self.assertEqual(results[0][1], "House Wren")
        self.assertEqual(results[1][1], "American Robin")

    def test_query_chronological_photos(self):
        results = query_chronological_photos(self.cursor)
        self.assertIn("house wren", results)
        self.assertIn("american robin", results)
        self.assertEqual(results["house wren"]["date"], "2026-05-12")
        self.assertEqual(results["house wren"]["location"], "My Yard, San Jose, California, USA")
