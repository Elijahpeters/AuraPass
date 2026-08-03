import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.database import connect, init_db, utc_now
from aurapass.face_engine import FaceEngine, embedding_to_json
from aurapass.face_quality import FaceQualityChecker, image_from_path
from aurapass.paths import resolve_runtime_path


def main():
    init_db()
    engine = FaceEngine()
    checker = FaceQualityChecker()
    rebuilt = 0
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, student_id, image_path, quality_json
            FROM face_templates
            WHERE active = 1
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            image_path = resolve_runtime_path(row["image_path"])
            if not image_path.exists():
                print(f"SKIP missing image: {image_path}")
                continue
            image = image_from_path(image_path)
            quality = checker.evaluate(image)
            payload = engine.compute_embedding(image_path)
            try:
                previous_quality = json.loads(row["quality_json"] or "{}")
            except Exception:
                previous_quality = {}
            pose = previous_quality.get("pose")
            if not pose:
                stem_parts = image_path.stem.split("_")
                pose = stem_parts[-1] if stem_parts else "center"
            quality_json = {"pose": pose, **quality.metrics}
            conn.execute(
                """
                UPDATE face_templates
                SET embedding_json = ?, embedding_model = ?, quality_json = ?, created_at = ?
                WHERE id = ?
                """,
                (
                    embedding_to_json(payload),
                    payload["model"],
                    json.dumps(quality_json, sort_keys=True),
                    utc_now(),
                    row["id"],
                ),
            )
            rebuilt += 1
            print(f"REB rebuilt student_id={row['student_id']} model={payload['model']} image={image_path.name}")
    print(f"Rebuilt {rebuilt} face template(s).")


if __name__ == "__main__":
    main()
