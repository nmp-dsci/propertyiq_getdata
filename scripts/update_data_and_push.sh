#!/usr/bin/env bash
set -euo pipefail

python -m propertyiq_getdata nswgov pull --data-dir data
python -m propertyiq_getdata nswgov extract --data-dir data
python -m propertyiq_getdata nswgov transform --data-dir data
python -m propertyiq_getdata rentboard update --data-dir data
python -m pytest

scripts/data_push_with_one_backup.sh
