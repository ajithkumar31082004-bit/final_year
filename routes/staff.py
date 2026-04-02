"""
Blissful Abodes - Staff Routes
Staff dashboard, room management, housekeeping, check-in/out
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
import html
import uuid
import json
from datetime import datetime
from functools import wraps
from models.database import get_db
from services.ai_chat_service import generate_ai_reply
from services.security import hash_password
from ml_models.openai_agent import openai_agent
from services.shift_scheduler import (
    get_today_shifts,
    get_staff_shift_today,
    get_shifts_for_date,
    assign_daily_shifts,
)

staff_bp = Blueprint("staff", __name__)


def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("user_role") not in ["staff", "manager", "admin", "superadmin"]:
            flash("Access denied. Staff privileges required.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated


def get_current_user():
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()
    return dict(user) if user else {}


def _get_staff_chat_history():
    history = session.get("staff_chat_history")
    if not isinstance(history, list):
        history = []
    return history


def _append_staff_chat_history(user_text, assistant_text):
    history = _get_staff_chat_history()
    history.append({"role": "user", "content": (user_text or "")[:600]})
    history.append({"role": "assistant", "content": (assistant_text or "")[:600]})
    session["staff_chat_history"] = history[-6:]


def _sanitize_reply(text):
    return html.escape(text or "").replace("\n", "<br/>")


def _build_staff_prompt(user, tasks, shift):
    task_lines = []
    for t in tasks:
        task_lines.append(
            f"{t.get('room_number','')} | {t.get('task_type','')} | {t.get('priority','')} | {t.get('status','')}"
        )
    task_summary = "\n".join(task_lines) if task_lines else "No assigned tasks."

    shift_text = (
        f"{shift.get('shift_type','')} {shift.get('start_time','')} - {shift.get('end_time','')}"
        if shift
        else "No shift scheduled today."
    )

    return (
        "You are the Staff Assistant for Blissful Abodes. "
        "You help staff understand their tasks and shifts, and give guidance on procedures. "
        "If asked to update task or room status, instruct them to use the Staff Dashboard buttons. "
        f"Staff: {user.get('first_name','')} {user.get('last_name','')} ({user.get('department','Staff')}). "
        f"Today's shift: {shift_text}. "
        f"Assigned tasks:\n{task_summary}"
    )


@staff_bp.route("/staff/dashboard")
@staff_required
def dashboard():
    user = get_current_user()
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Stats
    checkins_today = conn.execute(
        """SELECT COUNT(*) FROM bookings WHERE check_in = ? AND status = 'confirmed' """,
        (today,),
    ).fetchone()[0]
    checkouts_today = conn.execute(
        """SELECT COUNT(*) FROM bookings WHERE check_out = ? AND status = 'confirmed' """,
        (today,),
    ).fetchone()[0]
    occupied = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'occupied'"
    ).fetchone()[0]
    available = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'available'"
    ).fetchone()[0]
    cleaning = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'cleaning'"
    ).fetchone()[0]
    maintenance_rooms = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'maintenance'"
    ).fetchone()[0]
    reserved = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'reserved'"
    ).fetchone()[0]

    # Today's check-ins
    checkin_list = conn.execute(
        """SELECT b.*, u.first_name, u.last_name, u.phone, r.room_type
                                   FROM bookings b
                                   JOIN users u ON b.user_id = u.user_id
                                   JOIN rooms r ON b.room_id = r.room_id
                                   WHERE b.check_in = ? AND b.status = 'confirmed'
                                   ORDER BY b.check_in ASC""",
        (today,),
    ).fetchall()

    # Today's check-outs
    checkout_list = conn.execute(
        """SELECT b.*, u.first_name, u.last_name, u.phone, r.room_type
                                    FROM bookings b
                                    JOIN users u ON b.user_id = u.user_id
                                    JOIN rooms r ON b.room_id = r.room_id
                                    WHERE b.check_out = ? AND b.status = 'confirmed'
                                    ORDER BY b.check_out ASC""",
        (today,),
    ).fetchall()

    # All rooms for grid
    rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()

    # Housekeeping tasks
    tasks = conn.execute(
        """SELECT h.*, u.first_name as staff_name FROM housekeeping_tasks h
                            LEFT JOIN users u ON h.assigned_to = u.user_id
                            WHERE h.status != 'completed'
                            ORDER BY CASE h.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END, h.created_at DESC LIMIT 20"""
    ).fetchall()

    # Maintenance issues
    issues = conn.execute(
        """SELECT * FROM maintenance_issues 
                             WHERE status != 'resolved' ORDER BY priority DESC, created_at"""
    ).fetchall()

    # Service requests
    service_requests = conn.execute(
        """SELECT * FROM service_requests
           WHERE status != 'completed'
           ORDER BY created_at DESC"""
    ).fetchall()

    # Staff for assignment
    staff_list = conn.execute(
        "SELECT user_id, first_name, last_name FROM users WHERE role = 'staff' AND is_active = 1"
    ).fetchall()

    conn.close()

    rooms_by_floor = {}
    for r in rooms:
        rd = dict(r)
        fl = str(rd["floor"])
        if fl not in rooms_by_floor:
            rooms_by_floor[fl] = []
        rooms_by_floor[fl].append(rd)

    # Today's shift for the logged-in staff member
    my_shift = get_staff_shift_today(user["user_id"])

    return render_template(
        "staff/dashboard.html",
        user=user,
        my_shift=my_shift,
        stats={
            "checkins_today": checkins_today,
            "checkouts_today": checkouts_today,
            "occupied": occupied,
            "available": available,
            "cleaning": cleaning,
            "maintenance": maintenance_rooms,
            "reserved": reserved,
        },
        checkin_list=[dict(b) for b in checkin_list],
        checkout_list=[dict(b) for b in checkout_list],
        rooms_by_floor=rooms_by_floor,
        tasks=[dict(t) for t in tasks],
        issues=[dict(i) for i in issues],
        service_requests=[dict(s) for s in service_requests],
        staff_list=[dict(s) for s in staff_list],
    )


@staff_bp.route("/api/rooms/availability")
def room_availability():
    """Real-time room availability API"""
    conn = get_db()
    rooms = conn.execute(
        "SELECT room_number, status, room_type, floor FROM rooms ORDER BY room_number"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rooms])


@staff_bp.route("/api/room/update-status", methods=["POST"])
@staff_required
def update_room_status():
    room_number = request.json.get("room_number")
    new_status = request.json.get("status")

    valid_statuses = [
        "available",
        "occupied",
        "cleaning",
        "maintenance",
        "out_of_service",
        "reserved",
    ]
    if new_status not in valid_statuses:
        return jsonify({"success": False, "message": "Invalid status"})

    conn = get_db()
    conn.execute(
        "UPDATE rooms SET status = ? WHERE room_number = ?", (new_status, room_number)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "room": room_number, "status": new_status})


@staff_bp.route("/api/housekeeping/task", methods=["POST"])
@staff_required
def create_task():
    data = request.json
    task_id = str(uuid.uuid4())
    conn = get_db()

    room = conn.execute(
        "SELECT * FROM rooms WHERE room_number = ?", (data.get("room_number"),)
    ).fetchone()

    conn.execute(
        """INSERT INTO housekeeping_tasks
        (task_id, room_id, room_number, assigned_to, task_type, priority, status, notes, created_by)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (
            task_id,
            room["room_id"] if room else None,
            data.get("room_number"),
            data.get("assigned_to"),
            data.get("task_type", "cleaning"),
            data.get("priority", "normal"),
            data.get("notes", ""),
            session["user_id"],
        ),
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "task_id": task_id})


