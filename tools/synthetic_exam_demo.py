"""Run a deterministic, non-biometric demonstration of exam-access policy."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass import database
from aurapass.exam_service import ExamService


COURSE_CODE = "EEG501"


def _add_student(matric, name, courses):
    now = database.utc_now()
    with database.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO students (matric, name, level, faculty, department, created_at, updated_at)
            VALUES (?, ?, '500 Level', 'Engineering', 'Electrical and Electronics Engineering', ?, ?)
            """,
            (matric, name, now, now),
        )
        student_id = cursor.lastrowid
        for code in courses:
            connection.execute("INSERT OR IGNORE INTO courses (code, title) VALUES (?, ?)", (code, None))
            course_id = connection.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()["id"]
            connection.execute(
                """
                INSERT INTO student_courses (student_id, course_id, source, created_at)
                VALUES (?, ?, 'synthetic_demo', ?)
                """,
                (student_id, course_id, now),
            )
    return {
        "id": student_id,
        "matric": matric,
        "name": name,
        "level": "500 Level",
        "faculty": "Engineering",
        "department": "Electrical and Electronics Engineering",
    }


def _synthetic_match(student):
    return {
        "matched": True,
        "student": student,
        "confidence": None,
        "reason": "Synthetic match fixture; no biometric analysis was performed.",
    }


def _print_scenario(index, label, decision):
    print(f"\n[{index}] {label}")
    print(f"Decision: {decision['decision']}")
    print(f"Reason: {decision['reason']}")

    student = decision.get("student")
    if student:
        print(f"Student: {student['name']} ({student['matric']})")
    if decision.get("course"):
        print(f"Course: {decision['course']}")
    if decision.get("seat") is not None:
        print(f"Seat: {decision['seat']}")

    commands = decision.get("hardware_commands", [])
    print(f"Controller dry run: {';'.join(commands)}")


def run_demo():
    """Run the real exam policy service against disposable fictional records."""
    original_database_path = database.DATABASE_PATH
    original_ensure_directories = database.ensure_directories

    with TemporaryDirectory(prefix="aurapass-synthetic-demo-") as temporary_directory:
        demo_database_path = Path(temporary_directory) / "demo.db"
        database.DATABASE_PATH = demo_database_path
        database.ensure_directories = lambda: demo_database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            database.init_db()
            enrolled = _add_student("DEMO-001", "Alex Example", [COURSE_CODE])
            repeat = enrolled
            wrong_course = _add_student("DEMO-002", "Casey Sample", ["EEE503"])
            overflow = _add_student("DEMO-003", "Riley Fiction", [COURSE_CODE])

            service = ExamService()
            service.start_session(COURSE_CODE, 1, hall_name="Synthetic Demo Hall", reset_existing=True)

            scenarios = [
                ("Registered student, seat available", _synthetic_match(enrolled)),
                ("Same student scanned again", _synthetic_match(repeat)),
                ("Student not registered for the active course", _synthetic_match(wrong_course)),
                ("Registered student, hall already full", _synthetic_match(overflow)),
                (
                    "No synthetic identity match supplied",
                    {"matched": False, "confidence": None, "reason": "No synthetic match was supplied."},
                ),
            ]

            decisions = []
            for label, match_result in scenarios:
                decisions.append({"label": label, "decision": service.decide_access(match_result)})

            print("AuraPass synthetic exam-access demo")
            print("Fictional records and injected policy outcomes only; no biometric analysis is performed.")
            print("One-seat EEG501 session; controller commands are printed and never transmitted.")
            for index, scenario in enumerate(decisions, start=1):
                _print_scenario(index, scenario["label"], scenario["decision"])
            print("\nDemo database is temporary and will be removed on exit.")
            return decisions
        finally:
            database.DATABASE_PATH = original_database_path
            database.ensure_directories = original_ensure_directories


def main():
    run_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
