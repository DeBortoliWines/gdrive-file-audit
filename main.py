#!/usr/bin/env python3

import time
import logging
import argparse
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

location_url = lambda parent_id: f"https://drive.google.com/drive/folders/{parent_id}"


def main(credentials_file, drive, sheet, list_folders, list_trashed):
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=scopes
    )
    drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    sheets_service = build(
        "sheets", "v4", credentials=credentials, cache_discovery=False
    )

    # Define kwargs (key word arguments) for file search
    # Written this way to aviod defining parameters for file search twice due to pagination
    kwargs = {
        "corpora": "drive",
        "driveId": drive,
        "fields": "files(id, mimeType, name, createdTime, modifiedTime, lastModifyingUser(displayName), trashedTime, webViewLink, parents), nextPageToken",
        "includeItemsFromAllDrives": True,
        "pageSize": 1000,
        "supportsAllDrives": True,
        "q": "trashed = false",
    }

    if list_trashed:
        del kwargs["q"]

    # Recursively find all files in drive
    files = []
    while True:
        try:
            results = drive_service.files().list(**kwargs).execute()
        except HttpError as e:
            logging.error(e)
            raise

        files.extend(results["files"])

        # If no next page, break out of loop
        if "nextPageToken" not in results:
            break

        # Add next page token to kwargs
        kwargs["pageToken"] = results["nextPageToken"]

    logging.info(f"Found {len(files)} total files")

    for file in files:
        file["path"] = build_file_path(files, file["parents"][0])
        file["location"] = location_url(file["parents"][0])
        if file["path"] == "":
            file["path"] = "/"

        if "lastModifyingUser" in file:
            file["lastModifyingUser"] = file.pop("lastModifyingUser")["displayName"]

    body = build_sheet_body(files, list_folders)
    output_to_sheet(sheets_service, sheet, body)


def build_file_path(files, parent_id, path="", file_dict=None):
    if file_dict is None:
        # Create a dictionary to store the files by their IDs
        file_dict = {file["id"]: file for file in files}

    parent_folder = file_dict.get(parent_id)
    if parent_folder is None:
        return path

    path = f"{parent_folder['name']}/{path}"

    return build_file_path(files, parent_folder["parents"][0], path, file_dict)


def build_sheet_body(files, list_folders):
    # Use pandas to build values for sheet (instead of manually formatting)
    df = pd.DataFrame(files)

    # Build hyperlinks for name and path
    df["name"] = '=HYPERLINK("' + df["webViewLink"] + '", "' + df["name"] + '")'
    df["path"] = '=HYPERLINK("' + df["location"] + '", "' + df["path"] + '")'

    if not list_folders:
        df = df[df["mimeType"].str.contains("folder") == False]

    col_order = ["name", "createdTime", "modifiedTime", "lastModifyingUser", "path"]
    time_cols = ["createdTime", "modifiedTime"]

    if "trashedTime" in df:
        col_order.append("trashedTime")
        time_cols.append("trashedTime")

    for time_col in time_cols:
        df[time_col] = pd.to_datetime(df[time_col]).dt.strftime("%Y-%m-%d %H:%M:%S")

    df = df[col_order]
    df = df.fillna("")

    values = [df.keys().tolist()]
    values.extend(df.values.tolist())

    # Write new data to sheet
    body = {"values": values}

    return body


def output_to_sheet(sheets_service, sheet, body):
    try:
        sheets_service.spreadsheets().values().clear(
            spreadsheetId=sheet, range="A:ZZ"
        ).execute()
        logging.info(f"Cleared sheet {sheet}")
    except HttpError as e:
        logging.error(e)
        raise

    try:
        result = (
            sheets_service.spreadsheets()
            .values()
            .update(
                spreadsheetId=sheet,
                valueInputOption="USER_ENTERED",
                range="A:ZZ",
                body=body,
            )
            .execute()
        )
        logging.info(f"Written {result.get('updatedCells')} cells to sheet {sheet}")
    except HttpError as e:
        logging.error(e)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Google Shared Drive file audit", add_help=True
    )
    parser.add_argument("credentials", help="Service Account Credentials JSON File")
    parser.add_argument("drive", help="Google Shared Drive ID")
    parser.add_argument("sheet", help="Output Google Sheet ID")
    parser.add_argument(
        "-v",
        "--verbose",
        help="Enable more verbose logging",
        action="store_const",
        dest="logLevel",
        const=logging.INFO,
        default=logging.WARN,
    )
    parser.add_argument(
        "-l",
        "--logfile",
        help="Specify log file location",
        dest="logFile",
        default="/var/log/file_audit.log",
    )
    parser.add_argument(
        "-f",
        "--folders",
        help="List folders as well as files",
        dest="listFolders",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-t",
        "--trashed",
        help="List trashed items",
        dest="listTrashed",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    logging.basicConfig(
        filename=args.logFile,
        format="%(asctime)s %(levelname)-4s %(message)s",
        datefmt="%b %d %H:%M:%S",
        level=args.logLevel,
    )

    logging.info(f"Starting file audit on drive {args.drive}")
    start = time.time()
    main(args.credentials, args.drive, args.sheet, args.listFolders, args.listTrashed)
    end = time.time()
    logging.info(
        f"File audit complete on drive {args.drive} in {round(end - start, 2)} seconds"
    )
