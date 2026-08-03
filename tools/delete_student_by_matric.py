import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.database import connect, table_counts


def main():
    parser = argparse.ArgumentParser(description="Delete one AuraPass student by matric number.")
    parser.add_argument("matric")
    args = parser.parse_args()

    with connect() as conn:
        student = conn.execute(
            "SELECT id, name, matric FROM students WHERE UPPER(matric) = UPPER(?)",
            (args.matric,),
        ).fetchone()
        if not student:
            print(f"No student found for {args.matric}")
            return
        templates = conn.execute(
            "SELECT image_path FROM face_templates WHERE student_id = ?",
            (student["id"],),
        ).fetchall()
        conn.execute("DELETE FROM students WHERE id = ?", (student["id"],))

    for row in templates:
        path = Path(row["image_path"])
        if path.exists():
            path.unlink()

    print(f"Deleted {student['name']} ({student['matric']})")
    print(table_counts())


if __name__ == "__main__":
    main()
