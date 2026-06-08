import sqlite3
import shutil
import os
import urllib.request
import json


# query smugmug API to find which bird family galleries we have right now

smugmug_api_key = os.getenv("SMUGMUG_API_KEY")

smugmug_galleries_query = f"""https://api.smugmug.com/api/v2/pagedesign/23635258/published?APIKey={smugmug_api_key}"""

smugmug_req = urllib.request.Request(smugmug_galleries_query)
smugmug_req.add_header('Accept', 'application/json')

with urllib.request.urlopen(smugmug_req) as response:
    # Read response body and parse JSON string
    data = json.loads(response.read().decode())

print(data);

