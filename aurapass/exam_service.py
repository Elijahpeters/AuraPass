import json
import random
import re
import zlib

from .database import connect, init_db, log_event, utc_now


def parse_course_codes(value):
    codes = []
    for code in re.findall(r"\b[A-Z]{2,4}\d{3}\b", (value or "").upper()):
        if code not in codes:
            codes.append(code)
    return codes


class ExamService:
    def __init__(self):
        init_db()
        self.session_id = None
        self.session_code = None
        self.course_codes = []
        self.hall_capacity = 0

    def start_session(self, course_text, hall_capacity, hall_name="Main Hall", reset_existing=False):
        courses = parse_course_codes(course_text)
        if not courses:
            raise ValueError("Enter at least one course code, such as EEG501.")
        capacity = int(hall_capacity)
        if capacity < 1:
            raise ValueError("Hall capacity must be at least 1.")

        now = utc_now()
        base_code = f"{'-'.join(courses)}-{now[:10]}"
        session_code = f"{base_code}-{now[11:19].replace(':', '')}" if reset_existing else base_code
        with connect() as conn:
            existing = conn.execute(
                "SELECT id FROM exam_sessions WHERE session_code = ?",
                (session_code,),
            ).fetchone()
            if existing:
                session_id = existing["id"]
                conn.execute(
                    """
                    UPDATE exam_sessions
                    SET course_codes = ?, hall_name = ?, hall_capacity = ?, status = ?, started_at = COALESCE(started_at, ?)
                    WHERE id = ?
                    """,
                    (",".join(courses), hall_name, capacity, "active", now, session_id),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO exam_sessions
                        (session_code, course_codes, hall_name, hall_capacity, status, created_at, started_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (session_code, ",".join(courses), hall_name, capacity, "active", now, now),
                )
                session_id = cur.lastrowid

        self.session_id = session_id
        self.session_code = session_code
        self.course_codes = courses
        self.hall_capacity = capacity
        log_event("exam_session_started", {"session_id": session_id, "courses": courses, "capacity": capacity})
        return self.session_summary()

    def session_summary(self):
        if not self.session_id:
            return {
                "active": False,
                "session_id": None,
                "courses": [],
                "capacity": 0,
                "assigned": 0,
                "free": 0,
            }
        with connect() as conn:
            assigned = conn.execute(
                "SELECT COUNT(*) AS n FROM seat_assignments WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()["n"]
        return {
            "active": True,
            "session_id": self.session_id,
            "session_code": self.session_code,
            "courses": self.course_codes,
            "capacity": self.hall_capacity,
            "assigned": assigned,
            "free": max(self.hall_capacity - assigned, 0),
        }

    def _student_courses(self, conn, student_id):
        rows = conn.execute(
            """
            SELECT c.code
            FROM student_courses sc
            JOIN courses c ON c.id = sc.course_id
            WHERE sc.student_id = ?
            ORDER BY c.code
            """,
            (student_id,),
        ).fetchall()
        return [row["code"] for row in rows]

    def _next_seat(self, conn, course_code):
        rows = conn.execute(
            "SELECT seat_number, course_code FROM seat_assignments WHERE session_id = ?",
            (self.session_id,),
        ).fetchall()
        occupied = {int(row["seat_number"]): row["course_code"] for row in rows}
        available = [seat for seat in range(1, self.hall_capacity + 1) if seat not in occupied]
        safe = [
            seat for seat in available
            if occupied.get(seat - 1) != course_code and occupied.get(seat + 1) != course_code
        ]
        pool = safe or available
        if not pool:
            return None
        order = self._seat_order(course_code)
        for seat in order:
            if seat in pool:
                return seat
        return pool[0]

    def _seat_order(self, course_code):
        seed_text = f"{self.session_code}|{course_code}|{self.hall_capacity}"
        seed = zlib.crc32(seed_text.encode("utf-8"))
        seats = list(range(1, self.hall_capacity + 1))
        random.Random(seed).shuffle(seats)
        return seats

    def decide_access(self, match_result):
        if not self.session_id:
            raise RuntimeError("Exam session has not been started.")

        now = utc_now()
        if not match_result.get("matched"):
            decision = "RESCAN" if match_result.get("rescan_recommended") else "DENIED"
            self._log(None, decision, match_result.get("reason", "Face not recognized."), match_result.get("confidence"), None, "C")
            return {
                "decision": decision,
                "reason": match_result.get("reason", "Face not recognized."),
                "student": None,
                "seat": None,
                "course": None,
                "hardware_command": "C",
                "hardware_commands": ["C"],
            }

        student = match_result["student"]
        student_id = int(student["id"])
        with connect() as conn:
            existing = conn.execute(
                """
                SELECT seat_number, course_code
                FROM seat_assignments
                WHERE session_id = ? AND student_id = ?
                """,
                (self.session_id, student_id),
            ).fetchone()
            if existing:
                reason = f"Already scanned. Seat {existing['seat_number']}."
                self._log(student_id, "DENIED", reason, match_result["confidence"], existing["seat_number"], "C")
                return {
                    "decision": "DENIED",
                    "reason": reason,
                    "student": student,
                    "seat": existing["seat_number"],
                    "course": existing["course_code"],
                    "hardware_command": "C",
                    "hardware_commands": ["C"],
                }

            student_courses = self._student_courses(conn, student_id)
            matching = [course for course in self.course_codes if course in student_courses]
            if not matching:
                reason = "Student is not registered for today's course."
                self._log(student_id, "DENIED", reason, match_result["confidence"], None, "C")
                return {
                    "decision": "DENIED",
                    "reason": reason,
                    "student": student,
                    "seat": None,
                    "course": None,
                    "hardware_command": "C",
                    "hardware_commands": ["C"],
                }

            seat = self._next_seat(conn, matching[0])
            if seat is None:
                reason = "Hall capacity is full."
                self._log(student_id, "DENIED", reason, match_result["confidence"], None, "F")
                return {
                    "decision": "DENIED",
                    "reason": reason,
                    "student": student,
                    "seat": None,
                    "course": matching[0],
                    "hardware_command": "F",
                    "hardware_commands": ["F"],
                }

            conn.execute(
                """
                INSERT INTO seat_assignments (session_id, student_id, course_code, seat_number, assigned_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.session_id, student_id, matching[0], seat, now),
            )

            verify_command = f"V,{student['matric']},{matching[0]}"
            open_command = f"O,{seat}"
        command = f"{verify_command};{open_command}"
        self._log(student_id, "GRANTED", "Access granted.", match_result["confidence"], seat, command)
        return {
            "decision": "GRANTED",
            "reason": "Access granted.",
            "student": student,
            "seat": seat,
            "course": matching[0],
            "confidence": match_result["confidence"],
            "hardware_command": command,
            "hardware_commands": [verify_command, open_command],
        }

    def _log(self, student_id, decision, reason, confidence, seat, hardware_command):
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO attendance_logs
                    (session_id, student_id, decision, reason, confidence, seat_number, hardware_command, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.session_id, student_id, decision, reason, confidence, seat, hardware_command, utc_now()),
            )
