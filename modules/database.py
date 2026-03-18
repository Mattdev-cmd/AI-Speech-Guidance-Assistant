"""
Education Management Database Module.

Handles all database operations for user management,
class scheduling, and attendance monitoring.
Uses SQLite for lightweight, file-based storage.
"""

import logging
import os
import sqlite3
import threading

from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

_db_instance = None
_db_lock = threading.Lock()


def get_db(db_path=None):
    """Get or create the database singleton."""
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                path = db_path or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "education.db",
                )
                _db_instance = Database(path)
    return _db_instance


class Database:
    """Thread-safe SQLite database for education management."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_tables()

    def _conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA foreign_keys = ON")
        return self._local.conn

    def _init_tables(self):
        conn = self._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'teacher'
                    CHECK(role IN ('admin', 'teacher', 'student')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS classrooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                capacity INTEGER DEFAULT 30
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                classroom_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL
                    CHECK(day_of_week IN (
                        'Monday','Tuesday','Wednesday','Thursday',
                        'Friday','Saturday','Sunday')),
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                UNIQUE(student_id, subject_id)
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'absent'
                    CHECK(status IN ('present', 'late', 'absent')),
                marked_by INTEGER,
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (marked_by) REFERENCES users(id),
                UNIQUE(schedule_id, student_id, date)
            );
        """
        )
        conn.commit()
        self._ensure_admin()
        logger.info("Database initialized at %s", self.db_path)

    def _ensure_admin(self):
        conn = self._conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        if row["cnt"] == 0:
            self.create_user("admin", "admin123", "Administrator", "admin")
            logger.info(
                "Default admin created (username: admin, password: admin123)"
            )

    # ── Users ──────────────────────────────

    def create_user(self, username, password, full_name, role="teacher"):
        conn = self._conn()
        pw_hash = generate_password_hash(password)
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role) "
                "VALUES (?, ?, ?, ?)",
                (username, pw_hash, full_name, role),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username, password):
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            return dict(row)
        return None

    def get_user_by_id(self, user_id):
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_users(self, role=None):
        conn = self._conn()
        if role:
            rows = conn.execute(
                "SELECT * FROM users WHERE role = ? ORDER BY full_name",
                (role,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY role, full_name"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_user(self, user_id):
        conn = self._conn()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    # ── Classrooms ─────────────────────────

    def create_classroom(self, name, capacity=30):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO classrooms (name, capacity) VALUES (?, ?)",
                (name, capacity),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_classrooms(self):
        conn = self._conn()
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM classrooms ORDER BY name"
            ).fetchall()
        ]

    def delete_classroom(self, classroom_id):
        conn = self._conn()
        conn.execute("DELETE FROM classrooms WHERE id = ?", (classroom_id,))
        conn.commit()

    # ── Subjects ───────────────────────────

    def create_subject(self, name, code):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO subjects (name, code) VALUES (?, ?)", (name, code)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_subjects(self):
        conn = self._conn()
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM subjects ORDER BY name"
            ).fetchall()
        ]

    def delete_subject(self, subject_id):
        conn = self._conn()
        conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        conn.commit()

    # ── Schedules ──────────────────────────

    def check_schedule_conflict(
        self, day_of_week, start_time, end_time, teacher_id, classroom_id,
        exclude_id=None,
    ):
        """Return list of conflict descriptions, empty if none."""
        conn = self._conn()
        conflicts = []

        # Teacher conflict
        q = (
            "SELECT s.*, u.full_name AS teacher_name, sub.name AS subject_name "
            "FROM schedules s "
            "JOIN users u ON s.teacher_id = u.id "
            "JOIN subjects sub ON s.subject_id = sub.id "
            "WHERE s.day_of_week = ? AND s.teacher_id = ? "
            "AND s.start_time < ? AND s.end_time > ?"
        )
        params = [day_of_week, teacher_id, end_time, start_time]
        if exclude_id:
            q += " AND s.id != ?"
            params.append(exclude_id)
        for row in conn.execute(q, params).fetchall():
            conflicts.append(
                f"Teacher '{row['teacher_name']}' already has "
                f"'{row['subject_name']}' on {day_of_week} "
                f"{row['start_time']}\u2013{row['end_time']}"
            )

        # Classroom conflict
        q = (
            "SELECT s.*, c.name AS classroom_name, sub.name AS subject_name "
            "FROM schedules s "
            "JOIN classrooms c ON s.classroom_id = c.id "
            "JOIN subjects sub ON s.subject_id = sub.id "
            "WHERE s.day_of_week = ? AND s.classroom_id = ? "
            "AND s.start_time < ? AND s.end_time > ?"
        )
        params = [day_of_week, classroom_id, end_time, start_time]
        if exclude_id:
            q += " AND s.id != ?"
            params.append(exclude_id)
        for row in conn.execute(q, params).fetchall():
            conflicts.append(
                f"Room '{row['classroom_name']}' already used for "
                f"'{row['subject_name']}' on {day_of_week} "
                f"{row['start_time']}\u2013{row['end_time']}"
            )

        return conflicts

    def create_schedule(
        self, subject_id, teacher_id, classroom_id,
        day_of_week, start_time, end_time,
    ):
        conflicts = self.check_schedule_conflict(
            day_of_week, start_time, end_time, teacher_id, classroom_id
        )
        if conflicts:
            return False, conflicts

        conn = self._conn()
        conn.execute(
            "INSERT INTO schedules "
            "(subject_id, teacher_id, classroom_id, day_of_week, "
            "start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)",
            (subject_id, teacher_id, classroom_id,
             day_of_week, start_time, end_time),
        )
        conn.commit()
        return True, []

    def get_schedules(self, day_of_week=None, teacher_id=None):
        conn = self._conn()
        q = (
            "SELECT s.*, "
            "sub.name AS subject_name, sub.code AS subject_code, "
            "u.full_name AS teacher_name, "
            "c.name AS classroom_name "
            "FROM schedules s "
            "JOIN subjects sub ON s.subject_id = sub.id "
            "JOIN users u ON s.teacher_id = u.id "
            "JOIN classrooms c ON s.classroom_id = c.id WHERE 1=1"
        )
        params = []
        if day_of_week:
            q += " AND s.day_of_week = ?"
            params.append(day_of_week)
        if teacher_id:
            q += " AND s.teacher_id = ?"
            params.append(teacher_id)
        q += (
            " ORDER BY CASE s.day_of_week "
            "WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 "
            "WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 "
            "WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 "
            "WHEN 'Sunday' THEN 7 END, s.start_time"
        )
        return [dict(r) for r in conn.execute(q, params).fetchall()]

    def delete_schedule(self, schedule_id):
        conn = self._conn()
        conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        conn.commit()

    # ── Enrollments ────────────────────────

    def enroll_student(self, student_id, subject_id):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO enrollments (student_id, subject_id) "
                "VALUES (?, ?)",
                (student_id, subject_id),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_enrolled_students(self, subject_id):
        conn = self._conn()
        rows = conn.execute(
            "SELECT u.* FROM users u "
            "JOIN enrollments e ON u.id = e.student_id "
            "WHERE e.subject_id = ? ORDER BY u.full_name",
            (subject_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_student_enrollments(self, student_id):
        conn = self._conn()
        rows = conn.execute(
            "SELECT sub.* FROM subjects sub "
            "JOIN enrollments e ON sub.id = e.subject_id "
            "WHERE e.student_id = ? ORDER BY sub.name",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def set_student_enrollments(self, student_id, subject_ids):
        """Replace all enrollments for a student."""
        conn = self._conn()
        conn.execute(
            "DELETE FROM enrollments WHERE student_id = ?", (student_id,)
        )
        for sid in subject_ids:
            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, subject_id) "
                "VALUES (?, ?)",
                (student_id, sid),
            )
        conn.commit()

    def unenroll_student(self, student_id, subject_id):
        conn = self._conn()
        conn.execute(
            "DELETE FROM enrollments WHERE student_id = ? AND subject_id = ?",
            (student_id, subject_id),
        )
        conn.commit()

    # ── Attendance ─────────────────────────

    def mark_attendance(self, schedule_id, student_id, date, status, marked_by):
        conn = self._conn()
        conn.execute(
            "INSERT INTO attendance "
            "(schedule_id, student_id, date, status, marked_by) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(schedule_id, student_id, date) "
            "DO UPDATE SET status=excluded.status, "
            "marked_by=excluded.marked_by, marked_at=CURRENT_TIMESTAMP",
            (schedule_id, student_id, date, status, marked_by),
        )
        conn.commit()

    def get_attendance(self, schedule_id, date):
        conn = self._conn()
        schedule = conn.execute(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        if not schedule:
            return []

        rows = conn.execute(
            "SELECT u.id AS student_id, u.full_name, "
            "COALESCE(a.status, 'absent') AS status, a.marked_at "
            "FROM users u "
            "JOIN enrollments e ON u.id = e.student_id "
            "LEFT JOIN attendance a ON a.student_id = u.id "
            "  AND a.schedule_id = ? AND a.date = ? "
            "WHERE e.subject_id = ? ORDER BY u.full_name",
            (schedule_id, date, schedule["subject_id"]),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_attendance_summary(self, date_from=None, date_to=None):
        conn = self._conn()
        q = "SELECT status, COUNT(*) AS count FROM attendance WHERE 1=1"
        params = []
        if date_from:
            q += " AND date >= ?"
            params.append(date_from)
        if date_to:
            q += " AND date <= ?"
            params.append(date_to)
        q += " GROUP BY status"
        return {
            row["status"]: row["count"]
            for row in conn.execute(q, params).fetchall()
        }

    # ── Dashboard Stats ────────────────────

    def get_dashboard_stats(self):
        conn = self._conn()
        s = {}
        s["total_students"] = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role='student'"
        ).fetchone()["c"]
        s["total_teachers"] = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role='teacher'"
        ).fetchone()["c"]
        s["total_subjects"] = conn.execute(
            "SELECT COUNT(*) AS c FROM subjects"
        ).fetchone()["c"]
        s["total_classrooms"] = conn.execute(
            "SELECT COUNT(*) AS c FROM classrooms"
        ).fetchone()["c"]
        s["total_schedules"] = conn.execute(
            "SELECT COUNT(*) AS c FROM schedules"
        ).fetchone()["c"]

        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        summary = self.get_attendance_summary(date_from=today, date_to=today)
        s["today_present"] = summary.get("present", 0)
        s["today_late"] = summary.get("late", 0)
        s["today_absent"] = summary.get("absent", 0)
        return s
