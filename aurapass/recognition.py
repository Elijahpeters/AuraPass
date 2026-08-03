import json
import math
import tempfile
from pathlib import Path

import cv2
import numpy as np

from .database import connect
from .face_engine import FaceEngine
from .paths import CAPTURES_DIR


MATCH_THRESHOLDS = {
    "opencv_sface_2021dec": 0.50,
    "offline_lbp_v3": 0.72,
    "offline_lbp_v2": 0.74,
    "offline_32x32_gray": 0.82,
    "Facenet": 0.68,
}

SUPPORT_THRESHOLDS = {
    "opencv_sface_2021dec": 0.42,
    "offline_lbp_v3": 0.64,
    "offline_lbp_v2": 0.70,
    "Facenet": 0.62,
}

STRONG_SINGLE_THRESHOLDS = {
    "opencv_sface_2021dec": 0.58,
    "offline_lbp_v3": 0.755,
    "offline_lbp_v2": 0.78,
    "Facenet": 0.72,
}


def cosine_similarity(a, b):
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom <= 1e-9:
        return 0.0
    return float(np.dot(va, vb) / denom)


class FaceRecognizer:
    def __init__(self):
        self.engine = FaceEngine()

    def _probe_embedding(self, cropped_face_bgr):
        return self.engine.compute_embedding_from_image(cropped_face_bgr)

    def _load_templates(self):
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ft.student_id,
                    ft.embedding_json,
                    ft.embedding_model,
                    s.name,
                    s.matric,
                    s.level,
                    s.faculty,
                    s.department
                FROM face_templates ft
                JOIN students s ON s.id = ft.student_id
                WHERE ft.active = 1
                ORDER BY ft.student_id
                """
            ).fetchall()

        templates = []
        for row in rows:
            payload = json.loads(row["embedding_json"])
            templates.append({
                "student_id": row["student_id"],
                "name": row["name"],
                "matric": row["matric"],
                "level": row["level"],
                "faculty": row["faculty"],
                "department": row["department"],
                "model": row["embedding_model"],
                "embedding": payload["embedding"],
            })
        return templates

    def match_cropped_face(self, cropped_face_bgr, templates=None):
        templates = self._load_templates() if templates is None else templates
        if not templates:
            return {
                "matched": False,
                "reason": "No enrolled face templates are available.",
                "confidence": 0.0,
                "student": None,
            }

        probe = self._probe_embedding(cropped_face_bgr)
        grouped = {}
        for template in templates:
            if template["model"] != probe["model"]:
                continue
            score = cosine_similarity(probe["embedding"], template["embedding"])
            item = grouped.setdefault(
                template["student_id"],
                {
                    "scores": [],
                    "student": {
                        "id": template["student_id"],
                        "name": template["name"],
                        "matric": template["matric"],
                        "level": template["level"],
                        "faculty": template["faculty"],
                        "department": template["department"],
                    },
                },
            )
            item["scores"].append(score)

        best = None
        for item in grouped.values():
            scores = sorted(item["scores"], reverse=True)
            confidence = scores[0]
            support_threshold = SUPPORT_THRESHOLDS.get(probe["model"], 0.66)
            supporting = len([score for score in scores if score >= support_threshold])
            if len(scores) >= 3 and supporting >= 2:
                confidence = (scores[0] * 0.7) + (scores[1] * 0.3)
            item["confidence"] = confidence
            item["supporting_templates"] = supporting
            item["template_count"] = len(scores)
            if best is None or confidence > best["confidence"]:
                best = item

        if best is None:
            return {
                "matched": False,
                "reason": "No compatible face template was found.",
                "confidence": 0.0,
                "student": None,
            }

        threshold = MATCH_THRESHOLDS.get(probe["model"], 0.70)
        ranked = sorted(grouped.values(), key=lambda item: item["confidence"], reverse=True)
        runner_up = ranked[1] if len(ranked) > 1 else None
        if runner_up and (best["confidence"] - runner_up["confidence"]) < 0.045:
            return {
                "matched": False,
                "reason": "Face match is ambiguous; ask the student to rescan.",
                "confidence": best["confidence"],
                "student": None,
                "supporting_templates": best.get("supporting_templates", 0),
            }

        strong_single_threshold = STRONG_SINGLE_THRESHOLDS.get(probe["model"], threshold + 0.05)
        if (
            best.get("template_count", 0) >= 3
            and best.get("supporting_templates", 0) < 2
            and best["confidence"] < strong_single_threshold
        ):
            return {
                "matched": False,
                "reason": "Face match is not strong enough across enrollment samples.",
                "confidence": best["confidence"],
                "student": None,
                "supporting_templates": best.get("supporting_templates", 0),
            }

        if best["confidence"] < threshold:
            return {
                "matched": False,
                "reason": f"Face confidence too low ({best['confidence']:.3f}, required {threshold:.2f}).",
                "confidence": best["confidence"],
                "student": best["student"],
                "supporting_templates": best.get("supporting_templates", 0),
            }

        return {
            "matched": True,
            "reason": "Face recognized.",
            "confidence": best["confidence"],
            "student": best["student"],
            "supporting_templates": best.get("supporting_templates", 0),
        }
