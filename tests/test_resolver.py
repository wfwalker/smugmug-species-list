import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
import os
import tempfile
import csv
from lib.dashboard_resolver import normalize_name, build_automatic_resolutions

class TestResolver(unittest.TestCase):
    def test_normalize_name(self):
        self.assertEqual(normalize_name("Grey-headed Albatross"), "grayheadedalbatross")
        self.assertEqual(normalize_name("Western Cattle-Egret"), "westerncattleegret")
        self.assertEqual(normalize_name("House Wren"), "housewren")
        self.assertEqual(normalize_name("Large Cactus Finch"), "largecactusfinch")
        self.assertEqual(normalize_name("Large Cactus-Finch"), "largecactusfinch")
        self.assertEqual(normalize_name(""), "")

    def test_build_automatic_resolutions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Write mock v2025 taxonomy
            v2025_path = os.path.join(temp_dir, "eBird_taxonomy_v2025.csv")
            with open(v2025_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["PRIMARY_COM_NAME", "SCI_NAME", "SPECIES_CODE", "CATEGORY"])
                writer.writeheader()
                writer.writerow({
                    "PRIMARY_COM_NAME": "Western Cattle-Egret",
                    "SCI_NAME": "Bubulcus ibis",
                    "SPECIES_CODE": "categr1",
                    "CATEGORY": "species"
                })
                writer.writerow({
                    "PRIMARY_COM_NAME": "Eastern Cattle-Egret",
                    "SCI_NAME": "Bubulcus coromandus",
                    "SPECIES_CODE": "categr2",
                    "CATEGORY": "species"
                })
                writer.writerow({
                    "PRIMARY_COM_NAME": "Common Gallinule",
                    "SCI_NAME": "Gallinula galeata",
                    "SPECIES_CODE": "comgal",
                    "CATEGORY": "species"
                })
                writer.writerow({
                    "PRIMARY_COM_NAME": "Large Cactus-Finch",
                    "SCI_NAME": "Geospiza conirostris",
                    "SPECIES_CODE": "lacfin",
                    "CATEGORY": "species"
                })

            # 2. Write mock historical taxonomy (v2016) representing split/rename targets
            v2016_path = os.path.join(temp_dir, "eBird_taxonomy_v2016.csv")
            with open(v2016_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["PRIMARY_COM_NAME", "SCI_NAME", "SPECIES_CODE", "CATEGORY"])
                writer.writeheader()
                writer.writerow({
                    "PRIMARY_COM_NAME": "Cattle Egret",
                    "SCI_NAME": "Bubulcus oldname", # non-matching scientific name to trigger prefix code split detection
                    "SPECIES_CODE": "categr",
                    "CATEGORY": "species"
                })
                writer.writerow({
                    "PRIMARY_COM_NAME": "Common Moorhen",
                    "SCI_NAME": "Gallinula chloropus",
                    "SPECIES_CODE": "commoo",
                    "CATEGORY": "species"
                })

            auto_recs, auto_splits, normalized_v2025 = build_automatic_resolutions(temp_dir)

            # Assertions
            self.assertIn("Cattle Egret", auto_splits)
            self.assertEqual(auto_splits["Cattle Egret"], ["Eastern Cattle-Egret", "Western Cattle-Egret"])
            self.assertIn("westerncattleegret", normalized_v2025)
            self.assertEqual(normalized_v2025["westerncattleegret"], "Western Cattle-Egret")
            self.assertIn("largecactusfinch", normalized_v2025)
            self.assertEqual(normalized_v2025["largecactusfinch"], "Large Cactus-Finch")
            
if __name__ == "__main__":
    unittest.main()
