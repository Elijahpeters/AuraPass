"""Download the official OpenCV Zoo models required by AuraPass.

The repository intentionally excludes vendor model binaries. This script downloads
the exact reviewed artifacts and rejects a file when its SHA-256 does not match.
"""

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models"
MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    },
    "face_recognition_sface_2021dec.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name, metadata, destination_dir, force=False):
    destination = destination_dir / name
    expected = metadata["sha256"]
    if destination.exists() and not force:
        if sha256(destination) == expected:
            print(f"ready  {name}")
            return destination
        raise RuntimeError(f"Existing {name} failed checksum; rerun with --force.")

    destination_dir.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    request = urllib.request.Request(metadata["url"], headers={"User-Agent": "AuraPass-model-downloader"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = sha256(temporary)
        if actual != expected:
            raise RuntimeError(f"Checksum mismatch for {name}: expected {expected}, received {actual}.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"saved  {destination}")
    return destination


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        for name, metadata in MODELS.items():
            download(name, metadata, args.directory.resolve(), force=args.force)
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
