#!/usr/bin/python3

import urllib.parse
import urllib.request
import sys
import os
from publish_lifelist import oauth_sign_request

REQUEST_TOKEN_URL = "https://api.smugmug.com/services/oauth/1.0a/getRequestToken"
AUTHORIZE_URL = "https://api.smugmug.com/services/oauth/1.0a/authorize"
ACCESS_TOKEN_URL = "https://api.smugmug.com/services/oauth/1.0a/getAccessToken"

def make_oauth_request(url, method, consumer_key, consumer_secret, token=None, token_secret=None, params=None):
    if params is None:
        params = {}
    if token is None:
        token = ""
    if token_secret is None:
        token_secret = ""
        
    auth_header = oauth_sign_request(method, url, params, consumer_key, consumer_secret, token, token_secret)
    
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json"
    }
    
    if params:
        url_parts = urllib.parse.urlparse(url)
        q_params = list(urllib.parse.parse_qsl(url_parts.query))
        for k, v in params.items():
            q_params.append((k, v))
        url = urllib.parse.urlunparse((
            url_parts.scheme,
            url_parts.netloc,
            url_parts.path,
            url_parts.params,
            urllib.parse.urlencode(q_params),
            url_parts.fragment
        ))
        
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode()
    except urllib.error.HTTPError as e:
        print(f"❌ Error request failed: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)

def main():
    print("=" * 80)
    print("SMUGMUG OAUTH 1.0A TOKEN GENERATOR")
    print("=" * 80)
    print("This script will help you authorize write access and generate Access Tokens.")
    print("First, get your API Key and Secret from: https://api.smugmug.com/api/developer/apply")
    print("-" * 80)
    
    consumer_key = input("Enter your SMUGMUG_API_KEY (Consumer Key): ").strip()
    consumer_secret = input("Enter your SMUGMUG_API_SECRET (Consumer Secret): ").strip()
    
    if not consumer_key or not consumer_secret:
        print("❌ Error: Both API Key and Secret are required.")
        sys.exit(1)
        
    print("\n1. Requesting temporary OAuth Request Token...")
    # 'oauth_callback="oob"' enables Out-Of-Band authentication, generating an on-screen PIN code
    resp_text = make_oauth_request(REQUEST_TOKEN_URL, "GET", consumer_key, consumer_secret, params={"oauth_callback": "oob"})
    
    resp_params = dict(urllib.parse.parse_qsl(resp_text))
    req_token = resp_params.get("oauth_token")
    req_secret = resp_params.get("oauth_token_secret")
    
    if not req_token or not req_secret:
        print("❌ Error: Failed to obtain Request Token from SmugMug.")
        sys.exit(1)
        
    # Generate authorization URL with write permissions
    auth_query = urllib.parse.urlencode({
        "oauth_token": req_token,
        "Access": "Full",
        "Permissions": "Write"
    })
    auth_url = f"{AUTHORIZE_URL}?{auth_query}"
    
    print("\n2. Authorize the App:")
    print("Open the following URL in your web browser, log in, and click 'Authorize':")
    print("-" * 80)
    print(auth_url)
    print("-" * 80)
    
    verifier = input("\nAfter authorizing, copy the 5-6 digit PIN code and paste it here: ").strip()
    if not verifier:
        print("❌ Error: PIN verifier is required.")
        sys.exit(1)
        
    print("\n3. Exchanging temporary token for permanent Access Tokens...")
    access_text = make_oauth_request(
        ACCESS_TOKEN_URL, 
        "GET", 
        consumer_key, 
        consumer_secret, 
        token=req_token, 
        token_secret=req_secret, 
        params={"oauth_verifier": verifier}
    )
    
    access_params = dict(urllib.parse.parse_qsl(access_text))
    access_token = access_params.get("oauth_token")
    access_token_secret = access_params.get("oauth_token_secret")
    
    if not access_token or not access_token_secret:
        print("❌ Error: Failed to exchange Access Token.")
        sys.exit(1)
        
    print("\n" + "=" * 80)
    print("🎉 SUCCESS! Copy and paste the following lines directly into your '.env' file:")
    print("=" * 80)
    print(f"SMUGMUG_API_KEY={consumer_key}")
    print(f"SMUGMUG_API_SECRET={consumer_secret}")
    print(f"SMUGMUG_ACCESS_TOKEN={access_token}")
    print(f"SMUGMUG_ACCESS_TOKEN_SECRET={access_token_secret}")
    print("=" * 80)

if __name__ == "__main__":
    main()
