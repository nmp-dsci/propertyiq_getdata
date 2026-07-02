from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from propertyiq_getdata.nswgov import pull_nswgov


def get_nswgov(data_dir=None):
    return pull_nswgov(data_dir=data_dir)


if __name__ == "__main__":
    print("Pull NSWGOV data")
    print(get_nswgov().to_string(index=False))
