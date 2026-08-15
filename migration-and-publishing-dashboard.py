#!/usr/bin/env python3
"""
Bird Migration & Publishing Dashboard CLI wrapper.
Queries Lightroom, matches against eBird logs, resolves taxonomy mismatches,
and generates unified HTML and CSV reports.
"""

import os
from lib.lrcat_utils import open_catalog
from lib.dashboard_pipeline import run_migration_dashboard_pipeline

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Connecting to Lightroom Catalog...")
    with open_catalog() as cursor:
        run_migration_dashboard_pipeline(cursor, script_dir)

if __name__ == "__main__":
    main()