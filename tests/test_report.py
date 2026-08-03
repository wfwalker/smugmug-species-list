import unittest
from dashboard_report import generate_report

class TestReport(unittest.TestCase):
    def test_generate_report(self):
        # 1. Setup mock statistics
        label_stats = {
            "House Wren": {"total_label": 10, "keyword_on_label": 8, "needs_tagging": 2},
            "Andean Gull": {"total_label": 5, "keyword_on_label": 5, "needs_tagging": 0}
        }
        keyword_stats = {
            "House Wren": 8,
            "Andean Gull": 5,
            "Belcher's Gull": 2
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
