#!/usr/bin/python3

import sys
import os
from datetime import datetime, timedelta
import json
import urllib.parse
import urllib.request

# Import from our central Lightroom utilities
from lrcat_utils import open_catalog
from publish_lifelist import load_credentials, make_signed_request

# --- SMUGMUG ALBUM DISCOVERY ---

def get_root_node_id(credentials):
    """Fetches the authenticated user's root Node ID."""
    print("Fetching authenticated user profile...")
    auth_data = make_signed_request("GET", "https://api.smugmug.com/api/v2!authuser", credentials=credentials)
    user_node_uri = auth_data.get("Response", {}).get("User", {}).get("Uris", {}).get("Node", {}).get("Uri")
    if not user_node_uri:
        print("❌ Error: Could not retrieve root node URI from user profile.")
        sys.exit(1)
    return user_node_uri.split("/")[-1]

def search_nodes_for_album(parent_node_id, album_name, credentials, depth=1, max_depth=2):
    """Recursively searches for an album with the given name under a parent node."""
    url = f"https://api.smugmug.com/api/v2/node/{parent_node_id}!children"
    params = {"count": "100"}
    try:
        data = make_signed_request("GET", url, params=params, credentials=credentials)
    except Exception as e:
        print(f"⚠️ Warning: Could not search children of node {parent_node_id}: {e}")
        return None
        
    children = data.get("Response", {}).get("Node", [])
    
    # 1. Search for matching Album at current level
    for child in children:
        if child.get("Type") == "Album" and child.get("Name", "").strip().lower() == album_name.lower():
            album_uri = child.get("Uris", {}).get("Album", {}).get("Uri")
            node_id = child.get("NodeID")
            return {"Name": child.get("Name"), "NodeID": node_id, "AlbumUri": album_uri}
            
    # 2. Recursively search folders
    if depth < max_depth:
        for child in children:
            if child.get("Type") == "Folder":
                folder_node_id = child.get("NodeID")
                print(f"   Searching inside folder: {child.get('Name')}...")
                result = search_nodes_for_album(folder_node_id, album_name, credentials, depth + 1, max_depth)
                if result:
                    return result
                    
    return None

# --- ON THIS DATE ENGINE ---

def get_photos_on_this_date():
    """Queries Lightroom database copy for published photos taken within +/- 5 days of today's date across all years."""
    today = datetime.now()
    
    # Generate list of 11 target date strings (MM-DD) centered around today
    target_dates = []
    for offset in range(-5, 6):
        date_offset = today + timedelta(days=offset)
        target_dates.append(date_offset.strftime("%m-%d"))
        
    print(f"🔍 Querying Lightroom copy for photos taken between {target_dates[0]} and {target_dates[-1]} (inclusive)...")
    
    # Build query with IN clause for the dates
    placeholders = ",".join(["?"] * len(target_dates))
    query = f"""
        SELECT rp.remoteId, i.captureTime
        FROM Adobe_images i
        JOIN AgRemotePhoto rp ON i.id_local = rp.photo
        WHERE rp.remoteId LIKE '/image/%'
          AND strftime('%m-%d', i.captureTime) IN ({placeholders})
        ORDER BY i.captureTime DESC;
    """
    
    with open_catalog() as cursor:
        cursor.execute(query, target_dates)
        rows = cursor.fetchall()
        
    # Reconstruct Image URIs
    image_uris = []
    for r in rows:
        remote_id = r[0] # e.g. /image/t7nSTwx
        image_uris.append(f"/api/v2{remote_id}")
        
    print(f"✅ Found {len(image_uris)} published photos taken within +/- 5 days of today.")
    return image_uris

def clear_album_images(album_uri, credentials):
    """Fetches all existing images in the album and deletes them."""
    images_url = f"https://api.smugmug.com{album_uri}!images"
    params = {"count": "100"}
    
    print("Fetching current album photos...")
    data = make_signed_request("GET", images_url, params=params, credentials=credentials)
    album_images = data.get("Response", {}).get("AlbumImage", [])
    
    if not album_images:
        print("   Album is already empty.")
        return True
        
    # Extract AlbumImage Uris (these represent the references in this specific album)
    delete_uris = [img.get("Uri") for img in album_images]
    delete_list = ",".join(delete_uris)
    
    print(f"Removing {len(delete_uris)} existing photos from album...")
    delete_url = f"https://api.smugmug.com{album_uri}!deleteimages"
    patch_body = {
        "DeleteUris": delete_list,
        "Async": False
    }
    make_signed_request("POST", delete_url, body=patch_body, credentials=credentials)
    print("   Album cleared successfully.")
    return True

def collect_images_to_album(album_uri, image_uris, credentials):
    """Collects existing image URIs into the album."""
    if not image_uris:
        print("No new photos to collect today.")
        return True
        
    # Comma-separated list of raw Image URIs (e.g. /api/v2/image/xxxx)
    collect_list = ",".join(image_uris)
    
    print(f"Collecting {len(image_uris)} photos into the album...")
    collect_url = f"https://api.smugmug.com{album_uri}!collectimages"
    patch_body = {
        "CollectUris": collect_list,
        "Async": False
    }
    make_signed_request("POST", collect_url, body=patch_body, credentials=credentials)
    print("🎉 Album populated successfully!")
    return True

# --- MAIN CONTROLLER ---

def main():
    print("=" * 80)
    print("SMUGMUG 'ON THIS DATE' DAILY UPDATE AUTOMATION")
    print("=" * 80)
    
    credentials = load_credentials()
    
    # 1. Get local Lightroom photos taken on MM-DD
    try:
        image_uris = get_photos_on_this_date()
    except Exception as e:
        print(f"❌ Database error reading Lightroom: {e}")
        sys.exit(1)
        
    # 2. Find target album "On This Date" on SmugMug
    root_node_id = get_root_node_id(credentials)
    print("Searching for 'On This Date' Album on your SmugMug account...")
    album_info = search_nodes_for_album(root_node_id, "On This Date", credentials)
    
    if not album_info:
        print("\n❌ Error: Could not find an Album named 'On This Date' on your account.")
        print("   Please create a new Album named 'On This Date' in your SmugMug organizer.")
        sys.exit(1)
        
    print(f"✅ Found Album: '{album_info['Name']}'")
    print(f"   Node ID: {album_info['NodeID']}")
    print(f"   Album URI: {album_info['AlbumUri']}")
    
    album_uri = album_info["AlbumUri"]
    
    # 3. Clear existing photos
    try:
        clear_album_images(album_uri, credentials)
    except Exception as e:
        print(f"❌ Error clearing existing photos: {e}")
        sys.exit(1)
        
    # 4. Collect new photos
    try:
        collect_images_to_album(album_uri, image_uris, credentials)
    except Exception as e:
        print(f"❌ Error collecting photos: {e}")
        sys.exit(1)
        
    print("\nDaily update completed successfully!")

if __name__ == "__main__":
    main()
