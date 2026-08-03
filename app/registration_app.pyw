import json
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.database import init_db
from aurapass.enrollment import preview_course_form, register_student
from aurapass.face_quality import FaceQualityChecker
from aurapass.paths import CAPTURES_DIR


class CameraWindow(tk.Toplevel):
    def __init__(self, parent, on_capture):
        super().__init__(parent)
        self.title("AuraPass Face Capture")
        self.geometry("900x700")
        self.configure(bg="#0f172a")
        self.on_capture = on_capture
        self.capture = cv2.VideoCapture(0)
        self.quality = FaceQualityChecker()
        self.current_frame = None
        self.current_result = None
        self.samples = []
        self.pose_index = 0
        self.poses = [
            ("right", "Turn your head slightly RIGHT"),
            ("left", "Turn your head slightly LEFT"),
            ("center", "Face the camera CENTER"),
        ]
        self.pose_phase = "prepare"
        self.prepare_valid_since = None
        self.phase_started_at = time.monotonic()
        self.analysis_duration_s = 2.7
        self.prepare_hold_s = 1.2
        self.min_analysis_frames = 34
        self.valid_analysis_frames = 0
        self.best_frame = None
        self.best_score = -1.0
        self.paused_until = 0.0
        self.previous_face_box = None
        self.locked = False
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.video = tk.Label(self, bg="#020617", width=860, height=520)
        self.video.pack(fill=tk.BOTH, expand=True, padx=16, pady=(16, 8))
        self.status = tk.Label(
            self,
            text=self.current_prompt(),
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Segoe UI", 12, "bold"),
        )
        self.status.pack(pady=6)

        controls = tk.Frame(self, bg="#0f172a")
        controls.pack(fill=tk.X, padx=16, pady=(4, 16))
        self.capture_btn = tk.Button(
            controls,
            text="Guided capture running",
            command=lambda: None,
            bg="#15803d",
            fg="white",
            height=2,
            state=tk.DISABLED,
        )
        self.capture_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Button(controls, text="Retake", command=self.retake, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        tk.Button(controls, text="Cancel", command=self.close, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        self.after(20, self.update_frame)

    def update_frame(self):
        if self.locked:
            return
        if time.monotonic() < self.paused_until:
            self.after(50, self.update_frame)
            return

        ok, frame = self.capture.read()
        if not ok:
            self.status.config(text="Camera not available", fg="#f87171")
            self.after(250, self.update_frame)
            return

        self.current_frame = frame
        result = self.quality.evaluate(frame)
        self.current_result = result
        display = frame.copy()

        stable_face = result.accepted and self._face_box_is_stable(result.face_box)
        analysis_progress = self._analysis_progress()
        self._draw_enrollment_overlay(display, result, analysis_progress)
        self._update_capture_state(frame, result, stable_face)

        self.previous_face_box = result.face_box if result.face_box else None
        self.show_frame(display)
        self.after(35, self.update_frame)

    def _draw_enrollment_overlay(self, display, result, analysis_progress):
        height, width = display.shape[:2]
        guide_w = int(width * 0.38)
        guide_h = int(height * 0.54)
        guide_x1 = (width - guide_w) // 2
        guide_y1 = (height - guide_h) // 2
        guide_x2 = guide_x1 + guide_w
        guide_y2 = guide_y1 + guide_h
        cv2.ellipse(
            display,
            ((guide_x1 + guide_x2) // 2, (guide_y1 + guide_y2) // 2),
            (guide_w // 2, guide_h // 2),
            0,
            0,
            360,
            (148, 163, 184),
            2,
        )

        if self.pose_phase == "analyzing":
            pose_key, _ = self.poses[self.pose_index]
            center_x = (guide_x1 + guide_x2) // 2
            if pose_key == "right":
                beam_start, beam_end = center_x, guide_x2
            elif pose_key == "left":
                beam_start, beam_end = center_x, guide_x1
            else:
                beam_start, beam_end = guide_x1, guide_x2
            beam_x = int(beam_start + ((beam_end - beam_start) * analysis_progress))
            overlay = display.copy()
            cv2.rectangle(overlay, (beam_x - 12, guide_y1), (beam_x + 12, guide_y2), (56, 189, 248), -1)
            cv2.addWeighted(overlay, 0.24, display, 0.76, 0, display)
            cv2.line(display, (beam_x, guide_y1), (beam_x, guide_y2), (125, 211, 252), 3)
            cv2.putText(
                display,
                f"ANALYSING {pose_key.upper()}",
                (guide_x1, max(28, guide_y1 - 16)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (125, 211, 252),
                2,
                cv2.LINE_AA,
            )

        if result.face_box:
            x, y, w, h = result.face_box
            color = (34, 197, 94) if result.accepted else (248, 113, 113)
            cv2.ellipse(display, (x + w // 2, y + h // 2), (w // 2, h // 2), 0, 0, 360, color, 2)

        bar_x1, bar_y1 = guide_x1, min(height - 22, guide_y2 + 18)
        bar_x2, bar_y2 = guide_x2, bar_y1 + 8
        cv2.rectangle(display, (bar_x1, bar_y1), (bar_x2, bar_y2), (51, 65, 85), -1)
        fill_x = int(bar_x1 + ((bar_x2 - bar_x1) * analysis_progress))
        cv2.rectangle(display, (bar_x1, bar_y1), (fill_x, bar_y2), (34, 197, 94), -1)

    def _update_capture_state(self, frame, result, stable_face):
        now = time.monotonic()
        pose_key, prompt = self.poses[self.pose_index]
        if self.pose_phase == "prepare":
            if not stable_face:
                self.prepare_valid_since = None
                if result.accepted:
                    self.status.config(text=f"{prompt} - keep your face steady", fg="#fde68a")
                else:
                    self.status.config(text=f"{prompt} - {result.reason}", fg="#fca5a5")
                return

            if self.prepare_valid_since is None:
                self.prepare_valid_since = now
            elapsed = now - self.prepare_valid_since
            if elapsed < self.prepare_hold_s:
                remaining = max(1, int(round(self.prepare_hold_s - elapsed + 0.5)))
                self.status.config(text=f"{prompt} - hold steady, analysis starts in {remaining}s", fg="#bbf7d0")
                return

            self.pose_phase = "analyzing"
            self.phase_started_at = now
            self.valid_analysis_frames = 0
            self.best_frame = frame.copy()
            self.best_score = self._quality_score(result.metrics)
            self.status.config(text=f"Analysing {pose_key.upper()} sample...", fg="#bae6fd")
            return

        if not stable_face:
            reason = result.reason if not result.accepted else "keep your face steady"
            self.status.config(text=f"Analysing {pose_key.upper()} paused - {reason}", fg="#fde68a")
            return

        self.valid_analysis_frames += 1
        score = self._quality_score(result.metrics)
        if score > self.best_score:
            self.best_score = score
            self.best_frame = frame.copy()

        elapsed = now - self.phase_started_at
        progress = min(100, int((elapsed / self.analysis_duration_s) * 100))
        if elapsed < self.analysis_duration_s or self.valid_analysis_frames < self.min_analysis_frames:
            self.status.config(text=f"Analysing {pose_key.upper()} sample... {progress}%", fg="#bae6fd")
            return

        self.status.config(text=f"{pose_key.upper()} sample accepted.", fg="#86efac")
        self.save_current_pose(self.best_frame if self.best_frame is not None else frame)

    def _analysis_progress(self):
        if self.pose_phase != "analyzing":
            return 0.0
        elapsed = time.monotonic() - self.phase_started_at
        return max(0.0, min(1.0, elapsed / self.analysis_duration_s))

    @staticmethod
    def _quality_score(metrics):
        brightness = float(metrics.get("brightness", 128.0))
        blur = min(float(metrics.get("blur_score", 0.0)), 650.0)
        contrast = min(float(metrics.get("contrast", 0.0)), 80.0)
        area = float(metrics.get("face_area_ratio", 0.0)) * 800.0
        center_penalty = (float(metrics.get("center_offset_x", 0.0)) + float(metrics.get("center_offset_y", 0.0))) * 120.0
        brightness_penalty = abs(brightness - 125.0) * 0.35
        return blur + contrast + area - center_penalty - brightness_penalty

    def _face_box_is_stable(self, face_box):
        if not face_box or not self.previous_face_box:
            return True
        x, y, w, h = face_box
        px, py, pw, ph = self.previous_face_box
        center_shift = abs((x + w / 2.0) - (px + pw / 2.0)) / max(w, 1)
        size_shift = abs((w * h) - (pw * ph)) / max(w * h, 1)
        return center_shift <= 0.08 and size_shift <= 0.12

    def show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        img.thumbnail((860, 520), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.video.configure(image=photo)
        self.video.image = photo

    def retake(self):
        self.locked = False
        self.samples = []
        self.pose_index = 0
        self.pose_phase = "prepare"
        self.prepare_valid_since = None
        self.phase_started_at = time.monotonic()
        self.valid_analysis_frames = 0
        self.best_frame = None
        self.best_score = -1.0
        self.paused_until = 0.0
        self.previous_face_box = None
        self.capture_btn.config(state=tk.DISABLED)
        self.status.config(text=self.current_prompt(), fg="#e2e8f0")
        self.after(20, self.update_frame)

    def current_prompt(self):
        if self.pose_index >= len(self.poses):
            return "Face enrollment complete"
        return self.poses[self.pose_index][1]

    def save_current_pose(self, frame):
        CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
        pose_key, _ = self.poses[self.pose_index]
        path = CAPTURES_DIR / f"registration_{int(time.time() * 1000)}_{pose_key}.jpg"
        cv2.imwrite(str(path), frame)
        self.samples.append(str(path))
        self.pose_index += 1
        self.pose_phase = "prepare"
        self.prepare_valid_since = None
        self.phase_started_at = time.monotonic()
        self.valid_analysis_frames = 0
        self.best_frame = None
        self.best_score = -1.0
        self.paused_until = time.monotonic() + 1.0
        self.previous_face_box = None
        if self.pose_index >= len(self.poses):
            self.locked = True
            self.capture_btn.config(text="All samples captured", state=tk.DISABLED)
            self.status.config(text="Enrollment samples captured: right, left, center.", fg="#86efac")
            self.after(900, self.finish_capture)
            return
        self.status.config(text=self.current_prompt(), fg="#e2e8f0")

    def finish_capture(self):
        self.on_capture(self.samples)
        self.close()

    def close(self):
        try:
            self.capture.release()
        except Exception:
            pass
        self.destroy()


class RegistrationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()
        self.title("AuraPass Enrollment")
        self.geometry("1240x820")
        self.minsize(1120, 760)
        self.configure(bg="#e8edf2")
        self.pdf_path = None
        self.face_path = None
        self.face_paths = []
        self.parsed = None
        self.face_preview = None
        self.face_quality_summary = None

        self.status_var = tk.StringVar(value="Ready")
        self.detail_vars = {
            "name": tk.StringVar(value="-"),
            "matric": tk.StringVar(value="-"),
            "level": tk.StringVar(value="-"),
            "faculty": tk.StringVar(value="-"),
            "department": tk.StringVar(value="-"),
            "courses": tk.StringVar(value="-"),
        }
        self.result_vars = {
            "student_id": tk.StringVar(value="-"),
            "image_path": tk.StringVar(value="-"),
            "embedding": tk.StringVar(value="-"),
            "quality": tk.StringVar(value="-"),
        }
        self.build_ui()

    def build_ui(self):
        header = tk.Frame(self, bg="#0f172a", height=92)
        header.pack(fill=tk.X)
        tk.Label(header, text="AuraPass Enrollment", bg="#0f172a", fg="white", font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(header, text="Offline student registration with course-form parsing, face-quality validation, and SQLite storage.", bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 10)).pack(anchor="w", padx=26)

        body = tk.Frame(self, bg="#e8edf2")
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

        left = tk.Frame(body, bg="white", width=390)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        left.pack_propagate(False)

        right = tk.Frame(body, bg="white")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._section_title(left, "Course Form")
        pdf_row = tk.Frame(left, bg="white")
        pdf_row.pack(fill=tk.X, padx=18, pady=(8, 8))
        tk.Button(pdf_row, text="Upload PDF", command=self.upload_pdf, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(pdf_row, text="Preview", command=self.preview_pdf, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(pdf_row, text="Clear", command=self.clear_pdf, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.pdf_label = tk.Label(left, text="No PDF selected", bg="white", fg="#334155", wraplength=300, justify="left")
        self.pdf_label.pack(fill=tk.X, padx=18)

        ttk.Separator(left).pack(fill=tk.X, padx=18, pady=(16, 12))
        self._section_title(left, "Student Face")
        row = tk.Frame(left, bg="white")
        row.pack(fill=tk.X, padx=18, pady=(8, 6))
        tk.Button(row, text="Upload Photo", command=self.upload_face, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(row, text="Scan Face", command=self.scan_face, height=2, bg="#15803d", fg="white").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(row, text="Clear", command=self.clear_face, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        self.face_preview_frame = tk.Frame(left, bg="#f8fafc", width=330, height=220, highlightthickness=1, highlightbackground="#cbd5e1")
        self.face_preview_frame.pack(fill=tk.X, padx=18, pady=(8, 8))
        self.face_preview_frame.pack_propagate(False)
        self.face_canvas = tk.Label(self.face_preview_frame, text="No face selected", bg="#f8fafc", fg="#64748b")
        self.face_canvas.pack(fill=tk.BOTH, expand=True)
        self.face_label = tk.Label(left, text="No face selected", bg="white", fg="#334155", wraplength=300, justify="left")
        self.face_label.pack(fill=tk.X, padx=18)
        self.face_quality_label = tk.Label(left, text="", bg="white", fg="#15803d", wraplength=330, justify="left")
        self.face_quality_label.pack(fill=tk.X, padx=18, pady=(4, 0))

        tk.Button(left, text="Register Student", command=self.register_async, height=2, bg="#0f172a", fg="white").pack(fill=tk.X, padx=18, pady=(12, 6))
        tk.Label(left, textvariable=self.status_var, bg="white", fg="#0f172a", wraplength=300, justify="left").pack(fill=tk.X, padx=18, pady=(6, 0))

        self._section_title(right, "Parsed Student Record")
        grid = tk.Frame(right, bg="white")
        grid.pack(fill=tk.X, padx=22, pady=(10, 18))
        for r, (key, label) in enumerate([
            ("name", "Name"),
            ("matric", "Matric Number"),
            ("level", "Level"),
            ("faculty", "Faculty"),
            ("department", "Department"),
            ("courses", "Courses"),
        ]):
            tk.Label(grid, text=label, bg="white", fg="#475569", width=18, anchor="w").grid(row=r, column=0, sticky="w", pady=8)
            tk.Label(grid, textvariable=self.detail_vars[key], bg="#f8fafc" if key == "courses" else "white", fg="#020617", anchor="w", justify="left", wraplength=660).grid(row=r, column=1, sticky="ew", pady=8)
        grid.columnconfigure(1, weight=1)

        ttk.Separator(right).pack(fill=tk.X, padx=22, pady=12)
        result_header = tk.Frame(right, bg="white")
        result_header.pack(fill=tk.X, padx=22, pady=(14, 4))
        tk.Label(result_header, text="Database Result", bg="white", fg="#020617", font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        tk.Button(
            result_header,
            text="Register Student",
            command=self.register_async,
            height=2,
            bg="#0f172a",
            fg="white",
        ).pack(side=tk.RIGHT)
        result = tk.Frame(right, bg="white")
        result.pack(fill=tk.X, padx=22, pady=(10, 0))
        for r, (key, label) in enumerate([
            ("student_id", "Student ID"),
            ("image_path", "Saved Face Path"),
            ("embedding", "Embedding"),
            ("quality", "Safety / Quality"),
        ]):
            tk.Label(result, text=label, bg="white", fg="#475569", width=18, anchor="w").grid(row=r, column=0, sticky="w", pady=8)
            tk.Label(result, textvariable=self.result_vars[key], bg="white", fg="#020617", anchor="w", justify="left", wraplength=700).grid(row=r, column=1, sticky="ew", pady=8)
        result.columnconfigure(1, weight=1)

    @staticmethod
    def _section_title(parent, text):
        tk.Label(parent, text=text, bg=parent["bg"], fg="#020617", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(18, 4))

    @staticmethod
    def compact(path, max_len=52):
        if not path:
            return "No file selected"
        return path if len(path) <= max_len else "..." + path[-(max_len - 3):]

    def upload_pdf(self):
        path = filedialog.askopenfilename(title="Select course form PDF", filetypes=[("PDF files", "*.pdf")])
        if path:
            self.pdf_path = path
            self.parsed = None
            self.pdf_label.config(text=self.compact(path))
            self.preview_pdf()

    def preview_pdf(self):
        if not self.pdf_path:
            messagebox.showwarning("PDF required", "Select the student's course form PDF first.")
            return
        try:
            self.status_var.set("Parsing PDF...")
            self.update_idletasks()
            self.parsed = preview_course_form(self.pdf_path)
            self.update_details(self.parsed)
            self.status_var.set("PDF parsed successfully.")
        except Exception as exc:
            self.status_var.set("PDF parsing failed.")
            messagebox.showerror("PDF parsing failed", str(exc))

    def update_details(self, parsed):
        for key in ("name", "matric", "level", "faculty", "department"):
            self.detail_vars[key].set(parsed.get(key, "-"))
        self.detail_vars["courses"].set(", ".join(parsed.get("courses", [])))

    def clear_pdf(self):
        self.pdf_path = None
        self.parsed = None
        self.pdf_label.config(text="No PDF selected")
        for var in self.detail_vars.values():
            var.set("-")
        self.status_var.set("Course form cleared.")

    def upload_face(self):
        path = filedialog.askopenfilename(title="Select face image", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
        if path:
            self.set_face_path(path)

    def set_face_path(self, path):
        paths = list(path) if isinstance(path, (list, tuple)) else [path]
        try:
            image_bgr = cv2.imread(str(paths[-1]))
            if image_bgr is None:
                raise ValueError("Could not read the selected image.")
            checker = FaceQualityChecker()
            result = checker.evaluate(image_bgr)
            if not result.accepted:
                raise ValueError(result.reason)
            crop = checker.crop_face(image_bgr, result.face_box)
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(crop_rgb)
        except Exception as exc:
            self.clear_face()
            messagebox.showerror("Face image rejected", str(exc))
            return

        self.face_path = paths[-1]
        self.face_paths = paths
        self.face_quality_summary = result.metrics
        if len(paths) == 1:
            self.face_label.config(text=self.compact(paths[0], 48))
        else:
            self.face_label.config(text=f"{len(paths)} guided samples captured: right, left, center")
        image.thumbnail((310, 200), Image.LANCZOS)
        canvas = Image.new("RGB", (310, 200), "#f8fafc")
        canvas.paste(image, ((310 - image.width) // 2, (200 - image.height) // 2))
        self.face_preview = ImageTk.PhotoImage(canvas)
        self.face_canvas.config(image=self.face_preview, text="")
        self.face_quality_label.config(
            text=f"Face samples accepted. Blur {result.metrics.get('blur_score', '-')}, area {result.metrics.get('face_area_ratio', '-')}.",
            fg="#15803d",
        )

    def clear_face(self):
        self.face_path = None
        self.face_paths = []
        self.face_quality_summary = None
        self.face_preview = None
        self.face_canvas.config(image="", text="No face selected")
        self.face_label.config(text="No face selected")
        self.face_quality_label.config(text="")

    def scan_face(self):
        CameraWindow(self, self.set_face_path)

    def register_async(self):
        if not self.pdf_path:
            messagebox.showwarning("PDF required", "Upload the student's course form PDF first.")
            return
        if not self.face_path:
            messagebox.showwarning("Face image required", "Upload or scan the student's face first.")
            return
        if len(self.face_paths) < 3:
            if not messagebox.askyesno(
                "Single face sample",
                "AuraPass enrollment works best with guided right, left, and center samples. Continue with one uploaded photo?",
            ):
                return
        threading.Thread(target=self.register_student, daemon=True).start()

    def register_student(self):
        try:
            self.after(0, lambda: self.status_var.set("Registering student and running face safety checks..."))
            record = register_student(self.pdf_path, self.face_paths or [self.face_path])
            self.after(0, lambda: self.registration_complete(record))
        except Exception as exc:
            self.after(0, lambda exc=exc: self.registration_failed(exc))

    def registration_complete(self, record):
        self.result_vars["student_id"].set(str(record["student_id"]))
        self.result_vars["image_path"].set(record["image_path"])
        self.result_vars["embedding"].set(f"{record['sample_count']} samples, {record['embedding_model']}")
        self.result_vars["quality"].set(self.safety_summary(record))
        self.status_var.set(f"Registered {record['name']} successfully. Face safety checks passed.")
        messagebox.showinfo("Registration complete", f"{record['name']} has been registered. Face safety checks passed.")
        self.reset_for_next_student(keep_result=True)

    @staticmethod
    def safety_summary(record):
        safety = record.get("safety_check") or {}
        consistency = safety.get("sample_consistency") or {}
        collision = safety.get("database_collision") or {}
        pair_min = consistency.get("minimum_pair_score")
        pair_strong = consistency.get("strongest_pair_score")
        collision_score = collision.get("highest_collision_score")
        parts = ["Safety passed"]
        if pair_min is not None:
            parts.append(f"pose min {pair_min}")
        if pair_strong is not None:
            parts.append(f"strong pair {pair_strong}")
        if collision_score is not None:
            parts.append(f"nearest DB score {collision_score}")
        else:
            parts.append(collision.get("message", "no DB collision"))
        return "; ".join(parts)

    def registration_failed(self, exc):
        self.status_var.set("Registration failed.")
        messagebox.showerror("Registration failed", str(exc))

    def reset_for_next_student(self, keep_result=False):
        self.pdf_path = None
        self.face_path = None
        self.face_paths = []
        self.parsed = None
        self.pdf_label.config(text="No PDF selected")
        self.clear_face()
        for var in self.detail_vars.values():
            var.set("-")
        if not keep_result:
            for var in self.result_vars.values():
                var.set("-")
            self.status_var.set("Ready")
        else:
            self.status_var.set("Ready for next student.")


def main():
    app = RegistrationApp()
    app.mainloop()


if __name__ == "__main__":
    main()
