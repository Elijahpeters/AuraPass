from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

@dataclass
class FaceQualityResult:
    accepted: bool
    reason: str
    face_box: tuple | None
    metrics: dict


class FaceQualityChecker:
    def __init__(self):
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(str(cascade_path))
        if self.detector.empty():
            raise RuntimeError(f"Could not load face detector: {cascade_path}")
        eye_path = Path(cv2.data.haarcascades) / "haarcascade_eye.xml"
        self.eye_detector = cv2.CascadeClassifier(str(eye_path))

    def evaluate(self, image):
        if image is None:
            return FaceQualityResult(False, "No image was supplied.", None, {})

        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(70, 70))
        faces = sorted(([int(v) for v in face] for face in faces), key=lambda face: face[2] * face[3], reverse=True)

        metrics = {
            "image_width": int(width),
            "image_height": int(height),
            "face_count": int(len(faces)),
        }

        if len(faces) == 0:
            return FaceQualityResult(False, "No clear face detected.", None, metrics)

        x, y, w, h = faces[0]
        main_area = w * h
        other_major_faces = [
            face for face in faces[1:]
            if (face[2] * face[3]) >= (main_area * 0.45)
        ]
        metrics["major_face_count"] = int(1 + len(other_major_faces))
        if other_major_faces:
            return FaceQualityResult(False, "Multiple major faces detected; use one student at a time.", (x, y, w, h), metrics)

        face_area_ratio = (w * h) / float(width * height)
        aspect_ratio = w / float(h)
        face_gray = gray[y:y + h, x:x + w]
        blur_score = float(cv2.Laplacian(face_gray, cv2.CV_64F).var())
        brightness = float(face_gray.mean())
        contrast = float(face_gray.std())
        center_x = x + w / 2.0
        center_y = y + h / 2.0
        center_offset_x = abs(center_x - width / 2.0) / width
        center_offset_y = abs(center_y - height / 2.0) / height
        eye_count, eye_angle = self._eye_metrics(face_gray)

        metrics.update({
            "face_x": x,
            "face_y": y,
            "face_w": w,
            "face_h": h,
            "face_area_ratio": round(face_area_ratio, 4),
            "aspect_ratio": round(aspect_ratio, 3),
            "blur_score": round(blur_score, 2),
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "center_offset_x": round(center_offset_x, 3),
            "center_offset_y": round(center_offset_y, 3),
            "eye_count": int(eye_count),
            "eye_angle": round(float(eye_angle), 2) if eye_angle is not None else None,
        })

        if face_area_ratio < 0.025:
            return FaceQualityResult(False, "Face is too far from the camera.", (x, y, w, h), metrics)
        if not 0.72 <= aspect_ratio <= 1.35:
            return FaceQualityResult(False, "Face angle is not frontal enough.", (x, y, w, h), metrics)
        if brightness < 48.0:
            return FaceQualityResult(False, "Lighting is too dark; move toward a brighter place.", (x, y, w, h), metrics)
        if brightness > 220.0:
            return FaceQualityResult(False, "Lighting is too bright; reduce glare on the face.", (x, y, w, h), metrics)
        if contrast < 18.0:
            return FaceQualityResult(False, "Lighting is too flat; face details are not clear.", (x, y, w, h), metrics)
        if blur_score < 45.0:
            return FaceQualityResult(False, "Face image is too blurry.", (x, y, w, h), metrics)
        if center_offset_x > 0.22 or center_offset_y > 0.24:
            return FaceQualityResult(False, "Face is not centered.", (x, y, w, h), metrics)

        return FaceQualityResult(True, "Face quality accepted.", (x, y, w, h), metrics)

    def _eye_metrics(self, face_gray):
        if self.eye_detector.empty():
            return 0, None
        height, width = face_gray.shape[:2]
        upper = face_gray[: int(height * 0.68), :]
        eyes = self.eye_detector.detectMultiScale(upper, scaleFactor=1.08, minNeighbors=5, minSize=(12, 12))
        eyes = sorted(([int(v) for v in eye] for eye in eyes), key=lambda eye: eye[2] * eye[3], reverse=True)
        if len(eyes) < 2:
            return len(eyes), None

        candidates = []
        for eye in eyes[:4]:
            ex, ey, ew, eh = eye
            candidates.append((ex + ew / 2.0, ey + eh / 2.0, ew * eh))
        candidates = sorted(candidates, key=lambda point: point[0])
        left = candidates[0]
        right = candidates[-1]
        if abs(right[0] - left[0]) < width * 0.18:
            return len(eyes), None
        angle = np.degrees(np.arctan2(right[1] - left[1], right[0] - left[0]))
        return len(eyes), angle

    @staticmethod
    def crop_face(image, face_box, padding=0.32):
        x, y, w, h = face_box
        height, width = image.shape[:2]
        pad_x = int(w * padding)
        pad_y = int(h * padding)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(width, x + w + pad_x)
        y2 = min(height, y + h + pad_y)
        return image[y1:y2, x1:x2]

    def normalized_face(self, image, face_box, output_size=(128, 128)):
        face = self.crop_face(image, face_box, padding=0.28)
        if face.size == 0:
            return face

        if not self.eye_detector.empty():
            gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape[:2]
            upper = gray[: int(height * 0.68), :]
            eyes = self.eye_detector.detectMultiScale(upper, scaleFactor=1.08, minNeighbors=5, minSize=(12, 12))
            eyes = sorted(([int(v) for v in eye] for eye in eyes), key=lambda eye: eye[2] * eye[3], reverse=True)
            if len(eyes) >= 2:
                centers = []
                for ex, ey, ew, eh in eyes[:4]:
                    centers.append((ex + ew / 2.0, ey + eh / 2.0, ew * eh))
                centers = sorted(centers, key=lambda point: point[0])
                left = centers[0]
                right = centers[-1]
                if abs(right[0] - left[0]) >= width * 0.18:
                    angle = np.degrees(np.arctan2(right[1] - left[1], right[0] - left[0]))
                    center = ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)
                    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                    face = cv2.warpAffine(face, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return cv2.resize(face, output_size, interpolation=cv2.INTER_AREA)


def image_from_path(path):
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image
