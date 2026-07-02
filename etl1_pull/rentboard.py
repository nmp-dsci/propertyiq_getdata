from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from propertyiq_getdata.rentboard import update_rentboard


if __name__ == "__main__":
    print("Update rentboard data")
    print(update_rentboard().to_string(index=False))
