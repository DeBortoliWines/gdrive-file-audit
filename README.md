# Drive File Audit
Script to find all files within a Google Drive Folder or Shared Drive and outputs file name, date modified, date created, file URL and parent folder URL into a Google Sheet for auditing or review purposes.

## Cloud Console Setup
1. Create new project
2. Enable Drive and Sheets APIs in "APIs and services"
3. Go to "Credentials" and create a new Service Account
4. Enter service account and create new key, download JSON key file

## Installation
1. Clone Repository
2. `pip3 install -r requirements.txt`

## Usage
1. Add the service account as viewer to Google Drive Folder/Shared Drive. Note: Drive ID is used when running the script.
2. Add the service account as editor to Google Sheet for audit output. Note: Sheet ID is used when running the script.
3. Run the tool
```
$ python3 main.py -h
$ python3 main.py <credentials.json> <drive_id> <sheet_id>
```
4. Information will be logged into the specified Google Sheet.
