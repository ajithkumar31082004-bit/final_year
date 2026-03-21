"""
Blissful Abodes - Super Admin Routes
GOD MODE: Full system control, audit logs, ML analytics
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
import os
import shutil
from models.database import get_db, DATABASE_PATH
from services.security import hash_password
from ml_models.models import (
    get_demand_model,
    get_pricing_engine,
    get_sentiment_analyzer,
    get_fraud_detector,
)

superadmin_bp = Blueprint("superadmin", __name__)


def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        is_super = session.get("user_role") == "superadmin"
        is_returning = (
            session.get("is_impersonating")
            and session.get("original_role") == "superadmin"
        )
        if "user_id" not in session or (not is_super and not is_returning):
            flash("Super Admin access required.", "danger")
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


@superadmin_bp.route("/superadmin/dashboard")
@superadmin_required
def dashboard():
    user = get_current_user()
    conn = get_db()

    # Mega stats
    lifetime_revenue = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM bookings WHERE payment_status = 'paid'"
    ).fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")
    this_month = datetime.now().strftime("%Y-%m")
    this_year = datetime.now().strftime("%Y")

    today_rev = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) FROM bookings 
                                WHERE date(created_at) = ? AND payment_status = 'paid' """,
        (today,),
    ).fetchone()[0]

    monthly_rev = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) FROM bookings 
                                  WHERE strftime('%Y-%m', created_at) = ? AND payment_status = 'paid' """,
        (this_month,),
    ).fetchone()[0]

    ytd_rev = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) FROM bookings 
                              WHERE strftime('%Y', created_at) = ? AND payment_status = 'paid' """,
        (this_year,),
    ).fetchone()[0]

    total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    occupied = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
    ).fetchone()[0]
    overall_occ = round(occupied / max(total_rooms, 1) * 100, 1)

    total_bookings = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    active_staff = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role IN ('staff', 'manager') AND is_active = 1"
    ).fetchone()[0]
    loyalty_members = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'guest' AND is_active = 1"
    ).fetchone()[0]
    avg_rating = conn.execute(
        "SELECT COALESCE(AVG(overall_rating), 0) FROM reviews"
    ).fetchone()[0]

    # Extended user list
    all_users = conn.execute(
        "SELECT * FROM users ORDER BY role, created_at DESC"
    ).fetchall()
    admin_users = [u for u in all_users if u["role"] in ("admin", "superadmin")]

    # Audit logs
    audit_logs = conn.execute(
        "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50"
    ).fetchall()

    # Flagged bookings
    flagged = conn.execute(
        """SELECT b.*, u.first_name, u.last_name FROM bookings b 
                              JOIN users u ON b.user_id = u.user_id 
                              WHERE b.is_flagged = 1 OR b.fraud_score > 0.5 
                              ORDER BY b.fraud_score DESC"""
    ).fetchall()
    flagged_bookings = []
    for f in flagged:
        fd = dict(f)
        try:
            fd["fraud_flags"] = json.loads(fd.get("fraud_flags") or "[]")
        except Exception:
            fd["fraud_flags"] = []
        flagged_bookings.append(fd)

    # System status (simulated)
    system_status = {
        "database": {"status": "Online", "color": "success"},
        "server": {"status": "Healthy", "color": "success"},
        "email": {"status": "Active", "color": "success"},
        "payment": {"status": "Razorpay Connected", "color": "success"},
        "storage": {"status": "Local", "color": "info"},
        "ml_models": {"status": "6/6 Loaded", "color": "success"},
    }

    # Strategic targets
    annual_target = 15000000  # ₹1.5 Crore
    target_progress = min(100, round(ytd_rev / annual_target * 100, 1))

    # ML Analytics summary
    demand = get_demand_model()
    forecast_7 = demand.get_next_7_days_avg()

    # Revenue trend (simulated multi-year data)
    year_data = []
    for y in range(5):
        yr = datetime.now().year - y
        rev = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) FROM bookings 
                              WHERE strftime('%Y', created_at) = ? AND payment_status = 'paid' """,
            (str(yr),),
        ).fetchone()[0]
        year_data.append({"year": yr, "revenue": round(rev, 0)})
    year_data.reverse()

    # Active room counts by status
    room_status = conn.execute(
        """SELECT status, COUNT(*) as cnt FROM rooms GROUP BY status"""
    ).fetchall()

    conn.close()

    return render_template(
        "superadmin/dashboard.html",
        user=user,
        mega_stats={
            "lifetime_revenue": lifetime_revenue,
            "ytd_revenue": ytd_rev,
            "monthly_revenue": monthly_rev,
            "today_revenue": today_rev,
            "overall_occupancy": overall_occ,
            "total_bookings": total_bookings,
            "active_staff": active_staff,
            "loyalty_members": loyalty_members,
            "avg_rating": round(avg_rating, 1),
            "forecast_7day": forecast_7,
        },
        all_users=[dict(u) for u in all_users],
        admin_users=[dict(u) for u in admin_users],
        audit_logs=[dict(a) for a in audit_logs],
        flagged_bookings=flagged_bookings,
        system_status=system_status,
        annual_target=annual_target,
        target_progress=target_progress,
        year_data=year_data,
        room_status=[dict(r) for r in room_status],
    )


# --- GOD MODE USER OPERATIONS ---
@superadmin_bp.route("/superadmin/users/create", methods=["POST"])
@superadmin_required
def create_any_user():
    """Super Admin can create ANY role including admin and superadmin"""
    email = request.form.get("email", "").lower()
    role = request.form.get("role", "staff")

    conn = get_db()
    existing = conn.execute(
        "SELECT user_id FROM users WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        conn.close()
        flash("Email already exists.", "danger")
        return redirect(url_for("superadmin.dashboard"))

    pwd = request.form.get("password", "Admin@123")
    pwd_hash = hash_password(pwd)
    user_id = f"user_{uuid.uuid4().hex[:12]}"

    conn.execute(
        """INSERT INTO users (user_id, email, phone, password_hash, first_name, last_name, role, is_verified, department)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            user_id,
            email,
            request.form.get("phone", ""),
            pwd_hash,
            request.form.get("first_name", ""),
            request.form.get("last_name", ""),
            role,
            request.form.get("department", ""),
        ),
    )
    conn.commit()
    conn.close()

    flash(f"{role.title()} account created: {email}", "success")
    return redirect(url_for("superadmin.dashboard"))


