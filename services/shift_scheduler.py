"""
Blissful Abodes - Automatic Daily Staff Shift Scheduler
========================================================
Runs every day at 00:05 AM (via APScheduler in app.py).
Distributes Morning / Evening / Night shifts across all active staff
using a fair round-robin rotation, weighted by today's occupancy.

Shift windows:
  Morning  06:00 – 14:00
  Evening  14:00 – 22:00
  Night    22:00 – 06:00

Logic:
  1. Fetch all active staff (role='staff').
  2. Skip staff who already have a shift for today (idempotent).
  3. Count today's check-ins to gauge demand (high occupancy → more
     staff on Morning/Evening, fewer on Night).
  4. Assign shifts in round-robin order, cycling through the three types.
  5. Insert rows into `staff_shifts` and push an in-app notification
     to each staff member.
  6. Send an SNS summary alert to the manager/admin team.
"""

import uuid
from datetime import datetime, date
from typing import List, Dict, Any


# ── Shift definitions ──────────────────────────────────────────────────────────
SHIFTS = [
    {"type": "Morning", "start": "06:00", "end": "14:00"},
    {"type": "Evening", "start": "14:00", "end": "22:00"},
    {"type": "Night",   "start": "22:00", "end": "06:00"},
]

# Departments and their preferred shift priority
DEPT_PRIORITY = {
    "Housekeeping": ["Morning", "Evening", "Night"],
    "Front Desk":   ["Morning", "Evening", "Night"],
    "F&B":          ["Morning", "Evening", "Night"],
    "Security":     ["Night", "Morning", "Evening"],
    "Maintenance":  ["Morning", "Evening", "Night"],
}


def _shift_by_type(shift_type: str) -> Dict[str, str]:
    """Return shift dict for a given type string."""
    return next((s for s in SHIFTS if s["type"] == shift_type), SHIFTS[0])


