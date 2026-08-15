import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from lib.dashboard_report import generate_report

class TestReport(unittest.TestCase):
    def test_generate_report(self):
        # 1. Setup mock statistics
        label_stats = {
            "House Wren": {"Total_With_This_Label": 10, "Total_With_Keyword": 8, "Needs_Tagging": 2},
            "Andean Gull": {"Total_With_This_Label": 5, "Total_With_Keyword": 5, "Needs_Tagging": 0}
        }
        keyword_stats = {
            "House Wren": {"Total_With_Keyword": 8},
            "Andean Gull": {"Total_With_Keyword": 5},
            "Belcher's Gull": {"Total_With_Keyword": 2}
        }
        published_stats = {
            "House Wren": 5,
            "Andean Gull": 2,
            "Belcher's Gull": 2
        }
        json_species = {"House Wren", "Andean Gull", "Belcher's Gull", "Unpublished Species"}
        ebird_sightings = {"House Wren", "Andean Gull", "Belcher's Gull", "Sighted Only Species"}
        missing_location_counts = {
            "House Wren": 1
        }
        fully_migrated_species = {"Andean Gull"}
        valid_taxonomy_names = {"House Wren", "Andean Gull", "Belcher's Gull"}

        merged_rows = generate_report(
            label_stats,
            keyword_stats,
            published_stats,
            json_species,
            ebird_sightings,
            missing_location_counts,
            fully_migrated_species,
            valid_taxonomy_names
        )

        # 2. Assertions
        # Total rows should exclude "Unpublished Species" and "Sighted Only Species" 
        # because they have total_label=0, total_keyword=0, and published_count=0.
        self.assertEqual(len(merged_rows), 3)

        # Confirm alphabetical sorting (Andean Gull, Belcher's Gull, House Wren)
        self.assertEqual(merged_rows[0]["species_name"], "Andean Gull")
        self.assertEqual(merged_rows[1]["species_name"], "Belcher's Gull")
        self.assertEqual(merged_rows[2]["species_name"], "House Wren")

        # Confirm fields
        self.assertEqual(merged_rows[2]["total_label"], 10)
        self.assertEqual(merged_rows[2]["total_keyword"], 8)
        self.assertEqual(merged_rows[2]["needs_tagging"], 2)
        self.assertEqual(merged_rows[2]["missing_loc_count"], 1)
        self.assertEqual(merged_rows[2]["is_valid_taxonomy"], "Yes")

if __name__ == "__main__":
    unittest.main()
