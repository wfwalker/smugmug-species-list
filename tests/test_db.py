import unittest
import sqlite3
from dashboard_db import fetch_db_statistics

class TestDB(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        
        # Create mock Lightroom tables
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
            genealogy TEXT
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

    def tearDown(self):
        self.conn.close()

    def test_fetch_db_statistics(self):
        # 1. Insert mock keywords
        # BIRD_ROOT = "/41240/825689457%"
        # House Wren has ID 1 and genealogy starts with BIRD_ROOT prefix
        self.cursor.execute("INSERT INTO AgLibraryKeyword VALUES (1, 'House Wren', '/41240/825689457/1/')")
        
        # 2. Insert mock files and folder paths
        self.cursor.execute("INSERT INTO AgLibraryRootFolder VALUES (10, '/path/to/photos/')")
        self.cursor.execute("INSERT INTO AgLibraryFolder VALUES (20, '2026/05/', 10)")
        self.cursor.execute("INSERT INTO AgLibraryFile VALUES (30, 'D86A7390', 'CR3', 20)")
        
        # 3. Insert mock image with color label
        self.cursor.execute("INSERT INTO Adobe_images VALUES (1, 'House Wren', 30, '2026-05-12T10:30:00')")
        
        # 4. Link keyword to image
        self.cursor.execute("INSERT INTO AgLibraryKeywordImage VALUES (1, 1, 1)")

        # 5. Insert mock SmugMug published collection
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollection VALUES (50, 'SmugMug Portfolio', NULL)")
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollection VALUES (51, 'Wrens Collection', 50)")
        self.cursor.execute("INSERT INTO AgLibraryPublishedCollectionImage VALUES (1, 51)")

        # 6. Insert metadata (missing location)
        self.cursor.execute("INSERT INTO AgHarvestedIptcMetadata VALUES (1, NULL, NULL, NULL, NULL)")
        
        # 7. Insert an untagged image (needs tagging)
        self.cursor.execute("INSERT INTO AgLibraryFile VALUES (31, 'D86A7391', 'CR3', 20)")
        self.cursor.execute("INSERT INTO Adobe_images VALUES (2, 'Anhinga', 31, '2026-05-12T10:35:00')")
        self.cursor.execute("INSERT INTO AgHarvestedIptcMetadata VALUES (2, NULL, NULL, NULL, NULL)")

        self.conn.commit()

        # Run stats fetch
        excluded_tags = ["People", "Wildlife"]
        (
            label_stats, 
            keyword_stats, 
            published_stats, 
            missing_location_counts, 
            photos_missing_location, 
            earliest_photos,
            fully_migrated_species,
            needs_tagging_examples
        ) = fetch_db_statistics(self.cursor, excluded_tags)

        # Assertions
        self.assertIn("House Wren", label_stats)
        self.assertEqual(label_stats["House Wren"]["total_label"], 1)
        self.assertEqual(label_stats["House Wren"]["keyword_on_label"], 1)
        self.assertEqual(label_stats["House Wren"]["needs_tagging"], 0)

        self.assertIn("House Wren", keyword_stats)
        self.assertEqual(keyword_stats["House Wren"], 1)

        self.assertIn("House Wren", published_stats)
        self.assertEqual(published_stats["House Wren"], 1)

        self.assertIn("House Wren", missing_location_counts)
        self.assertEqual(missing_location_counts["House Wren"], 1)

        self.assertEqual(len(photos_missing_location), 1)
        self.assertEqual(photos_missing_location[0][0], "House Wren")
        self.assertEqual(photos_missing_location[0][1], "D86A7390.CR3")

        self.assertIn("House Wren", earliest_photos)
        self.assertEqual(earliest_photos["House Wren"]["date"], "2026-05-12")

        # Test needs_tagging_examples for Anhinga
        self.assertIn("Anhinga", needs_tagging_examples)
        self.assertEqual(needs_tagging_examples["Anhinga"][0][0], "D86A7391.CR3")
        self.assertEqual(needs_tagging_examples["Anhinga"][0][1], "2026/05/")
        self.assertEqual(earliest_photos["House Wren"]["date"], "2026-05-12")

if __name__ == "__main__":
    unittest.main()
