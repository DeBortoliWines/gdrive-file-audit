#!/usr/bin/env python3

import time
import logging
import argparse
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

location_url = lambda parent_id: f"https://drive.google.com/drive/folders/{parent_id}"


def main(credentials_file, drive, sheet):
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=scopes
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    # Define kwargs (key word arguments) for file search
    # Written this way to aviod defining parameters for file search twice due to pagination
    kwargs = {
        "corpora": "drive",
        "driveId": drive,
        "fields": "files(id, name, createdTime, modifiedTime, lastModifyingUser(displayName), webViewLink, parents), nextPageToken",
        "includeItemsFromAllDrives": True,
        "pageSize": 1000,
        "supportsAllDrives": True,
    }

    # Recursively find all files in drive
    files = []
    while True:
        try:
            results = service.files().list(**kwargs).execute()
        except HttpError as e:
            logging.error(e)

        files.extend(results["files"])

        # If no next page, break out of loop
        if "nextPageToken" not in results:
            break

        # Add next page token to kwargs
        kwargs["pageToken"] = results["nextPageToken"]

    logging.info(f"Found {len(files)} total files")

    for file in files:
        # Create location url and remove parents key
        location = location_url(file["parents"][0])
        file["location"] = location

        file["path"] = build_file_path(files, file["parents"][0])

        file["url"] = file.pop("webViewLink")
        file["lastModifyingUser"] = file.pop("lastModifyingUser")["displayName"]

    output_to_sheet(credentials, sheet, files)


def build_file_path(files, parent_id, path="", file_dict=None):
    if file_dict is None:
        # Create a dictionary to store the files by their IDs
        file_dict = {file["id"]: file for file in files}

    parent_folder = file_dict.get(parent_id)
    if parent_folder is None:
        return path

    path = f"{parent_folder['name']}/{path}"

    return build_file_path(files, parent_folder["parents"][0], path, file_dict)


def output_to_sheet(credentials, sheet, files):
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    # Use pandas to build values for sheet (instead of manually formatting)
    df = pd.DataFrame(files)
    df = df.drop(columns=["id", "parents"])
    df["createdTime"] = pd.to_datetime(df["createdTime"]).dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    df["modifiedTime"] = pd.to_datetime(df["modifiedTime"]).dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    values = [df.keys().tolist()]
    values.extend(df.values.tolist())

    try:
        service.spreadsheets().values().clear(
            spreadsheetId=sheet, range="A:ZZ"
        ).execute()
        logging.info(f"Cleared sheet {sheet}")
    except HttpError as e:
        logging.error(e)

    # Write new data to sheet
    body = {"values": values}
    try:
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=sheet,
                valueInputOption="RAW",
                range="A:ZZ",
                body=body,
            )
            .execute()
        )
        logging.info(f"Written {result.get('updatedCells')} cells to sheet {sheet}")
    except HttpError as e:
        logging.error(e)


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

    args = parser.parse_args()

    logging.basicConfig(
        filename=args.logFile,
        format="%(asctime)s %(levelname)-4s %(message)s",
        datefmt="%b %d %H:%M:%S",
        level=args.logLevel,
    )

    logging.info(f"Starting file audit on drive {args.drive}")
    start = time.time()
    main(args.credentials, args.drive, args.sheet)
    end = time.time()
    logging.info(
        f"File audit complete on drive {args.drive} in {round(end - start, 2)} seconds"
    )
