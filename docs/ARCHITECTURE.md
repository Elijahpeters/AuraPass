# AuraPass architecture

AuraPass separates operator interfaces, domain services, local persistence, recognition, and the simulated controller link. It is designed to run offline after the optional model download.

## Components

| Component | Responsibility |
| --- | --- |
| `app/registration_app.pyw` | Selects a course-form PDF, previews parsed fields, accepts one uploaded image or runs the guided three-sample camera flow, and invokes enrollment. |
| `app/exam_terminal.pyw` | Creates an exam session, stabilizes face-quality observations over multiple frames, requests matching and displays a held decision until `NEXT SCAN`. |
| `app/admin_panel.pyw` | Shows table counts and exposes confirmed history/reset operations. |
| `aurapass/pdf_parser.py` | Extracts fields from the supported course-form text layout. |
| `aurapass/enrollment.py` | Coordinates parsing, duplicate checks, image normalization, embeddings, consistency/collision checks, and transactional database writes. |
| `aurapass/recognition.py` | Groups templates by student, calculates cosine similarity, checks supporting samples, and rejects close runner-up ambiguity. |
| `aurapass/exam_service.py` | Applies active-course, repeat, capacity, and seat-placement policy and writes the decision record. |
| `aurapass/hardware_bridge.py` | Starts or contacts the loopback UDP-to-serial process and sends controller commands. |
| `tools/proteus_bridge.py` | Relays newline-delimited UDP messages to the configured serial port. |

## Enrollment flow

1. `pdfplumber` extracts text from the selected PDF.
2. The layout-specific parser extracts name, matric number, academic fields, and unique course codes.
3. The operator supplies a photo or follows right/left/centre capture prompts.
4. Face-quality checks reject missing, multiple, very small, poorly lit, blurred, or strongly off-centre faces.
5. The configured embedding backend creates one template per accepted sample.
6. Enrollment safety checks compare the new samples with one another and with existing compatible templates.
7. A single SQLite transaction writes the student, courses, course links, face-template metadata and embeddings.
8. Normalized images are saved under the ignored runtime directory; the database stores runtime-relative paths.

The three camera prompts guide the operator, but the implementation does not estimate yaw or prove that the requested pose was followed. A single uploaded photo is also permitted after explicit operator confirmation.

## Recognition and decision flow

The exam terminal collects stable, quality-accepted frames and evaluates up to eight candidates. It selects the highest-confidence candidate result; it does not average embeddings across frames.

Templates are grouped by student. When a student has multiple compatible templates, supporting scores contribute to the final confidence. A close runner-up is rejected as ambiguous. Thresholds are backend-specific prototype constants in `aurapass/recognition.py`.

After recognition, `ExamService` checks:

1. Was the face accepted by the recognizer?
2. Has this student already scanned in this session?
3. Is the student registered for an active course?
4. Is a seat available?

Seat selection is deterministic for a session/course combination. It prefers a free seat without an adjacent student from the same course, then falls back to any free seat. SQLite uniqueness constraints prevent two students from receiving the same seat or one student receiving two seats in the same session.

## Persistence

The schema contains:

- `students`
- `courses`
- `student_courses`
- `face_templates`
- `exam_sessions`
- `seat_assignments`
- `attendance_logs`
- `system_events`
- `schema_meta`

Foreign keys and uniqueness constraints are enabled. Database operations use transactions, but a successful database decision and a later hardware send are not atomic together. Sessions can be created or resumed; the present UI does not expose a session-closing action.

## Controller boundary

The decision service creates commands. The UI sends those commands to a loopback UDP endpoint. A separate process forwards them to serial. The Arduino firmware updates the LCD, LEDs, buzzer, relay, and simulated motor.

This boundary deliberately prevents a missing serial port from corrupting the attendance transaction, but it also means a recorded grant does not prove that the controller actuated. The current firmware does not return an acknowledgement.
