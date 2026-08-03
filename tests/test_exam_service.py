from aurapass.exam_service import ExamService, parse_course_codes


def add_student(database, matric, name, courses):
    now = database.utc_now()
    with database.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO students (matric, name, level, faculty, department, created_at, updated_at)
            VALUES (?, ?, '500 Level', 'ENGINEERING', 'Electrical and Electronics Engineering', ?, ?)
            """,
            (matric, name, now, now),
        )
        student_id = cursor.lastrowid
        for code in courses:
            connection.execute("INSERT OR IGNORE INTO courses (code, title) VALUES (?, ?)", (code, None))
            course_id = connection.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()["id"]
            connection.execute(
                "INSERT INTO student_courses (student_id, course_id, source, created_at) VALUES (?, ?, 'synthetic_test', ?)",
                (student_id, course_id, now),
            )
    return {
        "id": student_id,
        "matric": matric,
        "name": name,
        "level": "500 Level",
        "faculty": "ENGINEERING",
        "department": "Electrical and Electronics Engineering",
    }


def match(student, confidence=0.91):
    return {"matched": True, "student": student, "confidence": confidence, "reason": "Face recognized."}


def test_course_code_parser_normalizes_and_deduplicates():
    assert parse_course_codes("eeg501, EEG501 / eee503") == ["EEG501", "EEE503"]


def test_grant_then_same_session_repeat_denial(isolated_database):
    student = add_student(isolated_database, "STU/2026/0001", "ALEX MORGAN", ["EEG501"])
    service = ExamService()
    service.start_session("EEG501", 10, reset_existing=True)

    granted = service.decide_access(match(student))
    repeated = service.decide_access(match(student))

    assert granted["decision"] == "GRANTED"
    assert granted["hardware_commands"][0] == "V,STU/2026/0001,EEG501"
    assert granted["hardware_commands"][1].startswith("O,")
    assert repeated["decision"] == "DENIED"
    assert repeated["hardware_commands"] == ["C"]
    assert "Already scanned" in repeated["reason"]


def test_denies_student_not_registered_for_active_course(isolated_database):
    student = add_student(isolated_database, "STU/2026/0002", "JORDAN LEE", ["EEE503"])
    service = ExamService()
    service.start_session("EEG501", 10, reset_existing=True)

    decision = service.decide_access(match(student))

    assert decision["decision"] == "DENIED"
    assert decision["hardware_commands"] == ["C"]
    assert "not registered" in decision["reason"]


def test_denies_when_hall_is_full(isolated_database):
    first = add_student(isolated_database, "STU/2026/0003", "SAM TAYLOR", ["EEG501"])
    second = add_student(isolated_database, "STU/2026/0004", "RILEY KIM", ["EEG501"])
    service = ExamService()
    service.start_session("EEG501", 1, reset_existing=True)

    assert service.decide_access(match(first))["decision"] == "GRANTED"
    full = service.decide_access(match(second))

    assert full["decision"] == "DENIED"
    assert full["hardware_commands"] == ["F"]
    assert full["reason"] == "Hall capacity is full."


def test_unknown_face_is_logged_as_denied(isolated_database):
    service = ExamService()
    service.start_session("EEG501", 5, reset_existing=True)

    decision = service.decide_access({"matched": False, "reason": "Unknown face.", "confidence": 0.2})

    assert decision["decision"] == "DENIED"
    assert decision["hardware_commands"] == ["C"]
    with isolated_database.connect() as connection:
        row = connection.execute("SELECT decision, reason FROM attendance_logs").fetchone()
    assert dict(row) == {"decision": "DENIED", "reason": "Unknown face."}
