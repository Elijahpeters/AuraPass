from .database import connect, init_db, table_counts
from .paths import FACE_IMAGES_DIR


def clear_exam_history():
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM attendance_logs")
        conn.execute("DELETE FROM seat_assignments")
        conn.execute("DELETE FROM exam_sessions")
    return table_counts()


def reset_all_data():
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM attendance_logs")
        conn.execute("DELETE FROM seat_assignments")
        conn.execute("DELETE FROM exam_sessions")
        conn.execute("DELETE FROM face_templates")
        conn.execute("DELETE FROM student_courses")
        conn.execute("DELETE FROM courses")
        conn.execute("DELETE FROM students")
        conn.execute("DELETE FROM system_events")
        for table in ("students", "courses", "face_templates", "exam_sessions", "seat_assignments", "attendance_logs", "system_events"):
            conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))

    if FACE_IMAGES_DIR.exists():
        for path in FACE_IMAGES_DIR.iterdir():
            if path.is_file():
                path.unlink()
    return table_counts()
