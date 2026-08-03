import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.database import init_db, table_counts


def main():
    path = init_db()
    print(f"Database ready: {path}")
    print(json.dumps(table_counts(), indent=2))


if __name__ == "__main__":
    main()
