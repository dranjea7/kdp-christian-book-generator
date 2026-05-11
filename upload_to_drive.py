#!/usr/bin/env python3
"""
Upload les fichiers générés vers Google Drive
Nécessite d'avoir lancé drive_auth.py une fois au préalable
Usage: python3 upload_to_drive.py <chemin_dossier_livre>
"""
import sys
import json
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_FILE = Path("/root/kdp-automation/drive_token.json")
PARENT_FOLDER_ID = "1mD7Ef8jBiXE-5GweJRg-Sq5p-EnpStfC"  # "Livres chrétien version finale"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

MIME_TYPES = {
    ".pdf":  "application/pdf",
    ".epub": "application/epub+zip",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".json": "application/json",
}

def get_service():
    import os
    refresh_token = os.environ.get("GDRIVE_REFRESH_TOKEN")

    # Si refresh token fourni directement via variable d'environnement
    if refresh_token:
        from google.oauth2.credentials import Credentials
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id="764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
            client_secret="d-FL95Q19q7MQmFpd7hHD0Ty",
            scopes=SCOPES
        )
        creds.refresh(Request())
        # Sauvegarder pour la prochaine fois
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        return build("drive", "v3", credentials=creds)

    # Sinon utiliser le token sauvegardé
    if not TOKEN_FILE.exists():
        print("❌ Token manquant.")
        print("   Option 1 : export GDRIVE_REFRESH_TOKEN='1//...' puis relancer")
        print("   Option 2 : python3 drive_auth.py")
        sys.exit(1)
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def create_folder(service, name: str, parent_id: str) -> str:
    result = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        supportsAllDrives=True,
        fields="id"
    ).execute()
    return result["id"]


def upload_file(service, file_path: Path, parent_id: str) -> str:
    mime = MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)
    result = service.files().create(
        body={"name": file_path.name, "parents": [parent_id]},
        media_body=media,
        supportsAllDrives=True,
        fields="id,name,webViewLink"
    ).execute()
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 upload_to_drive.py <chemin_dossier_livre>")
        sys.exit(1)

    book_dir = Path(sys.argv[1])
    if not book_dir.exists():
        print(f"❌ Dossier introuvable : {book_dir}")
        sys.exit(1)

    with open(book_dir / "content.json", encoding="utf-8") as f:
        data = json.load(f)
    book_title = data["title"]

    print(f"📤 Upload Drive : {book_title}")
    service = get_service()

    # Créer le dossier du livre
    folder_id = create_folder(service, book_title, PARENT_FOLDER_ID)
    print(f"   📁 Dossier créé sur Drive")

    # Uploader les fichiers
    files_to_upload = [
        book_dir / "cover.jpg",
        *book_dir.glob("*.pdf"),
        *book_dir.glob("*.epub"),
    ]

    for file_path in files_to_upload:
        if file_path.exists():
            print(f"   ⬆️  {file_path.name}...", end=" ", flush=True)
            result = upload_file(service, file_path, folder_id)
            print(f"✅")

    drive_url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"\n✅ Upload terminé !")
    print(f"   📁 {drive_url}")


if __name__ == "__main__":
    main()
