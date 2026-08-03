import unittest
import os
import tempfile
from dashboard_writer import save_to_html

class TestWriter(unittest.TestCase):
    def test_missing_ebird_count_rendered(self):
        # Setup mock data for save_to_html
        merged_rows = [
            {
                "species_name": "House Wren",
                "in_json": "Yes",
                "in_ebird": "No", # published count > 0, in_ebird = No -> Missing eBird count should be 1
                "is_valid_taxonomy": "Yes",
                "total_label": 5,
                "total_keyword": 5,
                "published_count": 3,
                "needs_tagging": 0,
                "missing_loc_count": 0
            }
        ]
        
        photos_missing_location = []
        earliest_photos = {}
        migration_items = []
        split_details_by_species = {}
        auto_recs = {}
        normalized_v2025 = {}
        ebird_locs = {}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_html_path = os.path.join(temp_dir, "test_dashboard.html")
            
            # Executes the HTML generation using the actual project templates
            save_to_html(
                output_html_path,
                merged_rows,
                photos_missing_location,
                earliest_photos,
                migration_items,
                split_details_by_species,
                auto_recs,
                normalized_v2025,
                ebird_locs
            )
            
            self.assertTrue(os.path.exists(output_html_path))
            
            with open(output_html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                
            # Assertions:
            # 1. The template placeholder is NOT present raw
            self.assertNotIn("{{ MISSING_EBIRD }}", html_content)
            
            # 2. The value is replaced with "1" inside the card-val
            self.assertIn('<div class="card-title">Missing eBird</div>', html_content)
            self.assertIn('<div class="card-val">1</div>', html_content)

if __name__ == "__main__":
    unittest.main()
