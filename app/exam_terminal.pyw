import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.exam_service import ExamService
from aurapass.face_quality import FaceQualityChecker
from aurapass.hardware_bridge import HardwareBridge
from aurapass.recognition import FaceRecognizer


class SetupDialog(tk.Toplevel):
    def __init__(self, parent, on_start):
        super().__init__(parent)
        self.title("AuraPass Exam Setup")
        self.geometry("430x330")
        self.configure(bg="white")
        self.resizable(False, False)
        self.on_start = on_start
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="Exam Setup", bg="white", fg="#0f172a", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=24, pady=(22, 4))
        tk.Label(self, text="Set the active course and hall capacity before scanning.", bg="white", fg="#475569").pack(anchor="w", padx=24)

        form = tk.Frame(self, bg="white")
        form.pack(fill=tk.X, padx=24, pady=22)
        tk.Label(form, text="Course code(s)", bg="white", fg="#334155").pack(anchor="w")
        self.course_var = tk.StringVar(value="EEG501")
        tk.Entry(form, textvariable=self.course_var, font=("Segoe UI", 12)).pack(fill=tk.X, pady=(4, 14))

        tk.Label(form, text="Hall capacity", bg="white", fg="#334155").pack(anchor="w")
        self.capacity_var = tk.StringVar(value="50")
        tk.Entry(form, textvariable=self.capacity_var, font=("Segoe UI", 12), width=10).pack(anchor="w", pady=(4, 14))

        self.reset_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form, text="Start fresh session for this course/date", variable=self.reset_var, bg="white").pack(anchor="w")

        tk.Button(self, text="Start Exam Session", command=self.start, bg="#0f172a", fg="white", height=2).pack(fill=tk.X, padx=24, pady=(6, 18))
        self.protocol("WM_DELETE_WINDOW", parent.destroy)

    def start(self):
        if self.on_start(self.course_var.get(), self.capacity_var.get(), self.reset_var.get()):
            self.destroy()


