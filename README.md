# propertyiq_getdata

Active ETL code for the trusted NSW property sales and NSW rental bond datasets:

- `data/nswgov_df.csv`
- `data/rentboard_df.csv`

The active sources are `nswgov` and `rentboard`. The older listing scrapers and
`etl4_load/` scripts are historical and should not be run as part of updating
these two CSVs.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

By default the pipeline uses the repo-local `data/` directory. Override it with
`--data-dir`, `PROPERTYIQ_DATA_DIR`, or `DATA_DIR`.

## Check the trusted outputs

```bash
scripts/data_pull.sh
python -m propertyiq_getdata audit --data-dir data
python -m pytest
```

## Update NSW Valuer General sales

```bash
python -m propertyiq_getdata nswgov pull --data-dir data
python -m propertyiq_getdata nswgov extract --data-dir data
python -m propertyiq_getdata nswgov transform --data-dir data
```

The legacy entrypoints still work and delegate to the same implementation:

```bash
python etl1_pull/nswgov.py
python etl2_extract/nswgov.py
python etl3_transform/nswgov.py
```

## Update NSW rental bond data

```bash
python -m propertyiq_getdata rentboard update --data-dir data
```

The legacy entrypoint still works:

```bash
python etl1_pull/rentboard.py
```

## Notes

Raw downloaded files are written under `data/raw/{source}/`. Intermediate NSW
ETL2 files are written under `data/interim/nswgov/output_etl2/`. The final CSV
contracts stay at the repo-local `data/*.csv` paths.

## Diagnostics

Compare the latest NSWGOV output to the newest backup for one postcode or suburb:

```bash
python scripts/compare_nswgov_latest_backup.py --postcode 2077
python scripts/compare_nswgov_latest_backup.py --suburb HORNSBY
```

The script prints the monthly average sale-price summary and writes a line chart
to `data/diagnostics/`, with one line for `backup` and one line for `latest`.

## Google Drive Data Storage

Data CSVs are ignored by git and stored in Google Drive. The Drive folder created
for this project is:

```text
propertyiq_getdata/
  data/
    current/   # latest nswgov_df.csv and rentboard_df.csv
    previous/  # exactly one previous-run backup
```

Drive folder URLs:

- Root: https://drive.google.com/drive/folders/1pVhbegnVbkHHXx3vJOu13EgJJPPtM4rH
- Data: https://drive.google.com/drive/folders/1sP06qpp9TcihGfedxTngp9vhXMZeyUyK
- Current: https://drive.google.com/drive/folders/1ugAN75wxaoVfiOGpfA3AwNam-EcYH5sm
- Previous: https://drive.google.com/drive/folders/1g-5AVG1Ak9rbwnaYXjV-e_Pmz4BBO-SY

Install and configure `rclone` once:

```bash
brew install rclone
rclone config
```

Create a Google Drive remote named `gdrive`, or set `RCLONE_REMOTE` to the remote
name you choose.

Check the setup:

```bash
scripts/google_drive_check.sh
```

Seed Google Drive the first time, using local refreshed files as `current/` and
the newest local `data/backups/*` folder as `previous/`:

```bash
scripts/data_seed_google_drive.sh
```

Pull current data before local work:

```bash
scripts/data_pull.sh
```

After a successful refresh and test run, push the updated data and rotate the one
backup:

```bash
scripts/data_push_with_one_backup.sh
```

The push script deletes any old files in Drive `previous/`, copies Drive
`current/` into `previous/`, then replaces Drive `current/` with local
`data/nswgov_df.csv` and `data/rentboard_df.csv`.
