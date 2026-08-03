import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .face_quality import FaceQualityChecker, image_from_path
from .paths import SFACE_MODEL_PATH, YUNET_MODEL_PATH


DEEPFACE_MODEL = "Facenet"
SUPPORTED_MODES = {"sface", "opencv_sface", "facenet", "deepface", "offline", "lbp", "offline_lbp"}


class FaceEngine:
    _sface_detector = None
    _sface_recognizer = None

    def __init__(self):
        self.quality = FaceQualityChecker()

    def validate_and_save_face(self, source_path, destination_path):
        source_path = Path(source_path)
        destination_path = Path(destination_path)
        image = image_from_path(source_path)
        result = self.quality.evaluate(image)
        if not result.accepted:
            raise ValueError(result.reason)

        face = self.quality.normalized_face(image, result.face_box)
        rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgb).save(destination_path, "JPEG", quality=94)
        return result.metrics

    def compute_embedding(self, image_path):
        mode = self._embedding_mode()
        if mode in {"sface", "opencv_sface"}:
            self._require_sface_models()
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not read image: {image_path}")
            return self._sface_embedding_from_image(image)
        if mode in {"facenet", "deepface"}:
            return self._facenet_embedding(image_path)
        if mode in {"offline", "lbp", "offline_lbp"}:
            return self._offline_lbp_embedding(image_path)
        raise ValueError(f"Unsupported AURAPASS_EMBEDDING_MODE: {mode}")

    def compute_embedding_from_image(self, image):
        mode = self._embedding_mode()
        if mode in {"sface", "opencv_sface"}:
            self._require_sface_models()
            return self._sface_embedding_from_image(image)
        if mode in {"facenet", "deepface"}:
            return self._facenet_embedding(image)
        if mode in {"offline", "lbp", "offline_lbp"}:
            return self._offline_lbp_embedding_from_image(image)
        raise ValueError(f"Unsupported AURAPASS_EMBEDDING_MODE: {mode}")

    @staticmethod
    def _embedding_mode():
        mode = os.environ.get("AURAPASS_EMBEDDING_MODE", "sface").strip().lower()
        if mode not in SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported AURAPASS_EMBEDDING_MODE '{mode}'. "
                f"Choose one of: {', '.join(sorted(SUPPORTED_MODES))}."
            )
        return mode

    @classmethod
    def _require_sface_models(cls):
        if cls._sface_available():
            return
        raise RuntimeError(
            "OpenCV SFace models are missing. Run `python tools/download_models.py` "
            "or set AURAPASS_MODEL_DIR to a directory containing the documented model files."
        )

    @staticmethod
    def _facenet_embedding(image_or_path):
        try:
            from deepface import DeepFace
        except ImportError as exc:
            raise RuntimeError(
                "FaceNet mode requires the optional dependency group: "
                "pip install -e .[facenet]"
            ) from exc

        records = DeepFace.represent(
            img_path=str(image_or_path) if isinstance(image_or_path, (str, Path)) else image_or_path,
            model_name=DEEPFACE_MODEL,
            enforce_detection=False,
            detector_backend="opencv",
            align=True,
        )
        embedding = records[0]["embedding"] if isinstance(records, list) else records["embedding"]
        return {
            "model": DEEPFACE_MODEL,
            "embedding": [float(value) for value in embedding],
            "source": "deepface",
        }

    @classmethod
    def _sface_available(cls):
        return (
            YUNET_MODEL_PATH.exists()
            and SFACE_MODEL_PATH.exists()
            and hasattr(cv2, "FaceDetectorYN_create")
            and hasattr(cv2, "FaceRecognizerSF_create")
        )

    @classmethod
    def _sface_models(cls):
        if cls._sface_detector is None:
            cls._sface_detector = cv2.FaceDetectorYN_create(
                str(YUNET_MODEL_PATH),
                "",
                (320, 320),
                0.7,
                0.3,
                5000,
            )
        if cls._sface_recognizer is None:
            cls._sface_recognizer = cv2.FaceRecognizerSF_create(str(SFACE_MODEL_PATH), "")
        return cls._sface_detector, cls._sface_recognizer

    @classmethod
    def _sface_embedding_from_image(cls, image):
        detector, recognizer = cls._sface_models()
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is not None and len(faces) > 0:
            face = sorted(faces, key=lambda item: item[2] * item[3], reverse=True)[0]
            aligned = recognizer.alignCrop(image, face)
        else:
            aligned = cv2.resize(image, (112, 112), interpolation=cv2.INTER_AREA)
        feature = recognizer.feature(aligned).flatten().astype(np.float32)
        feature /= np.linalg.norm(feature) + 1e-9
        digest = hashlib.sha256(feature.tobytes()).hexdigest()
        return {
            "model": "opencv_sface_2021dec",
            "embedding": [float(v) for v in feature.tolist()],
            "source": f"sface:{digest[:12]}",
        }

    @staticmethod
    def _offline_lbp_embedding(image_path):
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
        return FaceEngine._offline_lbp_embedding_from_image(image)

    @staticmethod
    def _offline_lbp_embedding_from_image(image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

        center = gray[1:-1, 1:-1]
        lbp = np.zeros_like(center, dtype=np.uint8)
        neighbors = [
            (-1, -1), (-1, 0), (-1, 1), (0, 1),
            (1, 1), (1, 0), (1, -1), (0, -1),
        ]
        for bit, (dy, dx) in enumerate(neighbors):
            lbp |= ((gray[1 + dy:127 + dy, 1 + dx:127 + dx] >= center).astype(np.uint8) << bit)

        features = []
        for yy in range(0, 126, 18):
            for xx in range(0, 126, 18):
                cell = lbp[yy:min(yy + 18, 126), xx:min(xx + 18, 126)]
                hist = np.bincount(cell.ravel(), minlength=256).astype(np.float32)
                hist /= hist.sum() + 1e-6
                features.extend(np.sqrt(hist).tolist())

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)
        bins = np.floor((ang % 180) / 20).astype(np.int32)
        for yy in range(0, 128, 32):
            for xx in range(0, 128, 32):
                hist = np.zeros(9, np.float32)
                cell_bins = bins[yy:yy + 32, xx:xx + 32].ravel()
                cell_mag = mag[yy:yy + 32, xx:xx + 32].ravel()
                for bin_index, value in zip(cell_bins, cell_mag):
                    hist[min(int(bin_index), 8)] += value
                hist /= np.linalg.norm(hist) + 1e-6
                features.extend(hist.tolist())

        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
        small = (small - small.mean()) / (small.std() + 1e-6)
        features.extend((small.ravel() * 0.12).tolist())

        arr = np.asarray(features, dtype=np.float32)
        arr /= np.linalg.norm(arr) + 1e-6
        digest = hashlib.sha256(arr.tobytes()).hexdigest()
        return {
            "model": "offline_lbp_v3",
            "embedding": [float(v) for v in arr.flatten().tolist()],
            "source": f"offline:{digest[:12]}",
        }


def embedding_to_json(payload):
    return json.dumps(payload, separators=(",", ":"))
