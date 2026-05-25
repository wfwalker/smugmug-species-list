
# The "Missing from SmugMug" Species Query

SELECT 
    k.name AS SpeciesName,
    COUNT(DISTINCT i.id_local) AS TotalPhotosInLibrary
FROM AgLibraryKeyword k
-- INNER JOIN ensures the keyword is actually attached to at least one image
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
-- LEFT JOIN to look for SmugMug records
LEFT JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
LEFT JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
LEFT JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
    AND parent_coll.name LIKE '%SmugMug%'
-- Filter for your Bird Taxonomy
WHERE k.genealogy LIKE "/41240/825689457%"
GROUP BY k.name
-- The Magic Filter: Only show species where NO photos have a SmugMug parent link
HAVING SUM(CASE WHEN parent_coll.name LIKE '%SmugMug%' THEN 1 ELSE 0 END) = 0
ORDER BY k.name ASC;

# A Useful "Check" Query

# If you want to see a list of all species and a count of how many are published vs. total, you can use this slightly modified version:

SELECT 
    k.name AS SpeciesName,
    COUNT(DISTINCT i.id_local) AS TotalInLibrary,
    SUM(CASE WHEN parent_coll.name LIKE '%SmugMug%' THEN 1 ELSE 0 END) AS PublishedToSmugMug
FROM AgLibraryKeyword k
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
LEFT JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
LEFT JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
LEFT JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
    AND parent_coll.name LIKE '%SmugMug%'
WHERE k.genealogy LIKE "/41240/825689457%"
GROUP BY k.name
ORDER BY TotalInLibrary DESC;

# The "Unpublished Species" Checklist Query

SELECT 
    k.name AS SpeciesName,
    COUNT(DISTINCT i.id_local) AS TotalUnpublished,
    -- Construct the folder path (Windows/Mac style depends on your OS)
    fold.pathFromRoot AS FolderPath,
    -- Get the filename of the most recent photo to help you search
    MAX(f.baseName || '.' || f.extension) AS ExampleFile
FROM AgLibraryKeyword k
-- Inner Join: Must have a photo
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
JOIN AgLibraryFile f ON i.rootFile = f.id_local
JOIN AgLibraryFolder fold ON f.folder = fold.id_local
-- Left Join: Look for SmugMug links
LEFT JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
LEFT JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
LEFT JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
    AND parent_coll.name LIKE '%SmugMug%'
WHERE k.genealogy LIKE "/41240/825689457%"
GROUP BY k.name
-- Only keep species where NOT A SINGLE photo is on SmugMug
HAVING SUM(CASE WHEN parent_coll.name LIKE '%SmugMug%' THEN 1 ELSE 0 END) = 0
ORDER BY TotalUnpublished DESC;

# One Final CSV Tip

# If you are running this from the SQLite Command Line Interface (CLI), you can turn this directly into a .csv file by running these commands before you paste the query:

# .headers on
# .mode csv
# .output unpublished_birds.csv
# -- [Paste the SQL Query here]
# .output stdout

# The "Label-to-SmugMug" Gap Query

# This query will list all unique bird species found in your colorLabels column that do not have a single photo published to SmugMug.

SELECT 
    i.colorLabels AS SpeciesFromLabel,
    COUNT(DISTINCT i.id_local) AS TotalInLibrary,
    -- Get an example folder path so you can find them in LrC
    fold.pathFromRoot AS ExampleFolder
FROM Adobe_images i
JOIN AgLibraryFile f ON i.rootFile = f.id_local
JOIN AgLibraryFolder fold ON f.folder = fold.id_local
-- Left Join to check for SmugMug publishing
LEFT JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
LEFT JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
LEFT JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local 
    AND parent_coll.name LIKE '%SmugMug%'
-- Filter for non-empty labels and exclude standard color names
WHERE i.colorLabels != '' 
  AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
