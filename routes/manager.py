"""
Blissful Abodes - Manager Routes
Department management, shifts, inventory, team oversight
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
import uuid, json
from datetime import datetime, timedelta
from functools import wraps
from models.database import get_db
from ml_models.models import get_demand_model, get_pricing_engine
from ml_models.openai_agent import openai_agent

manager_bp = Blueprint("manager", __name__)


def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session or session.get("user_role") not in [
            "manager",
            "admin",
            "superadmin",
        ]:
            flash("Manager access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


def get_current_user():
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()
    return dict(user) if user else {}


@manager_bp.route("/manager/dashboard")
@manager_required
def dashboard():
    user = get_current_user()
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    this_month = datetime.now().strftime("%Y-%m")

    # KPIs
    today_rev = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) FROM bookings 
                                WHERE date(created_at) = ? AND payment_status = 'paid' """,
        (today,),
    ).fetchone()[0]

    total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    occupied = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
    ).fetchone()[0]
    occupancy = round(occupied / max(total_rooms, 1) * 100, 1)

    staff_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'staff' AND is_active = 1"
    ).fetchone()[0]

    avg_rating = conn.execute(
        "SELECT COALESCE(AVG(overall_rating), 0) FROM reviews"
    ).fetchone()[0]

    pending_tasks = conn.execute(
        "SELECT COUNT(*) FROM housekeeping_tasks WHERE status = 'pending'"
    ).fetchone()[0]
    completed_tasks = conn.execute(
        "SELECT COUNT(*) FROM housekeeping_tasks WHERE status = 'completed' AND date(created_at) = ?",
        (today,),
    ).fetchone()[0]

    # Team management
    team = conn.execute(
        """SELECT u.*, 
                           COUNT(h.task_id) as total_tasks,
                           COUNT(CASE WHEN h.status = 'completed' THEN 1 END) as done_tasks
                           FROM users u LEFT JOIN housekeeping_tasks h ON u.user_id = h.assigned_to
                           WHERE u.role = 'staff' AND u.is_active = 1
                           GROUP BY u.user_id"""
    ).fetchall()

    # Today's shifts
    shifts = conn.execute(
        """SELECT s.*, u.first_name, u.last_name FROM staff_shifts s
                             JOIN users u ON s.staff_id = u.user_id
                             WHERE s.date = ? ORDER BY s.shift_type""",
        (today,),
    ).fetchall()

    # Recent feedback
    recent_reviews = conn.execute(
        """SELECT rv.*, u.first_name, u.last_name FROM reviews rv
                                     JOIN users u ON rv.user_id = u.user_id
                                     ORDER BY rv.created_at DESC LIMIT 10"""
    ).fetchall()

    # Recent bookings
    bookings = conn.execute(
        """SELECT b.*, u.first_name, u.last_name, r.room_type
           FROM bookings b
           JOIN users u ON b.user_id = u.user_id
           JOIN rooms r ON b.room_id = r.room_id
           ORDER BY b.created_at DESC
           LIMIT 20"""
    ).fetchall()

    today_bookings = conn.execute(
        """SELECT b.*, u.first_name, u.last_name, r.room_type
           FROM bookings b
           JOIN users u ON b.user_id = u.user_id
           JOIN rooms r ON b.room_id = r.room_id
           WHERE b.check_in = ? OR b.check_out = ?
           ORDER BY b.check_in ASC""",
        (today, today),
    ).fetchall()

    # Rooms for management
    rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()

    # Low reviews
    low_reviews = [r for r in recent_reviews if r["overall_rating"] < 3]

    # Inventory
    inventory = conn.execute("SELECT * FROM inventory ORDER BY name").fetchall()
    low_stock = [i for i in inventory if i["stock_count"] <= i["reorder_level"]]

    # Open issues
    issues = conn.execute(
        """SELECT * FROM maintenance_issues WHERE status = 'open' 
                             ORDER BY priority DESC, created_at"""
    ).fetchall()


    # Inventory
    inventory = conn.execute("SELECT * FROM inventory ORDER BY name").fetchall()
    low_stock = [i for i in inventory if i["stock_count"] <= i["reorder_level"]]

    # Open issues
    issues = conn.execute(
        """SELECT * FROM maintenance_issues WHERE status = 'open' 
                             ORDER BY priority DESC, created_at"""
    ).fetchall()

    conn.close()

    demand_model = get_demand_model()
    demand_forecast = demand_model.predict_next_30_days()
    next_7_avg = demand_model.get_next_7_days_avg()

    pricing = get_pricing_engine()
    prices = pricing.get_all_current_prices(occupancy)

    # AI Smart Control Metrics
    conn = get_db()
    high_fraud = conn.execute("SELECT COUNT(*) FROM bookings WHERE fraud_score >= 35 OR is_flagged = 1").fetchone()[0]
    cancel_risk = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'cancelled'").fetchone()[0]
    safe_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE fraud_score < 20").fetchone()[0]

    # Smart Fraud Control Panel Data
    flagged = conn.execute('''SELECT b.*, u.first_name, u.last_name FROM bookings b 
                              JOIN users u ON b.user_id = u.user_id 
                              WHERE b.is_flagged = 1 OR b.fraud_score > 30 
                              ORDER BY b.fraud_score DESC''').fetchall()
    
    flagged_bookings = []
    for f in flagged:
        fd = dict(f)
        try:
            flags = json.loads(fd.get('fraud_flags') or '[]')
            fd['fraud_explanation'] = ", ".join(flags) if flags else "Suspicious pattern detected"
        except:
            fd['fraud_explanation'] = "Suspicious pattern detected"
        flagged_bookings.append(fd)

    # Dynamic Pricing Control Data
    BASE_PRICES = {
        'Single': 3500,
        'Double': 5500,
        'Family': 7000,
        'Couple': 8500,
        'Couple Suite': 8500,
        'VIP Suite': 12000,
        'Executive Suite': 10000,
    }
    pricing_panel = []
    for room_type, price_info in prices.items():
        base = BASE_PRICES.get(room_type, BASE_PRICES.get(room_type.split()[0], 5000))
        actual_price = price_info.get("final_price", base) if isinstance(price_info, dict) else price_info
        delta = actual_price - base
        pct_change = round((delta / base) * 100, 1) if base > 0 else 0

        # Determine AI Reason
        if isinstance(price_info, dict) and price_info.get("reason"):
            ai_reason = price_info["reason"]
        elif pct_change > 20:
            ai_reason = "🔥 Very high demand — surge pricing active"
        elif pct_change > 0:
            ai_reason = "📈 Weekend/event premium applied"
        elif pct_change < -20:
            ai_reason = "📉 Low occupancy — discount to attract bookings"
        elif pct_change < 0:
            ai_reason = "💡 Slight discount — moderate demand"
        else:
            ai_reason = "✅ Standard market rate"

        pricing_panel.append({
            "room_type": room_type,
            "base_price": base,
            "ai_price": round(actual_price, 0),
            "pct_change": pct_change,
            "ai_reason": ai_reason
        })

    # AI Recommendation Insights
    rec_insights = [
        {"title": "Most Booked", "insight": "VIP Suites are currently trending among couples."},
        {"title": "Demographic", "insight": "Family rooms see highest demand during weekend check-ins."},
        {"title": "Amenity Preference", "insight": "Guests searching for 'Spa' convert 3x faster on Executive Suites."}
    ]
    
    conn.close()

    rooms_by_floor = {}
    for r in rooms:
        rd = dict(r)
        fl = str(rd["floor"])
        if fl not in rooms_by_floor:
            rooms_by_floor[fl] = []
        rooms_by_floor[fl].append(rd)

    return render_template(
        "manager/dashboard.html",
        user=user,
        kpis={
            "today_revenue": today_rev,
            "occupancy": occupancy,
            "staff_count": staff_count,
            "avg_rating": round(avg_rating, 1),
            "pending_tasks": pending_tasks,
            "tasks_done": completed_tasks,
            "fraud_alerts": high_fraud,
            "cancel_risk": cancel_risk,
            "safe_bookings": safe_bookings,
        },
        team=[dict(t) for t in team],
        shifts=[dict(s) for s in shifts],
        bookings=[dict(b) for b in bookings],
        today_bookings=[dict(b) for b in today_bookings],
        flagged_bookings=flagged_bookings,
        pricing_panel=pricing_panel,
        rec_insights=rec_insights,
        rooms_by_floor=rooms_by_floor,
        recent_reviews=[dict(r) for r in recent_reviews],
        low_reviews=[dict(r) for r in low_reviews],
        inventory=[dict(i) for i in inventory],
        low_stock=[dict(i) for i in low_stock],
        issues=[dict(i) for i in issues],
        demand_forecast=demand_forecast,
        demand_next_7_avg=next_7_avg,
    )


