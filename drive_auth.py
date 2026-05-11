#!/usr/bin/env python3
"""
Authentification Google Drive via Device Flow
Pas besoin de navigateur sur le serveur — juste un code à entrer sur google.com/device
"""
import json
import time
import requests
from pathlib import Path

TOKEN_FILE = Path("/root/kdp-automation/drive_token.json")

# Google OAuth2 client "installed app" credentials publiques (gcloud CLI)
CLIENT_ID     = "32555940559.apps.googleusercontent.com"
CLIENT_SECRET = "ZmssLNjJy2998hD4CTg2ejr2"
SCOPE         = "https://www.googleapis.com/auth/drive.file"

def get_device_code():
    r = requests.post("https://oauth2.googleapis.com/device/code", data={
        "client_id": CLIENT_ID,
        "scope": SCOPE,
    })
    r.raise_for_status()
    return r.json()

def poll_token(device_code: str, interval: int):
    while True:
        time.sleep(interval)
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "device_code": device_code,
            "grant_type": "urn:ietf:wg:oauth:2.0:device_code",
        })
        data = r.json()
        if "access_token" in data:
            return data
        if data.get("error") not in ("authorization_pending", "slow_down"):
            print(f"❌ Erreur: {data}")
            return None
        print("   ⏳ En attente de ton autorisation...", end="\r")

def main():
    print("🔐 Authentification Google Drive\n")
    resp = get_device_code()

    print("="*55)
    print(f"1. Va sur : {resp['verification_url']}")
    print(f"2. Entre ce code : {resp['user_code']}")
    print("3. Connecte-toi avec dranjea7@gmail.com")
    print("4. Clique Autoriser")
    print("="*55)
    print("\n⏳ En attente...\n")

    token_data = poll_token(resp["device_code"], resp.get("interval", 5))
    if not token_data:
        return

    TOKEN_FILE.write_text(json.dumps({
        "token":         token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "token_uri":     "https://oauth2.googleapis.com/token",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes":        [SCOPE],
    }))
    print(f"\n✅ Token sauvegardé dans {TOKEN_FILE}")
    print("Lance maintenant :")
    print(f"   python3 upload_to_drive.py <dossier_livre>")

if __name__ == "__main__":
    main()
