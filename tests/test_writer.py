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
                "needs_tagging": 1,
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
            ex_folder = "2026/05/"
            ex_file = "D86A7391.CR3"
            full_folder_path = os.path.join(temp_dir, ex_folder)
            os.makedirs(full_folder_path, exist_ok=True)
            with open(os.path.join(full_folder_path, ex_file), "w") as f:
                f.write("mock")
                
            needs_tagging_examples = {"House Wren": [(ex_file, ex_folder, temp_dir)]}
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
                ebird_locs,
                needs_tagging_examples
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
            
            # 3. The needs-tagging example photo filename and folder are rendered
            self.assertIn("D86A7391.CR3", html_content)
            self.assertIn("2026/05/", html_content)

if __name__ == "__main__":
    unittest.main()
