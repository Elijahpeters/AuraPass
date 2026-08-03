import pytest

from aurapass.enrollment_safety import validate_enrollment_samples


def sample(pose, embedding):
    return {
        "pose": pose,
        "embedding_model": "opencv_sface_2021dec",
        "embedding": embedding,
    }


def test_consistent_synthetic_templates_pass():
    report = validate_enrollment_samples(
        [
            sample("right", [1.0, 0.0, 0.0]),
            sample("left", [0.98, 0.02, 0.0]),
            sample("center", [0.99, 0.0, 0.01]),
        ],
        existing_templates=[],
    )

    assert report["status"] == "passed"
    assert report["sample_consistency"]["status"] == "passed"


def test_collision_with_existing_synthetic_identity_is_rejected():
    existing = [
        {
            "student_id": 8,
            "name": "EXISTING SYNTHETIC STUDENT",
            "matric": "STU/2026/0008",
            "model": "opencv_sface_2021dec",
            "embedding": [1.0, 0.0, 0.0],
        }
    ]

    with pytest.raises(ValueError, match="too close to existing student"):
        validate_enrollment_samples([sample("center", [1.0, 0.0, 0.0])], existing)
