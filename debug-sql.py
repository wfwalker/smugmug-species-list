import sqlite3
import shutil
import os

# 1. Path Configuration
lrcat_path = "/Users/walker/Pictures/Lightroom/Lightroom Catalog-v13-5.lrcat"
temp_db = "/Users/walker/Downloads/Lightroom Catalog-copy-v13-5.lrcat"
output_html = "alphabetical_life_list.html"

# 2. Copy the DB (Prevents "Database Locked" error if LrC is open)
shutil.copy2(lrcat_path, temp_db)

# 3. Connect and Query
conn = sqlite3.connect(temp_db)
cursor = conn.cursor()

query = """
SELECT *
FROM AgLibraryKeyword k
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
GROUP BY k.name
ORDER BY k.name ASC;
"""


cursor.execute(query)
results = cursor.fetchall()
conn.close()

for aResult in results:
    print(aResult);

