import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurapass.admin_service import clear_exam_history, reset_all_data
from aurapass.database import init_db, table_counts
from aurapass.paths import DATABASE_PATH


class AdminPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()
        self.title("AuraPass Database Admin")
        self.geometry("760x520")
        self.configure(bg="#e8edf2")
        self.resizable(False, False)

        self.count_vars = {}
        self.status_var = tk.StringVar(value="Ready")
        self.build_ui()
        self.refresh_counts()

    def build_ui(self):
        header = tk.Frame(self, bg="#0f172a", height=92)
        header.pack(fill=tk.X)
        tk.Label(header, text="AuraPass Database Admin", bg="#0f172a", fg="white", font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(header, text=str(DATABASE_PATH), bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 10)).pack(anchor="w", padx=26)

        body = tk.Frame(self, bg="#e8edf2")
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

        left = tk.Frame(body, bg="white", width=330)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        left.pack_propagate(False)

        right = tk.Frame(body, bg="white")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left, text="Actions", bg="white", fg="#020617", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=20, pady=(22, 12))

        tk.Button(
            left,
            text="Clear Exam History",
            command=self.clear_exams,
            height=2,
            bg="#0f172a",
            fg="white",
        ).pack(fill=tk.X, padx=20, pady=(4, 10))
        tk.Label(
            left,
            text="Clears exam sessions, seat assignments, and attendance logs. Students and face templates remain.",
            bg="white",
            fg="#475569",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 18))

        tk.Button(
            left,
            text="Reset All Database Data",
            command=self.reset_all,
            height=2,
            bg="#b91c1c",
            fg="white",
        ).pack(fill=tk.X, padx=20, pady=(8, 10))
        tk.Label(
            left,
            text="Deletes students, courses, face templates, exam sessions, seats, attendance logs, and saved face images.",
            bg="white",
            fg="#7f1d1d",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", padx=20)

        tk.Label(left, textvariable=self.status_var, bg="white", fg="#0f172a", wraplength=280, justify="left").pack(anchor="w", padx=20, pady=(26, 0))

        tk.Label(right, text="Current Database Counts", bg="white", fg="#020617", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=24, pady=(22, 12))
        grid = tk.Frame(right, bg="white")
        grid.pack(fill=tk.X, padx=24)
        for row, table in enumerate([
            "students",
            "courses",
            "student_courses",
            "face_templates",
            "exam_sessions",
            "seat_assignments",
            "attendance_logs",
            "system_events",
        ]):
            tk.Label(grid, text=table, bg="white", fg="#475569", width=20, anchor="w").grid(row=row, column=0, sticky="w", pady=7)
            var = tk.StringVar(value="-")
            self.count_vars[table] = var
            tk.Label(grid, textvariable=var, bg="#f8fafc", fg="#020617", width=12, anchor="center").grid(row=row, column=1, sticky="w", pady=7)

        tk.Button(right, text="Refresh Counts", command=self.refresh_counts, height=2).pack(anchor="e", padx=24, pady=(24, 0))

    def refresh_counts(self):
        counts = table_counts()
        for table, var in self.count_vars.items():
            var.set(str(counts.get(table, 0)))

    def clear_exams(self):
        if not messagebox.askyesno("Clear Exam History", "Clear exam sessions, seat assignments, and attendance logs?"):
            return
        counts = clear_exam_history()
        self.refresh_counts()
        self.status_var.set("Exam history cleared. Student enrollment data was kept.")

    def reset_all(self):
        answer = messagebox.askyesno(
            "Reset All Data",
            "This will delete every student, course, face template, exam record, and saved face image. Continue?",
        )
        if not answer:
            return
        confirm = messagebox.askyesno("Final Confirmation", "Are you absolutely sure you want a blank database?")
        if not confirm:
            return
        reset_all_data()
        self.refresh_counts()
        self.status_var.set("All database data cleared. Ready for fresh enrollment.")


def main():
    app = AdminPanel()
    app.mainloop()


if __name__ == "__main__":
    main()