GROUP BY i.colorLabels
-- This ensures that for the entire group (species), no SmugMug record exists
HAVING SUM(CASE WHEN parent_coll.name LIKE '%SmugMug%' THEN 1 ELSE 0 END) = 0
ORDER BY TotalInLibrary DESC;


# This query will act as a "Migration and Status Dashboard." It compares your old system (Labels) against your new system (Taxonomy Keywords) and your final output (SmugMug).

# To do this, we'll join the colorLabels to the AgLibraryKeyword table by matching the text strings.

# The Migration & Publishing Dashboard


SELECT 
    i.colorLabels AS SpeciesName,
    COUNT(DISTINCT i.id_local) AS Total_With_This_Label,
    -- Count how many of these have the official taxonomy keyword
    COUNT(DISTINCT ki.image) AS Total_With_Keyword,
    -- Count how many of these are on SmugMug
    COUNT(DISTINCT pci.image) AS Total_On_SmugMug,
    -- Calculate how many are left to "Fix" (Label exists but Keyword doesn't)
    (COUNT(DISTINCT i.id_local) - COUNT(DISTINCT ki.image)) AS Needs_Tagging
FROM Adobe_images i
-- 1. Check for matching Keywords (Taxonomy)
LEFT JOIN AgLibraryKeyword k 
    ON i.colorLabels = k.name 
    AND k.genealogy LIKE "/41240/825689457%"
LEFT JOIN AgLibraryKeywordImage ki 
    ON i.id_local = ki.image AND k.id_local = ki.tag
-- 2. Check for SmugMug publishing
LEFT JOIN AgLibraryPublishedCollectionImage pci 
    ON i.id_local = pci.image
LEFT JOIN AgLibraryPublishedCollection child_coll 
    ON pci.collection = child_coll.id_local
LEFT JOIN AgLibraryPublishedCollection parent_coll 
    ON child_coll.parent = parent_coll.id_local 
    AND parent_coll.name LIKE '%SmugMug%'
WHERE i.colorLabels != '' 
  AND i.colorLabels NOT IN ('Red', 'Yellow', 'Green', 'Blue', 'Purple')
GROUP BY i.colorLabels
ORDER BY Needs_Tagging DESC, Total_With_This_Label DESC;

# The Corrected HTML Generator Query

SELECT 
    '<li><a href="https://billwalker.smugmug.com/search/?q=' || 
    REPLACE(k.name, ' ', '+') || '">' || k.name || ' (' || COUNT(DISTINCT i.id_local) || ')</a></li>' AS HtmlListItem
FROM AgLibraryKeyword k
-- Link Keywords to Images
JOIN AgLibraryKeywordImage ki ON k.id_local = ki.tag
JOIN Adobe_images i ON ki.image = i.id_local
-- Link to SmugMug Publishing tables
JOIN AgLibraryPublishedCollectionImage pci ON i.id_local = pci.image
JOIN AgLibraryPublishedCollection child_coll ON pci.collection = child_coll.id_local
JOIN AgLibraryPublishedCollection parent_coll ON child_coll.parent = parent_coll.id_local
WHERE k.genealogy LIKE "/41240/825689457%"
  AND parent_coll.name LIKE '%SmugMug%'
GROUP BY k.name
ORDER BY k.name ASC;

# The "Mismatched Names" Discovery Query

SELECT 
    i.colorLabels AS LegacyLabel,
    k.name AS CurrentKeyword,
    COUNT(i.id_local) AS AffectedPhotos
FROM Adobe_images i
-- Join to the keyword link table
JOIN AgLibraryKeywordImage ki ON i.id_local = ki.image
-- Join to the actual keyword
JOIN AgLibraryKeyword k ON ki.tag = k.id_local
-- Filter for your Bird Taxonomy
WHERE k.genealogy LIKE "/41240/825689457%"
  -- Find the mismatches (ignoring empty labels)
  AND i.colorLabels != ''
  AND i.colorLabels != k.name
GROUP BY i.colorLabels, k.name
ORDER BY AffectedPhotos DESC;


