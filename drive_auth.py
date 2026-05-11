#!/usr/bin/env python3
"""
Étape 1 : Lancer ce script pour obtenir le lien d'autorisation Google Drive
Étape 2 : Visiter le lien, autoriser, copier le code
Étape 3 : Coller le code ici → le token est sauvegardé pour tous les uploads futurs
"""
import os
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_FILE = Path("/root/kdp-automation/drive_token.json")
CREDENTIALS_FILE = Path("/root/kdp-automation/drive_credentials.json")

# Client OAuth2 public (credentials partagées pour apps installées)
# Ces credentials sont "public" et standard pour les apps desktop Google
CLIENT_CONFIG = {
    "installed": {
        "client_id": "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
        "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
    }
}

def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Sauvegarder les credentials client
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump(CLIENT_CONFIG, f)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            # Mode console (pas de navigateur local)
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            auth_url, _ = flow.authorization_url(prompt="consent")
            print("\n" + "="*60)
            print("ÉTAPE 1 : Ouvre ce lien dans ton navigateur :")
            print("="*60)
            print(f"\n{auth_url}\n")
            print("="*60)
            code = input("ÉTAPE 2 : Colle le code ici → ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("✅ Token sauvegardé !")
    return creds

if __name__ == "__main__":
    get_credentials()
    print("✅ Authentification Google Drive réussie ! Lance maintenant :")
    print("   python3 upload_to_drive.py <dossier_livre>")
