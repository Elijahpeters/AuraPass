def test_database_starts_empty(isolated_database):
    counts = isolated_database.table_counts()

    assert set(counts) == {
        "students",
        "courses",
        "student_courses",
        "face_templates",
        "exam_sessions",
        "seat_assignments",
        "attendance_logs",
        "system_events",
    }
    assert all(value == 0 for value in counts.values())


def test_foreign_keys_are_enforced(isolated_database):
    import sqlite3

    with isolated_database.connect() as connection:
        try:
            connection.execute(
                "INSERT INTO student_courses (student_id, course_id, source, created_at) VALUES (1, 1, 'test', 'now')"
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Expected SQLite to reject orphaned course registration")
