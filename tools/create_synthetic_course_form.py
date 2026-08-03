"""Create a tiny, text-based synthetic course-form PDF for local demos.

The generated identity is fictional and the PDF contains no biometric data.
"""

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEXT = PROJECT_ROOT / "examples" / "synthetic_course_form.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "examples" / "synthetic_course_form.pdf"


def pdf_escape(value):
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(lines):
    drawing = ["BT", "/F1 12 Tf", "72 740 Td"]
    for index, line in enumerate(lines):
        if index:
            drawing.append("0 -18 Td")
        drawing.append(f"({pdf_escape(line)}) Tj")
    drawing.append("ET")
    stream = ("\n".join(drawing) + "\n").encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    document = bytearray(b"%PDF-1.4\n%synthetic\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii"))
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(document)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", type=Path, default=DEFAULT_TEXT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    lines = args.text.read_text(encoding="utf-8").splitlines()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_pdf(lines))
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