@staff_bp.route("/api/housekeeping/task/<task_id>/status", methods=["POST"])
@staff_required
def update_task_status(task_id):
    status = request.json.get("status")
    conn = get_db()
    update_data = {"status": status}
    if status == "completed":
        conn.execute(
            "UPDATE housekeeping_tasks SET status = ?, completed_at = ? WHERE task_id = ?",
            (status, datetime.now().isoformat(), task_id),
        )
    else:
        conn.execute(
            "UPDATE housekeeping_tasks SET status = ? WHERE task_id = ?",
            (status, task_id),
        )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@staff_bp.route("/api/service-request/<request_id>/status", methods=["POST"])
@staff_required
def update_service_request_status(request_id):
    status = request.json.get("status", "pending")
    if status not in ["pending", "in_progress", "completed", "cancelled"]:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    conn = get_db()
    req = conn.execute(
        "SELECT * FROM service_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    if not req:
        conn.close()
        return jsonify({"success": False, "message": "Request not found"}), 404
    req = dict(req)
    conn.execute(
        "UPDATE service_requests SET status = ?, updated_at = ? WHERE request_id = ?",
        (status, datetime.now().isoformat(), request_id),
    )
    if status == "completed":
        room_label = req.get("room_number") or "your room"
        is_special = req.get("request_type") == "special_request"
        title = "Special Request Completed" if is_special else "Service Request Completed"
        message = f"Your request for {room_label} has been completed."
        conn.execute(
            """INSERT INTO notifications
            (notification_id, user_id, title, message, notification_type, action_url)
            VALUES (?, ?, ?, ?, 'success', ?)""",
            (
                str(uuid.uuid4()),
                req.get("user_id"),
                title,
                message,
                "/guest/bookings",
            ),
        )

        managers = conn.execute(
            """SELECT user_id, role FROM users
               WHERE role IN ('manager','admin','superadmin')
               AND is_active = 1"""
        ).fetchall()
        for m in managers:
            role = m["role"]
            action_url = "/manager/dashboard" if role == "manager" else "/admin/bookings"
            conn.execute(
                """INSERT INTO notifications
                (notification_id, user_id, title, message, notification_type, action_url)
                VALUES (?, ?, ?, ?, 'info', ?)""",
                (
                    str(uuid.uuid4()),
                    m["user_id"],
                    title,
                    f"{title} for {room_label}.",
                    action_url,
                ),
            )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@staff_bp.route("/api/checkin/<booking_id>", methods=["POST"])
@staff_required
def process_checkin(booking_id):
    conn = get_db()
    conn.execute(
        "UPDATE bookings SET checked_in_at = ?, status = 'confirmed' WHERE booking_id = ?",
        (datetime.now().isoformat(), booking_id),
    )
    conn.execute(
        "UPDATE rooms SET status = 'occupied' WHERE room_id = (SELECT room_id FROM bookings WHERE booking_id = ?)",
        (booking_id,),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Check-in processed successfully"})


@staff_bp.route("/api/checkout/<booking_id>", methods=["POST"])
@staff_required
def process_checkout(booking_id):
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
    ).fetchone()
    if not booking:
        conn.close()
        return jsonify({"success": False, "message": "Booking not found"})

    booking = dict(booking)
    conn.execute(
        "UPDATE bookings SET checked_out_at = ?, status = 'completed', updated_at = ? WHERE booking_id = ?",
        (datetime.now().isoformat(), datetime.now().isoformat(), booking_id),
    )

    # Set room to cleaning
    conn.execute(
        "UPDATE rooms SET status = 'cleaning' WHERE room_id = ?", (booking["room_id"],)
    )

    # Auto-create cleaning task
    task_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO housekeeping_tasks 
        (task_id, room_id, room_number, task_type, priority, status, notes, created_by)
        VALUES (?, ?, ?, 'cleaning', 'high', 'pending', 'Post check-out cleaning required', ?)""",
        (task_id, booking["room_id"], booking["room_number"], session["user_id"]),
    )

    # Award loyalty points if not already done
    pts = booking.get("loyalty_points_earned", 0)
    if pts > 0:
        conn.execute(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id = ?",
            (pts, booking["user_id"]),
        )

    conn.commit()
    conn.close()

    return jsonify(
        {"success": True, "message": "Check-out processed. Room marked for cleaning."}
    )


@staff_bp.route("/api/maintenance/report", methods=["POST"])
@staff_required
def report_maintenance():
    data = request.json
    issue_id = str(uuid.uuid4())
    conn = get_db()

    conn.execute(
        """INSERT INTO maintenance_issues
        (issue_id, room_number, reported_by, issue_type, description, priority, status)
        VALUES (?, ?, ?, ?, ?, ?, 'open')""",
        (
            issue_id,
            data.get("room_number"),
            session["user_id"],
            data.get("issue_type"),
            data.get("description"),
            data.get("priority", "normal"),
        ),
    )

    # Update room status if needed
    if data.get("block_room"):
        conn.execute(
            "UPDATE rooms SET status = 'maintenance' WHERE room_number = ?",
            (data.get("room_number"),),
        )

    conn.commit()
    conn.close()
    return jsonify({"success": True, "issue_id": issue_id})


@staff_bp.route("/staff/walkin-booking", methods=["GET", "POST"])
@staff_required
def walkin_booking():
    """Walk-in booking form for staff"""
    conn = get_db()
    available_rooms = conn.execute(
        "SELECT * FROM rooms WHERE status = 'available' ORDER BY room_type, room_number"
    ).fetchall()
    conn.close()

    if request.method == "POST":
        # Process walk-in booking
        guest_name = request.form.get("guest_name")
        phone = request.form.get("phone")
        room_id = request.form.get("room_id")
        check_in = request.form.get("check_in")
        check_out = request.form.get("check_out")
        payment_method = request.form.get("payment_method", "cash")

        # Create temporary guest account
        guest_email = f"walkin_{uuid.uuid4().hex[:8]}@blissful.temp"
        pwd_hash = hash_password("TempPass123")
        user_id = f"user_{uuid.uuid4().hex[:12]}"

        name_parts = guest_name.split(" ", 1)
        conn = get_db()
        conn.execute(
            """INSERT INTO users (user_id, email, phone, password_hash, first_name, last_name, role)
                       VALUES (?, ?, ?, ?, ?, ?, 'guest')""",
            (
                user_id,
                guest_email,
                phone,
                pwd_hash,
                name_parts[0],
                name_parts[1] if len(name_parts) > 1 else "",
            ),
        )

        room = conn.execute(
            "SELECT * FROM rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
        ci = datetime.strptime(check_in, "%Y-%m-%d")
        co = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (co - ci).days
        base = room["current_price"] * nights
        gst = base * 0.18
        total = base + gst

        booking_id = (
            f"WI{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        )
        conn.execute(
            """INSERT INTO bookings 
            (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
             base_amount, gst_amount, total_amount, status, payment_status, payment_method, checked_in_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'confirmed', 'paid', ?, ?)""",
            (
                booking_id,
                user_id,
                room_id,
                room["room_number"],
                check_in,
                check_out,
                base,
                gst,
                total,
                payment_method,
                datetime.now().isoformat(),
            ),
        )

        conn.execute(
            "UPDATE rooms SET status = 'occupied' WHERE room_id = ?", (room_id,)
        )
        conn.commit()
        conn.close()

        flash(f"Walk-in booking created! ID: {booking_id}", "success")
        return redirect(url_for("staff.dashboard"))

    return render_template(
        "staff/walkin.html", rooms=[dict(r) for r in available_rooms]
    )


@staff_bp.route("/api/staff/chatbot/message", methods=["POST"])
@staff_required
def staff_chatbot_message():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "reply": "Please enter a message."}), 400

    user = get_current_user()
    conn = get_db()
    
    # Build AI Context
    today = datetime.now().strftime("%Y-%m-%d")
    pending = conn.execute("SELECT COUNT(*) FROM housekeeping_tasks WHERE assigned_to = ? AND status = 'pending'", (user.get("user_id"),)).fetchone()[0]
    urgent = conn.execute("SELECT COUNT(*) FROM housekeeping_tasks WHERE assigned_to = ? AND priority = 'urgent' AND status = 'pending'", (user.get("user_id"),)).fetchone()[0]
    checkins = conn.execute("SELECT COUNT(*) FROM bookings WHERE check_in = ? AND status = 'confirmed'", (today,)).fetchone()[0]
    cleaning_rooms = conn.execute("SELECT COUNT(*) FROM rooms WHERE status = 'cleaning'").fetchone()[0]
    
    next_task_row = conn.execute(
        "SELECT room_number, task_type FROM housekeeping_tasks WHERE assigned_to = ? AND status = 'pending' ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END LIMIT 1", 
        (user.get("user_id"),)
    ).fetchone()
    conn.close()

    context = {
        "pending_tasks": pending,
        "urgent_tasks": urgent,
        "checkins_today": checkins,
        "cleaning_rooms": cleaning_rooms,
        "next_task": f"{next_task_row['task_type']} in Room {next_task_row['room_number']}" if next_task_row else "None"
    }

    reply = openai_agent.handle_staff_message(message, context)
    return jsonify({"ok": True, "reply": reply})


# ── Shift Scheduling APIs ──────────────────────────────────────────────────────

@staff_bp.route("/api/shifts/today", methods=["GET"])
@staff_required
def api_shifts_today():
    """Return all staff shifts scheduled for today."""
    shifts = get_today_shifts()
    return jsonify({"date": shifts[0]["date"] if shifts else None, "shifts": shifts})


@staff_bp.route("/api/shifts/date/<target_date>", methods=["GET"])
@staff_required
def api_shifts_for_date(target_date):
    """Return all staff shifts for a specific date (YYYY-MM-DD)."""
    shifts = get_shifts_for_date(target_date)
    return jsonify({"date": target_date, "shifts": shifts})


@staff_bp.route("/api/shifts/my", methods=["GET"])
@staff_required
def api_my_shift():
    """Return the logged-in staff member's shift for today."""
    my_shift = get_staff_shift_today(session["user_id"])
    return jsonify(my_shift)


@staff_bp.route("/api/shifts/generate", methods=["POST"])
@staff_required
def api_generate_shifts():
    """
    Manager/Admin endpoint — manually trigger shift generation for today.
    Useful to regenerate after adding new staff members.
    """
    if session.get("user_role") not in ["manager", "admin", "superadmin"]:
        return jsonify({"success": False, "message": "Manager access required."}), 403
    try:
        result = assign_daily_shifts()
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@staff_bp.route("/api/shifts/<shift_id>/status", methods=["POST"])
@staff_required
def api_update_shift_status(shift_id):
    """Staff marks their shift as 'active' (clocked in) or 'completed' (clocked out)."""
    new_status = request.json.get("status")
    if new_status not in ["scheduled", "active", "completed", "absent"]:
        return jsonify({"success": False, "message": "Invalid status."}), 400

    conn = get_db()
    shift = conn.execute(
        "SELECT * FROM staff_shifts WHERE shift_id = ?", (shift_id,)
    ).fetchone()

    if not shift:
        conn.close()
        return jsonify({"success": False, "message": "Shift not found."}), 404

    shift = dict(shift)
    # Staff can only update their own shift; managers can update any
    if (shift["staff_id"] != session["user_id"] and
            session.get("user_role") not in ["manager", "admin", "superadmin"]):
        conn.close()
        return jsonify({"success": False, "message": "Unauthorized."}), 403

    conn.execute(
        "UPDATE staff_shifts SET status = ? WHERE shift_id = ?",
        (new_status, shift_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "shift_id": shift_id, "status": new_status})
