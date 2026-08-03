from pathlib import Path

import pytest

from aurapass.pdf_parser import _parse_text, parse_course_form


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_extracts_synthetic_course_form_text():
    text = (PROJECT_ROOT / "examples" / "synthetic_course_form.txt").read_text(encoding="utf-8")

    record = _parse_text(text)

    assert record == {
        "name": "ALEX MORGAN",
        "matric": "STU/2026/0001",
        "level": "500 Level",
        "faculty": "ENGINEERING",
        "department": "Electrical and Electronics Engineering",
        "courses": ["EEG501", "EEE503"],
    }


def test_extracts_same_record_from_generated_pdf():
    record = parse_course_form(PROJECT_ROOT / "examples" / "synthetic_course_form.pdf")

    assert record["matric"] == "STU/2026/0001"
    assert record["name"] == "ALEX MORGAN"
    assert record["courses"] == ["EEG501", "EEE503"]


def test_rejects_unrecognized_layout():
    with pytest.raises(ValueError, match="Could not extract"):
        _parse_text("This document does not follow the supported course-form layout.")
