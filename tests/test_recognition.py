import numpy as np

from aurapass.recognition import FaceRecognizer, cosine_similarity


def template(student_id, name, embedding):
    return {
        "student_id": student_id,
        "name": name,
        "matric": f"STU/2026/{student_id:04d}",
        "level": "500 Level",
        "faculty": "ENGINEERING",
        "department": "Electrical and Electronics Engineering",
        "model": "opencv_sface_2021dec",
        "embedding": embedding,
    }


def recognizer_with_probe(embedding):
    recognizer = FaceRecognizer.__new__(FaceRecognizer)
    recognizer._probe_embedding = lambda _image: {
        "model": "opencv_sface_2021dec",
        "embedding": embedding,
    }
    return recognizer


def test_cosine_similarity_handles_identical_and_orthogonal_vectors():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0


def test_multi_template_match_uses_supporting_synthetic_vectors():
    recognizer = recognizer_with_probe([1.0, 0.0, 0.0])
    templates = [
        template(1, "ALEX MORGAN", [1.0, 0.0, 0.0]),
        template(1, "ALEX MORGAN", [0.98, 0.02, 0.0]),
        template(1, "ALEX MORGAN", [0.96, 0.04, 0.0]),
        template(2, "JORDAN LEE", [0.0, 1.0, 0.0]),
    ]

    result = recognizer.match_cropped_face(np.zeros((8, 8, 3), dtype=np.uint8), templates=templates)

    assert result["matched"] is True
    assert result["student"]["matric"] == "STU/2026/0001"
    assert result["supporting_templates"] == 3


def test_close_runner_up_is_rejected_as_ambiguous():
    recognizer = recognizer_with_probe([1.0, 0.0])
    templates = [
        template(1, "ALEX MORGAN", [1.0, 0.0]),
        template(2, "JORDAN LEE", [0.999, 0.045]),
    ]

    result = recognizer.match_cropped_face(np.zeros((8, 8, 3), dtype=np.uint8), templates=templates)

    assert result["matched"] is False
    assert "ambiguous" in result["reason"]