@manager_bp.route("/manager/shifts", methods=["GET", "POST"])
@manager_required
def shift_management():
    user = get_current_user()
    conn = get_db()

    if request.method == "POST":
        shift_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO staff_shifts (shift_id, staff_id, date, shift_type, start_time, end_time, status)
                       VALUES (?, ?, ?, ?, ?, ?, 'scheduled')""",
            (
                shift_id,
                request.form.get("staff_id"),
                request.form.get("date"),
                request.form.get("shift_type"),
                request.form.get("start_time"),
                request.form.get("end_time"),
            ),
        )
        conn.commit()
        flash("Shift scheduled successfully.", "success")

    # Next 7 days shifts
    shifts = conn.execute(
        """SELECT s.*, u.first_name, u.last_name, u.department FROM staff_shifts s
                             JOIN users u ON s.staff_id = u.user_id
                             WHERE s.date >= date('now') AND s.date <= date('now', '+7 days')
                             ORDER BY s.date, s.shift_type"""
    ).fetchall()

    staff_list = conn.execute(
        "SELECT user_id, first_name, last_name, department FROM users WHERE role = 'staff' AND is_active = 1"
    ).fetchall()
    conn.close()

    return render_template(
        "manager/shifts.html",
        user=user,
        shifts=[dict(s) for s in shifts],
        staff_list=[dict(s) for s in staff_list],
    )


@manager_bp.route("/manager/inventory")
@manager_required
def inventory_management():
    user = get_current_user()
    conn = get_db()
    items = conn.execute("SELECT * FROM inventory ORDER BY category, name").fetchall()
    conn.close()
    return render_template(
        "manager/inventory.html", user=user, inventory=[dict(i) for i in items]
    )


@manager_bp.route("/api/manager/inventory/update", methods=["POST"])
@manager_required
def update_inventory():
    item_id = request.json.get("item_id")
    new_stock = int(request.json.get("stock_count", 0))
    conn = get_db()
    conn.execute(
        "UPDATE inventory SET stock_count = ?, last_updated = ? WHERE item_id = ?",
        (new_stock, datetime.now().isoformat(), item_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@manager_bp.route("/manager/tasks")
@manager_required
def task_management():
    user = get_current_user()
    conn = get_db()
    tasks = conn.execute(
        """SELECT h.*, u.first_name, u.last_name FROM housekeeping_tasks h
                            LEFT JOIN users u ON h.assigned_to = u.user_id
                            ORDER BY CASE h.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                            h.created_at DESC"""
    ).fetchall()
    staff = conn.execute(
        "SELECT user_id, first_name, last_name FROM users WHERE role = 'staff' AND is_active = 1"
    ).fetchall()
    conn.close()
    return render_template(
        "manager/tasks.html",
        user=user,
        tasks=[dict(t) for t in tasks],
        staff=[dict(s) for s in staff],
    )


@manager_bp.route("/api/manager/booking/status", methods=["POST"])
@manager_required
def update_booking_status():
    booking_id = request.json.get("booking_id")
    status = request.json.get("status")
    if status not in ["pending", "confirmed", "completed", "cancelled"]:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE bookings SET status = ?, updated_at = ? WHERE booking_id = ?",
        (status, datetime.now().isoformat(), booking_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@manager_bp.route("/api/manager/room/update-status", methods=["POST"])
@manager_required
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
        return jsonify({"success": False, "message": "Invalid status"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE rooms SET status = ? WHERE room_number = ?",
        (new_status, room_number),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@manager_bp.route("/api/manager/task/assign", methods=["POST"])
@manager_required
def assign_task():
    task_id = request.json.get("task_id")
    staff_id = request.json.get("staff_id")
    if not task_id or not staff_id:
        return jsonify({"success": False, "message": "Missing data"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE housekeeping_tasks SET assigned_to = ?, status = 'pending' WHERE task_id = ?",
        (staff_id, task_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@manager_bp.route("/api/manager/chat", methods=["POST"])
@manager_required
def manager_chat():
    user_msg = request.json.get("message", "")
    if not user_msg:
        return jsonify({"reply": "I didn't catch that."})

    # Build live context for AI
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    today_rev = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM bookings WHERE date(created_at) = ? AND payment_status = 'paid'", (today,)).fetchone()[0]
    monthly_rev = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM bookings WHERE strftime('%Y-%m', created_at) = ? AND payment_status = 'paid'", (datetime.now().strftime("%Y-%m"),)).fetchone()[0]
    rooms_count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    occupied = conn.execute("SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM housekeeping_tasks WHERE status = 'pending'").fetchone()[0]
    fraud = conn.execute("SELECT COUNT(*) FROM bookings WHERE fraud_score >= 35 OR is_flagged = 1").fetchone()[0]
    conn.close()

    context = {
        "today_revenue": today_rev,
        "monthly_revenue": monthly_rev,
        "occupancy": round(occupied / max(rooms_count, 1) * 100, 1) if rooms_count else 0,
        "pending_tasks": pending,
        "fraud_count": fraud
    }

    reply = openai_agent.handle_manager_message(user_msg, context)
    return jsonify({"reply": reply})
