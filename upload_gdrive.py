#!/usr/bin/env python3
"""Upload a file to a Google Drive folder. Prints the webViewLink on success.

Auth priority:
  1. Service account:  GOOGLE_SERVICE_ACCOUNT_KEY_FILE env var → path to JSON key
  2. OAuth token file: GOOGLE_OAUTH_TOKEN_FILE env var → path to saved token JSON
                       (pair with GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET for refresh)

Usage:
  python upload_gdrive.py <local_file> <drive_folder_name>
"""

import json
import mimetypes
import os
import sys

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _auth_service_account(key_file: str):
    from google.oauth2 import service_account
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
    return build("drive", "v3", credentials=creds)


def _auth_oauth(token_file: str):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    with open(token_file) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID", token_data.get("client_id", "")),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", token_data.get("client_secret", "")),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data.update({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
        })
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=2)

    return build("drive", "v3", credentials=creds)


def get_drive_service():
    sa_key = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_FILE")
    if sa_key:
        return _auth_service_account(sa_key)

    token_file = os.environ.get("GOOGLE_OAUTH_TOKEN_FILE")
    if token_file and os.path.exists(token_file):
        return _auth_oauth(token_file)

    raise RuntimeError(
        "No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_KEY_FILE "
        "or GOOGLE_OAUTH_TOKEN_FILE."
    )


def find_or_create_folder(service, name: str) -> str:
    resp = service.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
        pageSize=1,
    ).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    folder = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    return folder["id"]


def upload_file(service, local_path: str, folder_id: str) -> str:
    filename = os.path.basename(local_path)
    mime_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    file_meta = {"name": filename, "parents": [folder_id]}

    result = service.files().create(
        body=file_meta,
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    return result.get("webViewLink", f"https://drive.google.com/file/d/{result['id']}/view")


def main():
    if len(sys.argv) != 3:
        print("Usage: upload_gdrive.py <local_file> <drive_folder_name>", file=sys.stderr)
        sys.exit(1)

    local_file, folder_name = sys.argv[1], sys.argv[2]

    if not os.path.isfile(local_file):
        print(f"File not found: {local_file}", file=sys.stderr)
        sys.exit(1)

    service = get_drive_service()
    folder_id = find_or_create_folder(service, folder_name)
    link = upload_file(service, local_file, folder_id)
    print(link)


if __name__ == "__main__":
    main()
