import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.alphabetical import generate_html_content as gen_alpha
from generators.taxonomic import generate_html_content as gen_tax
from generators.chronological import generate_html_content as gen_chrono
from generators.growth_chart import process_timeline, build_html as gen_growth_html, build_svg as gen_growth_svg

class TestGenerators(unittest.TestCase):
    def setUp(self):
        # Determine root directory containing templates
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_alphabetical_generator(self):
        results = [
            ("American Robin", 2, "https://billwalker.smugmug.com/robin"),
            ("House Wren", 1, "https://billwalker.smugmug.com/wren")
        ]
        html = gen_alpha(results, root_dir=self.root_dir)
        self.assertIn("Bill's Photo Life List", html)
        self.assertIn("American Robin", html)
        self.assertIn("House Wren", html)
        # 1 photo of House Wren should have direct relative link
        self.assertIn("/wren", html)
        # 2 photos of American Robin should have search link
        self.assertIn("/search/?q=American+Robin", html)

    def test_taxonomic_generator(self):
        results = [
            ("Turdidae", "American Robin", 1, "https://billwalker.smugmug.com/robin"),
            ("Troglodytidae", "House Wren", 2, "https://billwalker.smugmug.com/wren")
        ]
        html = gen_tax(results, [], root_dir=self.root_dir)
        self.assertIn("Bill's Taxonomic Photo Life List", html)
        self.assertIn("Turdidae", html)
        self.assertIn("Troglodytidae", html)
        self.assertIn("American Robin", html)
        self.assertIn("/robin", html)
        self.assertIn("/search/?q=House+Wren", html)

    def test_chronological_generator(self):
        chrono_data = {
            "2026": [
                {
                    "name": "House Wren",
                    "ebird_date": "2026-05-12",
                    "ebird_location": "My Yard",
                    "photo": {
                        "name": "House Wren",
                        "date": "2026-05-12",
                        "location": "My Yard",
                        "url": "https://billwalker.smugmug.com/wren",
                        "photo_count": 1
                    }
                }
            ]
        }
        html = gen_chrono(chrono_data, 1, root_dir=self.root_dir)
        self.assertIn("Bill's Chronological Photo Life List", html)
        self.assertIn("2026", html)
        self.assertIn("House Wren", html)
        self.assertIn("/wren", html)

    def test_growth_chart_generator(self):
        species_list = [
            {
                "name": "House Wren",
                "date": "2026-05-12",
                "location": "My Yard",
                "url": "https://billwalker.smugmug.com/wren",
                "photo_count": 1
            }
        ]
        summary, timeline = process_timeline(species_list)
        self.assertEqual(summary["total_species"], 1)
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["month"], "2026-05")
        
        html = gen_growth_html(summary, timeline)
        self.assertIn("Photographic Species Life List Growth", html)
        self.assertIn("House Wren", html)
        
        svg = gen_growth_svg(summary, timeline)
        self.assertIn("Photographic Species Life List Growth", svg)
        self.assertIn("Total: 1 Species", svg)
