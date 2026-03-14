"""
Blissful Abodes - Authentication Routes
Handles registration, login, OTP, password reset
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
    current_app,
)
import uuid
import random
import json
from datetime import datetime, timedelta
from models.database import get_db
from services.email_service import send_welcome_email, send_otp_email
from services.security import hash_password, check_password
from services.rate_limiter import check_rate_limit

auth_bp = Blueprint("auth", __name__)


def log_action(user_id, action, resource, details="", ip="", result="success"):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO audit_logs (log_id, user_id, action, resource, details, ip_address, result)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), user_id, action, resource, details, ip, result),
        )
        conn.commit()
    finally:
        conn.close()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()

        errors = []
        if not all([email, phone, password, first_name, last_name]):
            errors.append("All fields are required")
        if password != confirm_password:
            errors.append("Passwords do not match")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")

        conn = get_db()
        existing = conn.execute(
            "SELECT user_id FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if existing:
            errors.append("Email already registered")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("auth/register.html")

        user_id = f"user_{uuid.uuid4().hex[:12]}"
        pwd_hash = hash_password(password)

        conn = get_db()
        conn.execute(
            """INSERT INTO users (user_id, email, phone, password_hash, first_name, last_name, 
                       role, is_verified, preferences)
                       VALUES (?, ?, ?, ?, ?, ?, 'guest', 1, '{}')""",
            (user_id, email, phone, pwd_hash, first_name, last_name),
        )

        # Welcome notification
        conn.execute(
            """INSERT INTO notifications (notification_id, user_id, title, message, notification_type, action_url)
                       VALUES (?, ?, ?, ?, 'success', '/rooms')""",
            (
                str(uuid.uuid4()),
                user_id,
                "🎉 Welcome to Blissful Abodes!",
                "Your account is ready. Use WELCOME10 for 10% off your first booking!",
            ),
        )
        conn.commit()
        conn.close()

        # Send welcome email (async-style)
        try:
            send_welcome_email(email, first_name)
        except Exception:
            current_app.logger.exception("Failed to send welcome email")

        log_action(user_id, "REGISTER", "users", email, request.remote_addr)
        flash("Registration successful! Welcome to Blissful Abodes!", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("redirect_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        ip_addr = request.remote_addr or "unknown"
        allowed, retry_after = check_rate_limit(
            f"login:{ip_addr}:{email}", limit=5, window_seconds=300
        )
        if not allowed:
            flash(
                f"Too many login attempts. Try again in {retry_after} seconds.",
                "danger",
            )
            return render_template("auth/login.html")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()
        conn.close()

        if user and check_password(password, user["password_hash"]):
            session.permanent = True
            session["user_id"] = user["user_id"]
            session["user_role"] = user["role"]
            session["user_name"] = f"{user['first_name']} {user['last_name']}"
            session["user_email"] = user["email"]

            # Update last login
            conn = get_db()
            conn.execute(
                "UPDATE users SET last_login = ? WHERE user_id = ?",
                (datetime.now().isoformat(), user["user_id"]),
            )
            conn.commit()
            conn.close()

            log_action(user["user_id"], "LOGIN", "auth", email, request.remote_addr)

            role = user["role"]
            redirects = {
                "superadmin": "/superadmin/dashboard",
                "admin": "/admin/dashboard",
                "manager": "/manager/dashboard",
                "staff": "/staff/dashboard",
                "guest": "/guest/dashboard",
            }
            return redirect(redirects.get(role, "/"))
        else:
            log_action(
                email, "LOGIN_FAIL", "auth", email, request.remote_addr, "failure"
            )
            flash("Invalid email or password. Please try again.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id:
        log_action(user_id, "LOGOUT", "auth", ip=request.remote_addr)
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user:
            otp = str(random.randint(100000, 999999))
            otp_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
            conn.execute(
                "UPDATE users SET otp = ?, otp_expiry = ? WHERE email = ?",
                (otp, otp_expiry, email),
            )
            conn.commit()
            try:
                send_otp_email(email, user["first_name"], otp)
            except Exception:
                current_app.logger.exception("Failed to send OTP email (forgot-password)")
            session["reset_email"] = email
            flash(f"OTP sent to {email}. Check your inbox.", "success")
            return redirect(url_for("auth.reset_password"))
        else:
            flash("No account found with that email.", "danger")
        conn.close()

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        otp = request.form.get("otp", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        email = session.get("reset_email", "")

        if not email:
            flash("Session expired. Please try again.", "danger")
            return redirect(url_for("auth.forgot_password"))

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and user["otp"] == otp:
            if datetime.fromisoformat(user["otp_expiry"]) > datetime.now():
                if new_password == confirm and len(new_password) >= 8:
                    pwd_hash = hash_password(new_password)
                    conn.execute(
                        "UPDATE users SET password_hash = ?, otp = NULL WHERE email = ?",
                        (pwd_hash, email),
                    )
                    conn.commit()
                    session.pop("reset_email", None)
                    flash("Password reset successfully! Please login.", "success")
                    return redirect(url_for("auth.login"))
                else:
                    flash(
                        "Passwords must match and be at least 8 characters.", "danger"
                    )
            else:
                flash("OTP has expired. Please request a new one.", "danger")
        else:
            flash("Invalid OTP. Please check and try again.", "danger")

        conn.close()

    return render_template("auth/reset_password.html")


@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    """AJAX endpoint to send OTP"""
    email = request.json.get("email", "")
    ip_addr = request.remote_addr or "unknown"
    allowed, retry_after = check_rate_limit(
        f"send_otp:{ip_addr}:{email}", limit=3, window_seconds=600
    )
    if not allowed:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Too many OTP requests. Try again in {retry_after} seconds.",
                }
            ),
            429,
        )
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if user:
        otp = str(random.randint(100000, 999999))
        conn2 = get_db()
        conn2.execute(
            "UPDATE users SET otp = ?, otp_expiry = ? WHERE email = ?",
            (otp, (datetime.now() + timedelta(minutes=10)).isoformat(), email),
        )
        conn2.commit()
        conn2.close()
        try:
            send_otp_email(email, user["first_name"], otp)
        except Exception:
            current_app.logger.exception("Failed to send OTP email (send-otp)")
        return jsonify({"success": True, "message": f"OTP sent to {email}"})

    return jsonify({"success": False, "message": "Email not found"})
