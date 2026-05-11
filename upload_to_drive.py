#!/usr/bin/env python3
"""
Upload les fichiers générés vers Google Drive
Utilise les credentials stockés par Claude Code MCP
"""
import os
import sys
import json
import base64
from pathlib import Path
import requests

def upload_file_to_drive(file_path: Path, parent_id: str, mime_type: str, api_token: str) -> dict:
    """Upload un fichier via l'API Google Drive."""
    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    # Metadata
    metadata = {"name": file_path.name, "parents": [parent_id]}

    # Upload multipart
    boundary = "boundary_kdp_upload"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n"
        f"Content-Transfer-Encoding: base64\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--"
    )

    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": f"multipart/related; boundary={boundary}"
        },
        data=body.encode()
    )
    r.raise_for_status()
    return r.json()


def create_drive_folder(name: str, parent_id: str, api_token: str) -> str:
    """Crée un dossier sur Drive et retourne son ID."""
    r = requests.post(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        json={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    )
    r.raise_for_status()
    return r.json()["id"]


def main():
    book_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not book_dir or not book_dir.exists():
        print("Usage: python3 upload_to_drive.py <chemin_dossier_livre>")
        sys.exit(1)

    token = os.environ.get("GOOGLE_ACCESS_TOKEN")
    if not token:
        print("❌ GOOGLE_ACCESS_TOKEN manquant")
        print("   Récupère-le depuis : https://developers.google.com/oauthplayground")
        sys.exit(1)

    # ID du dossier parent "Livres chrétien version finale"
    PARENT_FOLDER_ID = "1mD7Ef8jBiXE-5GweJRg-Sq5p-EnpStfC"

    with open(book_dir / "content.json", encoding="utf-8") as f:
        data = json.load(f)
    book_title = data["title"]

    print(f"📤 Upload Drive : {book_title}")

    folder_id = create_drive_folder(book_title, PARENT_FOLDER_ID, token)
    print(f"   📁 Dossier créé : {folder_id}")

    files_to_upload = [
        (book_dir / "cover.jpg", "image/jpeg"),
        *[(f, "application/pdf") for f in book_dir.glob("*.pdf")],
        *[(f, "application/epub+zip") for f in book_dir.glob("*.epub")],
    ]

    for file_path, mime in files_to_upload:
        if file_path.exists():
            result = upload_file_to_drive(file_path, folder_id, mime, token)
            print(f"   ✅ {file_path.name} → {result.get('id')}")

    print(f"\n✅ Upload terminé : https://drive.google.com/drive/folders/{folder_id}")


if __name__ == "__main__":
    main()
