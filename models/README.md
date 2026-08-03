# Local model directory

AuraPass defaults to OpenCV SFace and expects these files here:

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

Download and checksum both files with:

```powershell
python tools/download_models.py
```

The binaries are deliberately untracked. YuNet is published by OpenCV Zoo under the MIT License; SFace is published there under Apache-2.0. See [docs/MODELS.md](../docs/MODELS.md) for source links, hashes, alternatives, and limitations.
