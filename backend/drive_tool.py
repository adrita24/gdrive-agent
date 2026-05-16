import os
import re
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON", "")


def get_drive_service():
    if SERVICE_ACCOUNT_JSON:
        info = json.loads(SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
    return build("drive", "v3", credentials=creds)


FRIENDLY_MIME = {
    "application/pdf": "PDF",
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.spreadsheet": "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.folder": "Folder",
    "image/jpeg": "Image (JPEG)",
    "image/png": "Image (PNG)",
    "text/csv": "CSV",
    "text/plain": "Text",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word Doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
    "video/mp4": "Video",
    "application/x-shellscript": "Shell Script",
}


def friendly_mime(mime: str) -> str:
    return FRIENDLY_MIME.get(mime, mime)


def format_file(f: dict) -> str:
    name = f.get("name", "Untitled")
    mime = friendly_mime(f.get("mimeType", ""))
    modified = f.get("modifiedTime", "")[:10] if f.get("modifiedTime") else "N/A"
    link = f.get("webViewLink", "")
    size_bytes = f.get("size")
    size_str = ""
    if size_bytes:
        kb = int(size_bytes) / 1024
        size_str = f" | {kb:.0f} KB" if kb < 1024 else f" | {kb/1024:.1f} MB"

    # Plain text format — no markdown, no special chars that confuse LLMs
    line = f"- {name} | {mime}{size_str} | Modified: {modified} | Link: {link}"
    return line


def sanitize_query(query: str) -> str:
    query = query.replace("\\'", "'").replace('\\"', '"')
    query = re.sub(r'"([^"]*)"', lambda m: f"'{m.group(1)}'", query)
    return query.strip()


@tool
def search_drive_files(query: str) -> str:
    """Search for files in Google Drive using a Drive API query string.

    SYNTAX:
    - name contains 'keyword'
    - name = 'exact name'
    - mimeType = 'application/pdf'
    - fullText contains 'keyword'
    - modifiedTime > '2024-01-01T00:00:00'
    - Combine with: and / or

    MIME TYPES:
    - PDF: application/pdf
    - Google Doc: application/vnd.google-apps.document
    - Google Sheet: application/vnd.google-apps.spreadsheet
    - Google Slides: application/vnd.google-apps.presentation
    - JPEG: image/jpeg
    - PNG: image/png
    """
    if not FOLDER_ID:
        return "Error: GDRIVE_FOLDER_ID not configured."
    try:
        service = get_drive_service()
        clean_query = sanitize_query(query)
        full_query = f"'{FOLDER_ID}' in parents and trashed = false and ({clean_query})"
        results = service.files().list(
            q=full_query,
            fields="files(id, name, mimeType, modifiedTime, webViewLink, size)",
            pageSize=30,
            orderBy="modifiedTime desc",
        ).execute()
        files = results.get("files", [])
        if not files:
            return "No files found matching your query."
        lines = [f"Found {len(files)} file(s):"]
        for f in files:
            lines.append(format_file(f))
        return "\n".join(lines)
    except HttpError as e:
        return f"Drive API error: {e.reason}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def list_all_files(max_results: int = 50) -> str:
    """List ALL files in the shared Google Drive folder with no filters.
    Use when the user wants to browse or see everything available.
    """
    if not FOLDER_ID:
        return "Error: GDRIVE_FOLDER_ID not configured."
    try:
        service = get_drive_service()
        results = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name, mimeType, modifiedTime, webViewLink, size)",
            pageSize=min(max_results, 100),
            orderBy="name",
        ).execute()
        files = results.get("files", [])
        if not files:
            return "The shared folder is empty."
        lines = [f"Found {len(files)} file(s):"]
        for f in files:
            lines.append(format_file(f))
        return "\n".join(lines)
    except HttpError as e:
        return f"Drive API error: {e.reason}"
    except Exception as e:
        return f"Error: {str(e)}"