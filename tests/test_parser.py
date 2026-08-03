import unittest
import os
import tempfile
import json
import csv
from dashboard_parser import (
    load_json_species,
    load_valid_taxonomy_names,
    load_ebird_locations,
    parse_ebird_sightings,
    load_ebird_sightings_by_date
)

class TestParser(unittest.TestCase):
    def test_load_json_species(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([
                {"Common Name": "Andean Gull"},
                {"Common Name": "Antarctic Fur Seal"},
                {"something_else": "ignored"}
            ], f)
            temp_path = f.name
            
        try:
            res = load_json_species(temp_path)
            self.assertEqual(res, {"Andean Gull", "Antarctic Fur Seal"})
        finally:
            os.remove(temp_path)

    def test_load_valid_taxonomy_names(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["PRIMARY_COM_NAME"])
            writer.writeheader()
            writer.writerow({"PRIMARY_COM_NAME": "House Wren"})
            writer.writerow({"PRIMARY_COM_NAME": "Gray-headed Albatross"})
            temp_path = f.name
            
        try:
            res = load_valid_taxonomy_names(temp_path)
            self.assertEqual(res, {"House Wren", "Gray-headed Albatross"})
        finally:
            os.remove(temp_path)

    def test_load_ebird_locations(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["Common Name", "Date", "Location"])
            writer.writeheader()
            writer.writerow({"Common Name": "Yellow Warbler", "Date": "2026-05-12", "Location": "Dry Tortugas"})
            writer.writerow({"Common Name": "Yellow Warbler", "Date": "2026-05-12", "Location": "Fort De Soto"})
            temp_path = f.name
            
        try:
            res = load_ebird_locations(temp_path)
            self.assertEqual(res, {("yellow warbler", "2026-05-12"): {"Dry Tortugas", "Fort De Soto"}})
        finally:
            os.remove(temp_path)

    def test_parse_ebird_sightings(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["Common Name", "Date", "Location"])
            writer.writeheader()
            writer.writerow({"Common Name": "Yellow Warbler", "Date": "2026-05-12", "Location": "Dry Tortugas"})
            temp_path = f.name
            
        try:
            res = parse_ebird_sightings(temp_path)
            self.assertEqual(res, {"Yellow Warbler"})
        finally:
            os.remove(temp_path)

    def test_load_ebird_sightings_by_date(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["Common Name", "Date", "Location"])
            writer.writeheader()
            writer.writerow({"Common Name": "Yellow Warbler", "Date": "2026-05-12", "Location": "Dry Tortugas"})
            temp_path = f.name
            
        try:
            res = load_ebird_sightings_by_date(temp_path)
            self.assertEqual(res, {"2026-05-12": {"Yellow Warbler"}})
        finally:
            os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