def assign_daily_shifts(app_context=None) -> Dict[str, Any]:
    """
    Main entry point called by the APScheduler daily job.
    Assigns shifts for today to all active staff who don't already have one.

    Returns a summary dict for logging.
    """
    from models.database import get_db

    today = date.today().isoformat()
    now   = datetime.now().isoformat()

    conn = get_db()

    # 1. Get all active staff
    staff_rows = conn.execute(
        """SELECT user_id, first_name, last_name, department
           FROM users
           WHERE role = 'staff' AND is_active = 1
           ORDER BY department, first_name"""
    ).fetchall()
    staff_list: List[Dict] = [dict(s) for s in staff_rows]

    if not staff_list:
        conn.close()
        print("[SHIFT] No active staff found — skipping shift assignment.")
        return {"assigned": 0, "skipped": 0, "date": today}

    # 2. Find staff who already have a shift today (idempotent)
    existing_rows = conn.execute(
        "SELECT staff_id FROM staff_shifts WHERE date = ?", (today,)
    ).fetchall()
    already_scheduled = {r["staff_id"] for r in existing_rows}

    # 3. Check today's occupancy to determine shift weighting
    checkins_today = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE check_in = ? AND status IN ('confirmed','pending')",
        (today,)
    ).fetchone()[0]
    total_rooms = conn.execute("SELECT COUNT(*) FROM rooms WHERE is_active = 1").fetchone()[0]
    occupancy_pct = round(checkins_today / max(total_rooms, 1) * 100)

    # High occupancy (>50%) → weight shifts Morning-heavy, low → pure round-robin
    if occupancy_pct >= 50:
        # Pattern: M, M, E, M, E, N  (more morning/evening coverage)
        shift_pattern = ["Morning", "Morning", "Evening", "Morning", "Evening", "Night"]
    else:
        # Standard round-robin
        shift_pattern = ["Morning", "Evening", "Night"]

    # 4. Assign shifts
    assigned_count = 0
    skipped_count  = 0
    notifications  = []
    shift_index    = 0

    for staff in staff_list:
        uid = staff["user_id"]

        if uid in already_scheduled:
            skipped_count += 1
            continue

        # Department-aware shift selection
        dept   = staff.get("department") or "Front Desk"
        dept_pref = DEPT_PRIORITY.get(dept, ["Morning", "Evening", "Night"])

        # Pick from pattern, but respect department if Security (always Night-first)
        if dept == "Security":
            raw_type = dept_pref[shift_index % len(dept_pref)]
        else:
            raw_type = shift_pattern[shift_index % len(shift_pattern)]

        shift_info = _shift_by_type(raw_type)
        shift_id   = f"SH{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"

        conn.execute(
            """INSERT INTO staff_shifts
               (shift_id, staff_id, date, shift_type, start_time, end_time, status, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)""",
            (
                shift_id,
                uid,
                today,
                shift_info["type"],
                shift_info["start"],
                shift_info["end"],
                f"Auto-assigned by Daily Shift Scheduler. Occupancy: {occupancy_pct}%",
                now,
            )
        )

        # 5. In-app notification to each staff member
        notif_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO notifications
               (notification_id, user_id, title, message, notification_type, action_url, created_at)
               VALUES (?, ?, ?, ?, 'info', ?, ?)""",
            (
                notif_id,
                uid,
                f"📅 Your {shift_info['type']} Shift — {today}",
                f"Hi {staff['first_name']}! Your shift for today is {shift_info['type']} "
                f"({shift_info['start']} – {shift_info['end']}). Please report on time.",
                "/staff/dashboard",
                now,
            )
        )

        notifications.append({
            "staff": f"{staff['first_name']} {staff['last_name']}",
            "shift": shift_info["type"],
            "start": shift_info["start"],
            "end":   shift_info["end"],
        })

        shift_index    += 1
        assigned_count += 1

    conn.commit()

    # 6. Notify manager/admin via SNS (best-effort)
    _notify_managers(conn, today, assigned_count, occupancy_pct, notifications, now)

    conn.close()

    print(
        f"[SHIFT] {today} — Assigned: {assigned_count} | "
        f"Skipped: {skipped_count} | Occupancy: {occupancy_pct}%"
    )
    return {
        "assigned":     assigned_count,
        "skipped":      skipped_count,
        "date":         today,
        "occupancy_pct": occupancy_pct,
        "shifts":       notifications,
    }


def _notify_managers(conn, today: str, assigned: int, occupancy: int,
                     shifts: List[Dict], now: str):
    """Push an in-app summary notification to all managers/admins."""
    try:
        managers = conn.execute(
            "SELECT user_id FROM users WHERE role IN ('manager','admin','superadmin') AND is_active = 1"
        ).fetchall()

        shift_lines = "\n".join(
            f"  • {s['staff']}: {s['shift']} ({s['start']}–{s['end']})"
            for s in shifts[:10]   # cap at 10 lines
        )
        if len(shifts) > 10:
            shift_lines += f"\n  ... and {len(shifts) - 10} more"

        msg = (
            f"{assigned} staff shift(s) auto-assigned for {today}.\n"
            f"Hotel occupancy: {occupancy}%\n\n"
            f"{shift_lines}"
        )

        for mgr in managers:
            conn.execute(
                """INSERT INTO notifications
                   (notification_id, user_id, title, message, notification_type, action_url, created_at)
                   VALUES (?, ?, ?, ?, 'info', ?, ?)""",
                (
                    str(uuid.uuid4()),
                    mgr["user_id"],
                    f"📋 Daily Shift Schedule Generated — {today}",
                    msg,
                    "/manager/dashboard",
                    now,
                )
            )

        # Optional: SNS push (only if configured)
        try:
            from services.sns_service import is_configured, _get_sns
            import os
            if is_configured():
                topic = os.environ.get("SNS_ADMIN_TOPIC_ARN", "")
                if topic:
                    _get_sns().publish(
                        TopicArn=topic,
                        Subject=f"[Blissful Abodes] Staff Shifts Scheduled — {today}",
                        Message=msg,
                    )
        except Exception:
            pass  # SNS is optional

    except Exception as e:
        print(f"[SHIFT] Manager notification failed: {e}")


# ── Manual re-schedule API helper ─────────────────────────────────────────────

def get_today_shifts() -> List[Dict]:
    """Return all shifts for today (used by dashboard API)."""
    from models.database import get_db
    today = date.today().isoformat()
    conn  = get_db()
    rows  = conn.execute(
        """SELECT ss.*, u.first_name, u.last_name, u.department
           FROM staff_shifts ss
           JOIN users u ON ss.staff_id = u.user_id
           WHERE ss.date = ?
           ORDER BY ss.shift_type, u.first_name""",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_shifts_for_date(target_date: str) -> List[Dict]:
    """Return all shifts for a specific date (YYYY-MM-DD)."""
    from models.database import get_db
    conn = get_db()
    rows = conn.execute(
        """SELECT ss.*, u.first_name, u.last_name, u.department
           FROM staff_shifts ss
           JOIN users u ON ss.staff_id = u.user_id
           WHERE ss.date = ?
           ORDER BY ss.shift_type, u.first_name""",
        (target_date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_staff_shift_today(staff_id: str) -> Dict:
    """Return today's shift for a specific staff member (or empty dict)."""
    from models.database import get_db
    today = date.today().isoformat()
    conn  = get_db()
    row = conn.execute(
        "SELECT * FROM staff_shifts WHERE staff_id = ? AND date = ?",
        (staff_id, today)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}
