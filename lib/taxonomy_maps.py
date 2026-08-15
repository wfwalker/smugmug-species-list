# 2024 -> 2025 taxonomy mapping rules based on your personal eBird taxonomy report
RENAME_MAPS = {
    "Squirrel Cuckoo": "Common Squirrel-Cuckoo",
    "Elegant Trogon": "Coppery-tailed Trogon",
    "Collared Aracari": "Pale-mandibled Aracari",
    "Gray-hooded Bush Tanager": "Pink-billed Cnemoscopus",
    "Gartered Trogon": "Gartered Violaceous Trogon",
    "Guianan Trogon": "Guianan Violaceous Trogon",
    "Northern Black-throated Trogon": "Graceful Black-throated Trogon",
    "Eurasian Hoopoe": "Common Hoopoe",
    "Cherrie's Tanager": "Scarlet-rumped Tanager",
    "Passerini's Tanager": "Scarlet-rumped Tanager",
    "Mealy Parrot": "Mealy Amazon",
    "Greenfinch": "European Greenfinch",
    "Violaeous Trogon": "Violaceous Trogon",
    "White-crested Elania": "White-crested Elaenia",
    "Safron-crowned Tanager": "Saffron-crowned Tanager",
    "Barn Swalliow": "Barn Swallow",
    "Broadbilled Hummingbird": "Broad-billed Hummingbird",
    "Ochreaceous Pewee": "Ochraceous Pewee",
    "Great Tinnamou": "Great Tinamou",
    "Slated-colored Junco": "Slate-colored Junco",
    "Common House-Martin": "Western House-Martin",
    "House Martin": "Western House-Martin",
    "Common Whitethroat": "Greater Whitethroat",
    "Sooty-capped Bush-Tanager": "Sooty-capped Chlorospingus",
    "Grey-headed Tanager": "Gray-headed Tanager",
    "Yellow-billed Tropicbird": "White-tailed Tropicbird",
    "Red-crowned Parrot": "Red-crowned Amazon",
    "Glistening Green Tanager": "Glistening-green Tanager",
    "Tāiko": "Magenta Petrel",
    "Tūī": "Tui",
    "Western Mockingbird": "Northern Mockingbird",
    "Plumbeous Sierra-finch": "Plumbeous Sierra Finch",
    "Grey-throated Leaftosser": "Gray-throated Leaftosser",
    "Greater Sage Grouse": "Greater Sage-Grouse",
    "Hoffman's Woodpecker": "Hoffmann's Woodpecker",
    "Mangrove Warbler": "Mangrove Yellow Warbler",
    "Northern Gallinule": "Common Gallinule",
    "Band-tailed Gull": "Belcher's Gull",
}

SPLIT_MAPS = {
    "Whimbrel": ["Hudsonian Whimbrel", "Eurasian Whimbrel"],
    "Southern Rockhopper Penguin": ["Eastern Rockhopper Penguin", "Western Rockhopper Penguin"],
    "Striated Heron": ["Lava Heron", "Little Heron", "Striated Heron"],
    "Warbling Vireo": ["Eastern Warbling Vireo", "Western Warbling Vireo"],
    "Yellow Warbler": ["Mangrove Yellow Warbler", "Northern Yellow Warbler"],
    "Rockhopper Penguin": ["Western Rockhopper Penguin", "Eastern Rockhopper Penguin", "Moseley's Rockhopper Penguin"],
    "Immaculate Antbird": ["Zeledon's Antbird", "Blue-lored Antbird"],
    "Common Moorhen": ["Common Gallinule", "Eurasian Moorhen"],
}

LUMP_MAPS = {
    "Antarctic Shag": "Imperial Cormorant",
    "Macquarie Shag": "Imperial Cormorant",
    "South Georgia Shag": "Imperial Cormorant",
}

# Case-insensitive maps for lookup safety
RENAME_MAPS_LOWER = {k.lower(): (k, v) for k, v in RENAME_MAPS.items()}
SPLIT_MAPS_LOWER = {k.lower(): (k, v) for k, v in SPLIT_MAPS.items()}
LUMP_MAPS_LOWER = {k.lower(): (k, v) for k, v in LUMP_MAPS.items()}
