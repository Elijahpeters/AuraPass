import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.database import init_db, table_counts
from aurapass.paths import DATABASE_PATH, FACE_IMAGES_DIR


def main():
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    if FACE_IMAGES_DIR.exists():
        for image in FACE_IMAGES_DIR.glob("*"):
            if image.is_file():
                image.unlink()
            elif image.is_dir():
                shutil.rmtree(image)
    init_db()
    print(f"AuraPass database reset: {DATABASE_PATH}")
    print(table_counts())


if __name__ == "__main__":
    main()
