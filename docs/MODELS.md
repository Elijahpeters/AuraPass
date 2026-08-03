# Face-model setup and attribution

AuraPass does not commit vendor model binaries. `tools/download_models.py` downloads exact artifacts and verifies their SHA-256 checksums before installation.

## Default OpenCV path

| Purpose | Artifact | SHA-256 | Upstream licence |
| --- | --- | --- | --- |
| Detection | `face_detection_yunet_2023mar.onnx` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | MIT |
| Recognition | `face_recognition_sface_2021dec.onnx` | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` | Apache-2.0 |

Sources:

- [OpenCV Zoo YuNet directory](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [OpenCV Zoo SFace directory](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)

Install:

```powershell
python tools\download_models.py
```

The downloader stops if an existing or downloaded file does not match the reviewed checksum.

## Optional FaceNet path

DeepFace/FaceNet is not installed by the core dependency set because it is substantially heavier:

```powershell
python -m pip install -e ".[facenet]"
$env:AURAPASS_EMBEDDING_MODE = "facenet"
```

Both enrollment and live recognition use the selected backend. Do not mix templates from different models. Run `python tools\rebuild_face_templates.py` after an intentional backend migration.

## Development-only LBP mode

`AURAPASS_EMBEDDING_MODE=offline_lbp` uses deterministic handcrafted image features. It exists to exercise application logic when vendor models are unavailable. It is not presented as a secure biometric recognizer and should not be used for access decisions.

## Threshold warning

Similarity thresholds in `aurapass/recognition.py` are prototype values. The public repository does not include private face datasets, benchmark images, or a population-calibrated evaluation. No false-accept, false-reject, fairness, or production-accuracy claim should be inferred from them.