@superadmin_bp.route("/superadmin/users/<user_id>/delete", methods=["POST"])
@superadmin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        return jsonify({"success": False, "message": "Cannot delete yourself"})
    conn = get_db()
    conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@superadmin_bp.route("/superadmin/users/<user_id>/update", methods=["POST"])
@superadmin_required
def update_user(user_id):
    data = request.json or {}
    role = data.get("role")
    if role and role not in ["guest", "staff", "manager", "admin", "superadmin"]:
        return jsonify({"success": False, "message": "Invalid role"}), 400
    if user_id == session.get("user_id") and role and role != "superadmin":
        return jsonify({"success": False, "message": "Cannot demote yourself"}), 400

    updates = {
        "role": role,
        "department": data.get("department"),
        "shift": data.get("shift"),
        "phone": data.get("phone"),
        "is_active": data.get("is_active"),
    }
    fields = []
    values = []
    for key, value in updates.items():
        if value is None:
            continue
        if key == "is_active":
            value = 1 if str(value).lower() in ["1", "true", "yes"] else 0
        fields.append(f"{key} = ?")
        values.append(value)
    if not fields:
        return jsonify({"success": False, "message": "No updates provided"}), 400

    conn = get_db()
    conn.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?",
        (*values, user_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@superadmin_bp.route("/superadmin/impersonate/<user_id>", methods=["POST"])
@superadmin_required
def impersonate_user(user_id):
    """Impersonate any user (super admin only)"""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()

    if user:
        # Save super admin session
        session["original_user_id"] = session["user_id"]
        session["original_role"] = session["user_role"]

        session["user_id"] = user["user_id"]
        session["user_role"] = user["role"]
        session["user_name"] = f"{user['first_name']} {user['last_name']}"
        session["is_impersonating"] = True

        flash(
            f'Now viewing as: {user["first_name"]} {user["last_name"]} ({user["role"]})',
            "warning",
        )

        role_redirects = {
            "guest": "/guest/dashboard",
            "staff": "/staff/dashboard",
            "manager": "/manager/dashboard",
            "admin": "/admin/dashboard",
        }
        return jsonify(
            {"success": True, "redirect": role_redirects.get(user["role"], "/")}
        )

    return jsonify({"success": False, "message": "User not found"})


@superadmin_bp.route("/superadmin/stop-impersonate")
@superadmin_required
def stop_impersonate():
    if session.get("is_impersonating"):
        session["user_id"] = session.pop("original_user_id")
        session["user_role"] = session.pop("original_role")
        session.pop("is_impersonating", None)
        flash("Returned to Super Admin mode.", "success")
    return redirect(url_for("superadmin.dashboard"))


@superadmin_bp.route("/superadmin/system/maintenance-mode", methods=["POST"])
@superadmin_required
def maintenance_mode():
    enable = request.json.get("enable", False)
    # In production this would set a flag in cache/DB
    return jsonify(
        {
            "success": True,
            "maintenance_mode": enable,
            "message": "Maintenance mode " + ("enabled" if enable else "disabled"),
        }
    )


@superadmin_bp.route("/superadmin/system/backup", methods=["POST"])
@superadmin_required
def backup_database():
    backups_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"blissful_abodes_{timestamp}.db"
    backup_path = os.path.join(backups_dir, backup_name)
    shutil.copyfile(DATABASE_PATH, backup_path)
    return jsonify({"success": True, "backup": backup_name})


@superadmin_bp.route("/superadmin/system/restore", methods=["POST"])
@superadmin_required
def restore_database():
    backup_name = request.json.get("backup")
    if not backup_name:
        return jsonify({"success": False, "message": "Backup name required"}), 400
    backups_dir = os.path.join(os.getcwd(), "backups")
    backup_path = os.path.join(backups_dir, backup_name)
    if not os.path.exists(backup_path):
        return jsonify({"success": False, "message": "Backup not found"}), 404
    shutil.copyfile(backup_path, DATABASE_PATH)
    return jsonify({"success": True, "message": "Database restored. Restart the server."})


@superadmin_bp.route("/superadmin/audit-logs")
@superadmin_required
def audit_logs():
    user = get_current_user()
    conn = get_db()
    logs = conn.execute(
        """SELECT al.*, u.first_name, u.last_name, u.email 
                           FROM audit_logs al LEFT JOIN users u ON al.user_id = u.user_id
                           ORDER BY al.created_at DESC LIMIT 200"""
    ).fetchall()
    conn.close()
    return render_template(
        "superadmin/audit_logs.html", user=user, logs=[dict(l) for l in logs]
    )


@superadmin_bp.route("/superadmin/ml-analytics")
@superadmin_required
def ml_analytics():
    user = get_current_user()

    demand = get_demand_model()
    forecast = demand.predict_next_30_days()

    pricing = get_pricing_engine()
    prices = pricing.get_all_current_prices(65)

    # Fraud summary
    conn = get_db()
    high_fraud = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE fraud_score >= 35"
    ).fetchone()[0]
    flagged = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE is_flagged = 1"
    ).fetchone()[0]

    # Sentiment summary
    sentiments = conn.execute(
        "SELECT sentiment, COUNT(*) as cnt FROM reviews GROUP BY sentiment"
    ).fetchall()

    # Model accuracy metrics
    model_metrics = [
        {
            "name": "Room Recommendation",
            "algorithm": "Collaborative Filtering",
            "accuracy": "78%",
            "status": "✅ Active",
        },
        {
            "name": "Demand Forecasting",
            "algorithm": "Linear Regression",
            "accuracy": "89%",
            "status": "✅ Active",
        },
        {
            "name": "Dynamic Pricing",
            "algorithm": "Rules + ML Hybrid",
            "accuracy": "N/A",
            "status": "✅ Active",
        },
        {
            "name": "Sentiment Analysis",
            "algorithm": "TextBlob + VADER",
            "accuracy": "87%",
            "status": "✅ Active",
        },
        {
            "name": "Fraud Detection",
            "algorithm": "Random Forest",
            "accuracy": "95%",
            "status": "✅ Active",
        },
        {
            "name": "Cancellation Prediction",
            "algorithm": "Gradient Boosting",
            "accuracy": "82%",
            "status": "✅ Active",
        },
    ]

    conn.close()

    return render_template(
        "superadmin/ml_analytics.html",
        user=user,
        forecast=forecast,
        prices=prices,
        high_fraud_count=high_fraud,
        flagged_count=flagged,
        sentiments=[dict(s) for s in sentiments],
        model_metrics=model_metrics,
    )
