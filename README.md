# Drive File Audit
Script to find and audit all files within a Google Drive Folder or Shared Drive and outputs relevant information into a Google Sheet for auditing purposes.
## Cloud Console Setup
1. Create new project
2. Enable Drive and Sheets APIs in "APIs and services"
3. Go to "Credentials" and create a new Service Account
4. Enter service account and create new key, download JSON key file
## Installation
1. Clone Repository
2. `pip3 install -r requirements.txt`
## Usage
1. Add service account as viewer to Google Drive Folder/Shared Drive
2. Add service account as editor to Google Sheet for audit output
3. Run the tool
```
$ python3 main.py -h
$ python3 main.py <credentials.json> <drive_id> <sheet_id>
```