class ExamTerminal(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AuraPass Exam Terminal")
        self.geometry("1240x820")
        self.configure(bg="#e8edf2")
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.service = ExamService()
        self.quality = FaceQualityChecker()
        self.recognizer = FaceRecognizer()
        self.bridge = HardwareBridge()
        self.capture = None
        self.running = False
        self.hold = True
        self.scan_phase = "prepare"
        self.prepare_valid_since = None
        self.phase_started_at = time.monotonic()
        self.scan_duration_s = 2.4
        self.prepare_hold_s = 0.9
        self.min_scan_frames = 18
        self.valid_scan_frames = 0
        self.candidate_frames = []
        self.previous_face_box = None
        self.last_frame = None
        self.last_result = None

        self.status_var = tk.StringVar(value="Set up exam session to begin.")
        self.session_var = tk.StringVar(value="No active session")
        self.student_var = tk.StringVar(value="STUDENT: --")
        self.matric_var = tk.StringVar(value="MATRIC: --")
        self.course_var = tk.StringVar(value="COURSE: --")
        self.seat_var = tk.StringVar(value="SEAT: --")
        self.decision_var = tk.StringVar(value="WAITING")
        self.hardware_var = tk.StringVar(value="Hardware command: --")

        self.build_ui()
        SetupDialog(self, self.start_session)

    def build_ui(self):
        header = tk.Frame(self, bg="#0f172a", height=92)
        header.pack(fill=tk.X)
        tk.Label(header, text="AuraPass Exam Terminal", bg="#0f172a", fg="white", font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(header, textvariable=self.session_var, bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 10)).pack(anchor="w", padx=26)

        body = tk.Frame(self, bg="#e8edf2")
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

        left = tk.Frame(body, bg="white")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 14))
        right = tk.Frame(body, bg="white", width=390)
        right.pack(side=tk.LEFT, fill=tk.Y)
        right.pack_propagate(False)

        self.video = tk.Label(left, bg="#020617", text="Camera preview", fg="#94a3b8")
        self.video.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(right, textvariable=self.decision_var, bg="white", fg="#0f172a", font=("Segoe UI", 26, "bold")).pack(anchor="w", padx=22, pady=(24, 8))
        for var in (self.student_var, self.matric_var, self.course_var, self.seat_var):
            tk.Label(right, textvariable=var, bg="white", fg="#0f172a", font=("Segoe UI", 12, "bold"), wraplength=330, justify="left").pack(anchor="w", padx=22, pady=8)

        tk.Label(right, textvariable=self.status_var, bg="white", fg="#334155", wraplength=330, justify="left").pack(anchor="w", padx=22, pady=(16, 8))
        tk.Label(right, textvariable=self.hardware_var, bg="white", fg="#64748b", wraplength=330, justify="left").pack(anchor="w", padx=22, pady=(0, 16))

        tk.Button(right, text="NEXT SCAN", command=self.next_scan, bg="#0f172a", fg="white", height=2).pack(fill=tk.X, padx=22, pady=(12, 8))
        tk.Button(right, text="Exam Setup", command=lambda: SetupDialog(self, self.start_session), height=2).pack(fill=tk.X, padx=22, pady=8)

    def start_session(self, courses, capacity, reset):
        try:
            summary = self.service.start_session(courses, capacity, reset_existing=reset)
        except Exception as exc:
            messagebox.showerror("Exam setup failed", str(exc))
            return False
        self.session_var.set(
            f"Session {summary['session_id']} | Courses: {', '.join(summary['courses'])} | Seats: {summary['assigned']}/{summary['capacity']}"
        )
        if not self.capture:
            self.capture = cv2.VideoCapture(0)
        self.running = True
        self.hold = False
        self.reset_display()
        self.after(30, self.update_frame)
        return True

    def update_frame(self):
        if not self.running or self.hold:
            return

        ok, frame = self.capture.read()
        if not ok:
            self.status_var.set("Camera not available.")
            self.after(250, self.update_frame)
            return

        self.last_frame = frame
        result = self.quality.evaluate(frame)
        self.last_result = result
        display = frame.copy()
        live_ok, live_reason = self._live_scan_quality(result)
        stable_face = live_ok and self._face_box_is_stable(result.face_box)
        if result.face_box:
            x, y, w, h = result.face_box
            color = (34, 197, 94) if stable_face else (248, 113, 113)
            cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)

        self._draw_scan_overlay(display)
        self._update_scan_state(frame, result, stable_face, live_reason)
        self.previous_face_box = result.face_box if result.face_box else None
        self.show_frame(display)
        self.after(35, self.update_frame)

    def _update_scan_state(self, frame, result, stable_face, live_reason):
        now = time.monotonic()
        if self.scan_phase == "prepare":
            if not stable_face:
                self.prepare_valid_since = None
                self.status_var.set(live_reason)
                return

            if self.prepare_valid_since is None:
                self.prepare_valid_since = now
            elapsed = now - self.prepare_valid_since
            if elapsed < self.prepare_hold_s:
                self.status_var.set("Good face detected. Hold steady for analysis.")
                return

            self.scan_phase = "analyzing"
            self.phase_started_at = now
            self.valid_scan_frames = 0
            self.candidate_frames = []
            self.status_var.set("Analysing face quality and identity...")
            return

        if not stable_face:
            self.status_var.set(f"Analysis paused: {live_reason}")
            return

        self.valid_scan_frames += 1
        score = self._quality_score(result.metrics)
        self.candidate_frames.append((score, frame.copy(), result.face_box, result.metrics))
        self.candidate_frames = sorted(self.candidate_frames, key=lambda item: item[0], reverse=True)[:8]

        elapsed = now - self.phase_started_at
        progress = min(100, int((elapsed / self.scan_duration_s) * 100))
        self.status_var.set(f"Analysing face... {progress}%")
        if elapsed >= self.scan_duration_s and self.valid_scan_frames >= self.min_scan_frames:
            self.process_scan()

    def _draw_scan_overlay(self, display):
        if self.scan_phase != "analyzing":
            return
        height, width = display.shape[:2]
        elapsed = time.monotonic() - self.phase_started_at
        progress = max(0.0, min(1.0, elapsed / self.scan_duration_s))
        x = int(width * progress)
        overlay = display.copy()
        cv2.rectangle(overlay, (max(0, x - 16), 0), (min(width, x + 16), height), (56, 189, 248), -1)
        cv2.addWeighted(overlay, 0.18, display, 0.82, 0, display)
        cv2.line(display, (x, 0), (x, height), (125, 211, 252), 3)

    def _live_scan_quality(self, result):
        if not result.accepted:
            return False, result.reason
        metrics = result.metrics
        if float(metrics.get("face_area_ratio", 0.0)) < 0.055:
            return False, "Move closer to the camera."
        if float(metrics.get("blur_score", 0.0)) < 95.0:
            return False, "Face is too soft; hold still and improve the light."
        if float(metrics.get("brightness", 0.0)) < 62.0:
            return False, "Lighting is too dark; move toward a brighter place."
        if float(metrics.get("contrast", 0.0)) < 22.0:
            return False, "Lighting is too flat; face details are not clear."
        return True, "Good face detected."

    def _face_box_is_stable(self, face_box):
        if not face_box or not self.previous_face_box:
            return True
        x, y, w, h = face_box
        px, py, pw, ph = self.previous_face_box
        center_shift = abs((x + w / 2.0) - (px + pw / 2.0)) / max(w, 1)
        size_shift = abs((w * h) - (pw * ph)) / max(w * h, 1)
        return center_shift <= 0.08 and size_shift <= 0.12

    @staticmethod
    def _quality_score(metrics):
        brightness = float(metrics.get("brightness", 128.0))
        blur = min(float(metrics.get("blur_score", 0.0)), 700.0)
        contrast = min(float(metrics.get("contrast", 0.0)), 90.0)
        area = float(metrics.get("face_area_ratio", 0.0)) * 900.0
        center_penalty = (float(metrics.get("center_offset_x", 0.0)) + float(metrics.get("center_offset_y", 0.0))) * 140.0
        brightness_penalty = abs(brightness - 125.0) * 0.35
        return blur + contrast + area - center_penalty - brightness_penalty

    def show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((760, 620), Image.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        self.video.config(image=photo, text="")
        self.video.image = photo

    def process_scan(self):
        self.hold = True
        self.scan_phase = "prepare"
        ranked_frames = self.candidate_frames or [(0, self.last_frame, self.last_result.face_box, self.last_result.metrics)]
        templates = self.recognizer._load_templates()
        best_match = None
        best_metrics = None
        for _, frame, face_box, metrics in ranked_frames:
            crop = self.quality.normalized_face(frame, face_box)
            match = self.recognizer.match_cropped_face(crop, templates=templates)
            if best_match is None or match.get("confidence", 0.0) > best_match.get("confidence", 0.0):
                best_match = match
                best_metrics = metrics
        match = best_match or {
            "matched": False,
            "reason": "Face not recognized.",
            "confidence": 0.0,
            "student": None,
        }
        if not match.get("matched") and match.get("confidence", 0.0) >= 0.66:
            match = {
                **match,
                "reason": f"Face was close but not clear enough ({match.get('confidence', 0.0):.3f}). Move closer, improve light, and scan again.",
                "rescan_recommended": True,
            }
        self.candidate_frames = []
        decision = self.service.decide_access(match)
        self.apply_decision(decision)

    def apply_decision(self, decision):
        student = decision.get("student") or {}
        self.decision_var.set(decision["decision"])
        self.student_var.set(f"STUDENT: {student.get('name', '--')}")
        self.matric_var.set(f"MATRIC: {student.get('matric', '--')}")
        self.course_var.set(f"COURSE: {decision.get('course') or '--'}")
        self.seat_var.set(f"SEAT: {decision.get('seat') or '--'}")
        self.status_var.set(decision["reason"])
        commands = decision.get("hardware_commands") or [decision["hardware_command"]]
        self.send_hardware_async(commands, granted=(decision["decision"] == "GRANTED"))
        summary = self.service.session_summary()
        self.session_var.set(
            f"Session {summary['session_id']} | Courses: {', '.join(summary['courses'])} | Seats: {summary['assigned']}/{summary['capacity']} | Free: {summary['free']}"
        )

    def reset_display(self):
        self.decision_var.set("WAITING")
        self.student_var.set("STUDENT: --")
        self.matric_var.set("MATRIC: --")
        self.course_var.set("COURSE: --")
        self.seat_var.set("SEAT: --")
        self.status_var.set("Position one student face in front of the camera.")
        self.hardware_var.set("Hardware command: --")
        self.scan_phase = "prepare"
        self.prepare_valid_since = None
        self.phase_started_at = time.monotonic()
        self.valid_scan_frames = 0
        self.candidate_frames = []
        self.previous_face_box = None

    def next_scan(self):
        if not self.service.session_id:
            messagebox.showwarning("No session", "Start an exam session first.")
            return
        self.bridge.send("C")
        self.reset_display()
        self.hold = False
        self.after(30, self.update_frame)

    def send_hardware_async(self, commands, granted=False):
        delay = 2.0 if granted and len(commands) > 1 else 0.0
        self.hardware_var.set("Sending hardware command...")

        def worker():
            ok, msg = self.bridge.send_sequence(commands, delay_s=delay)
            self.after(0, lambda: self.hardware_var.set(msg if ok else f"Hardware offline: {msg}"))

        threading.Thread(target=worker, daemon=True).start()

    def close(self):
        self.running = False
        try:
            self.bridge.send("C")
        except Exception:
            pass
        if self.capture:
            self.capture.release()
        self.destroy()


def main():
    app = ExamTerminal()
    app.mainloop()


if __name__ == "__main__":
    main()
