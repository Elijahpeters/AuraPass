import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
DOCS_DIR = PROJECT_ROOT / "docs"


def _configured_path(variable, default):
    value = os.environ.get(variable)
    return Path(value).expanduser().resolve() if value else default


RUNTIME_DIR = _configured_path("AURAPASS_RUNTIME_DIR", PROJECT_ROOT / "runtime")
DATA_DIR = RUNTIME_DIR / "data"
FACE_IMAGES_DIR = DATA_DIR / "face_images"
CAPTURES_DIR = DATA_DIR / "captures"
DATABASE_DIR = RUNTIME_DIR / "database"
LOGS_DIR = RUNTIME_DIR / "logs"
MODEL_DIR = _configured_path("AURAPASS_MODEL_DIR", PROJECT_ROOT / "models")

DATABASE_PATH = _configured_path("AURAPASS_DB_PATH", DATABASE_DIR / "aurapass.db")
YUNET_MODEL_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL_PATH = MODEL_DIR / "face_recognition_sface_2021dec.onnx"


def ensure_directories():
    for path in (DATA_DIR, FACE_IMAGES_DIR, CAPTURES_DIR, DATABASE_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def runtime_relative(path):
    """Return a portable path for values persisted in the local database."""
    return Path(path).resolve().relative_to(RUNTIME_DIR.resolve()).as_posix()


def resolve_runtime_path(path):
    value = Path(path)
    return value if value.is_absolute() else RUNTIME_DIR / value
