import json
from pathlib import Path

from .database import connect, init_db, log_event, utc_now
from .enrollment_safety import load_existing_templates, validate_enrollment_samples
from .face_engine import FaceEngine, embedding_to_json
from .paths import FACE_IMAGES_DIR, runtime_relative
from .pdf_parser import parse_course_form


def _course_id(conn, code):
    row = conn.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO courses (code, title) VALUES (?, ?)", (code, None))
    return cur.lastrowid


def preview_course_form(pdf_path):
    return parse_course_form(pdf_path)


def register_student(pdf_path, face_image_path):
    init_db()
    parsed = parse_course_form(pdf_path)
    now = utc_now()
    face_paths = list(face_image_path) if isinstance(face_image_path, (list, tuple)) else [face_image_path]
    if len(face_paths) < 1:
        raise ValueError("At least one face sample is required.")

    engine = FaceEngine()
    samples = []
    saved_paths = []
    safety_report = None
    student_id = None

    try:
        with connect() as conn:
            existing = conn.execute(
                "SELECT id, name, matric FROM students WHERE UPPER(matric) = UPPER(?)",
                (parsed["matric"],),
            ).fetchone()
            if existing:
                raise ValueError(f"{existing['name']} ({existing['matric']}) is already registered")

            existing_templates = load_existing_templates(conn)

            cur = conn.execute(
                """
                INSERT INTO students (matric, name, level, faculty, department, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parsed["matric"],
                    parsed["name"],
                    parsed["level"],
                    parsed["faculty"],
                    parsed["department"],
                    now,
                    now,
                ),
            )
            student_id = cur.lastrowid

            for code in parsed["courses"]:
                course_id = _course_id(conn, code)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO student_courses (student_id, course_id, source, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student_id, course_id, "course_form_pdf", now),
                )

            for index, face_path in enumerate(face_paths, start=1):
                label = "center" if len(face_paths) == 1 else Path(face_path).stem.split("_")[-1]
                safe_label = "".join(ch for ch in label.lower() if ch.isalnum() or ch in ("-", "_")) or str(index)
                image_name = f"{student_id}_{index}_{safe_label}.jpg"
                image_path = FACE_IMAGES_DIR / image_name
                quality = engine.validate_and_save_face(face_path, image_path)
                saved_paths.append(image_path)
                embedding_payload = engine.compute_embedding(image_path)
                stored_image_path = runtime_relative(image_path)
                samples.append({
                    "pose": safe_label,
                    "image_path": stored_image_path,
                    "embedding_model": embedding_payload["model"],
                    "embedding_source": embedding_payload["source"],
                    "embedding": embedding_payload["embedding"],
                    "embedding_payload": embedding_payload,
                    "quality": quality,
                })

            safety_report = validate_enrollment_samples(samples, existing_templates)

            for sample in samples:
                embedding_payload = sample["embedding_payload"]
                quality_json = {
                    "pose": sample["pose"],
                    "safety_check": safety_report,
                    **sample["quality"],
                }
                conn.execute(
                    """
                    INSERT INTO face_templates
                        (student_id, image_path, embedding_json, embedding_model, quality_json, active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        student_id,
                        sample["image_path"],
                        embedding_to_json(embedding_payload),
                        embedding_payload["model"],
                        json.dumps(quality_json, sort_keys=True),
                        now,
                    ),
                )
    except Exception:
        for path in saved_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
        raise

    public_samples = []
    for sample in samples:
        public_samples.append({
            "pose": sample["pose"],
            "image_path": sample["image_path"],
            "embedding_model": sample["embedding_model"],
            "embedding_source": sample["embedding_source"],
            "quality": sample["quality"],
        })

    record = {
        "student_id": student_id,
        "name": parsed["name"],
        "matric": parsed["matric"],
        "level": parsed["level"],
        "faculty": parsed["faculty"],
        "department": parsed["department"],
        "courses": parsed["courses"],
        "image_path": public_samples[0]["image_path"],
        "image_paths": [sample["image_path"] for sample in public_samples],
        "sample_count": len(public_samples),
        "embedding_model": public_samples[0]["embedding_model"],
        "embedding_source": public_samples[0]["embedding_source"],
        "quality": public_samples[0]["quality"],
        "samples": public_samples,
        "safety_check": safety_report,
    }
    log_event(
        "student_registered",
        {
            "student_id": student_id,
            "matric": parsed["matric"],
            "samples": len(public_samples),
            "safety_check": safety_report,
        },
    )
    return record
