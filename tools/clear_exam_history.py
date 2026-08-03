import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.database import connect, table_counts


def main():
    with connect() as conn:
        conn.execute("DELETE FROM attendance_logs")
        conn.execute("DELETE FROM seat_assignments")
        conn.execute("DELETE FROM exam_sessions")
    print("Cleared exam sessions, seat assignments, and attendance logs.")
    print(table_counts())


if __name__ == "__main__":
    main()

