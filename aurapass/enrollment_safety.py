import json
from collections import defaultdict

from .recognition import (
    MATCH_THRESHOLDS,
    STRONG_SINGLE_THRESHOLDS,
    SUPPORT_THRESHOLDS,
    cosine_similarity,
)


DEFAULT_MIN_POSE_PAIR_SCORE = 0.56
DEFAULT_MIN_STRONG_PAIR_SCORE = 0.72
MODEL_CONSISTENCY_LIMITS = {
    "opencv_sface_2021dec": {
        "min_pose_pair_score": -1.0,
        "min_strong_pair_score": 0.50,
    },
}


def load_existing_templates(conn):
    rows = conn.execute(
        """
        SELECT
            ft.student_id,
            ft.embedding_json,
            ft.embedding_model,
            s.name,
            s.matric
        FROM face_templates ft
        JOIN students s ON s.id = ft.student_id
        WHERE ft.active = 1
        ORDER BY ft.student_id, ft.id
        """
    ).fetchall()
    templates = []
    for row in rows:
        payload = json.loads(row["embedding_json"])
        templates.append({
            "student_id": row["student_id"],
            "name": row["name"],
            "matric": row["matric"],
            "model": row["embedding_model"],
            "embedding": payload["embedding"],
        })
    return templates


def validate_enrollment_samples(samples, existing_templates):
    consistency = _validate_sample_consistency(samples)
    collision = _validate_database_collision(samples, existing_templates)
    return {
        "status": "passed",
        "sample_consistency": consistency,
        "database_collision": collision,
    }


def _validate_sample_consistency(samples):
    if len(samples) < 2:
        return {
            "status": "single_sample",
            "minimum_pair_score": None,
            "strongest_pair_score": None,
            "message": "Single-sample enrollment accepted by operator confirmation.",
        }

    pair_scores = []
    best_by_index = [0.0 for _ in samples]
    for i, first in enumerate(samples):
        for j, second in enumerate(samples[i + 1:], start=i + 1):
            if first["embedding_model"] != second["embedding_model"]:
                continue
            score = cosine_similarity(first["embedding"], second["embedding"])
            pair_scores.append({
                "first_pose": first["pose"],
                "second_pose": second["pose"],
                "score": score,
            })
            best_by_index[i] = max(best_by_index[i], score)
            best_by_index[j] = max(best_by_index[j], score)

    if not pair_scores:
        raise ValueError("Face safety check failed because enrollment samples used incompatible embedding models.")

    model = samples[0]["embedding_model"]
    limits = MODEL_CONSISTENCY_LIMITS.get(model, {})
    min_pose_pair_score = limits.get("min_pose_pair_score", DEFAULT_MIN_POSE_PAIR_SCORE)
    min_strong_pair_score = limits.get("min_strong_pair_score", DEFAULT_MIN_STRONG_PAIR_SCORE)
    weakest_best = min(best_by_index)
    strongest_pair = max(item["score"] for item in pair_scores)
    if weakest_best < min_pose_pair_score:
        raise ValueError(
            "Face safety check failed because one enrollment pose does not match the other samples well enough. "
            "Please rescan the student's face."
        )
    if len(samples) >= 3 and strongest_pair < min_strong_pair_score:
        raise ValueError(
            "Face safety check failed because the guided samples do not contain a strong same-person match. "
            "Please rescan with better lighting and a steady face."
        )

    return {
        "status": "passed",
        "minimum_pair_score": round(weakest_best, 4),
        "strongest_pair_score": round(strongest_pair, 4),
        "pair_scores": [
            {
                "first_pose": item["first_pose"],
                "second_pose": item["second_pose"],
                "score": round(item["score"], 4),
            }
            for item in pair_scores
        ],
    }


def _validate_database_collision(samples, existing_templates):
    if not existing_templates:
        return {
            "status": "no_existing_templates",
            "highest_collision_score": None,
            "message": "No existing face templates were present.",
        }

    grouped_scores = defaultdict(list)
    grouped_students = {}
    grouped_models = {}
    for sample in samples:
        for template in existing_templates:
            if sample["embedding_model"] != template["model"]:
                continue
            score = cosine_similarity(sample["embedding"], template["embedding"])
            grouped_scores[template["student_id"]].append(score)
            grouped_students[template["student_id"]] = template
            grouped_models[template["student_id"]] = template["model"]

    highest = {
        "score": 0.0,
        "student": None,
        "supporting_templates": 0,
        "confidence": 0.0,
    }
    for student_id, scores in grouped_scores.items():
        sorted_scores = sorted(scores, reverse=True)
        model = grouped_models[student_id]
        support_threshold = SUPPORT_THRESHOLDS.get(model, 0.66)
        supporting = len([score for score in sorted_scores if score >= support_threshold])
        confidence = sorted_scores[0]
        if len(sorted_scores) >= 3 and supporting >= 2:
            confidence = (sorted_scores[0] * 0.7) + (sorted_scores[1] * 0.3)
        if confidence > highest["confidence"]:
            highest = {
                "score": sorted_scores[0],
                "student": grouped_students[student_id],
                "supporting_templates": supporting,
                "confidence": confidence,
            }

    if highest["student"] is None:
        return {
            "status": "passed",
            "highest_collision_score": None,
            "message": "No compatible existing templates were found.",
        }

    model = highest["student"]["model"]
    threshold = MATCH_THRESHOLDS.get(model, 0.70)
    strong_single = STRONG_SINGLE_THRESHOLDS.get(model, threshold + 0.05)
    collision = highest["confidence"] >= threshold and (
        highest["supporting_templates"] >= 2 or highest["score"] >= strong_single
    )
    if collision:
        student = highest["student"]
        raise ValueError(
            f"Face safety check failed because this face is too close to existing student "
            f"{student['name']} ({student['matric']})."
        )

    return {
        "status": "passed",
        "highest_collision_score": round(highest["confidence"], 4),
        "nearest_student": {
            "name": highest["student"]["name"],
            "matric": highest["student"]["matric"],
        },
        "supporting_templates": highest["supporting_templates"],
    }
