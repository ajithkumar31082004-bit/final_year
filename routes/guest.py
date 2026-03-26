"""
Blissful Abodes - Guest Routes
Guest dashboard, room browsing, booking, reviews, loyalty
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, current_app
from functools import wraps
from datetime import datetime, timedelta
import json
import uuid

from models.database import get_db
from ml_models.models import (
    get_recommendation_model,
    get_pricing_engine,
    get_demand_model,
    get_sentiment_analyzer,
    get_cancellation_predictor,
    get_fraud_detector,
    get_user_behavior_model,
)

from services.email_service import send_booking_confirmation, send_cancellation_email, send_review_request
from services.refund_policy import calculate_refund_pct
from services.pdf_service import generate_gst_invoice, generate_booking_qr
from services.payment_service import create_order, verify_payment, RAZORPAY_KEY_ID

guest_bp = Blueprint("guest", __name__)

ROOM_IMAGE_MAP = {
    "Single": "images/rooms/single.jpg",
    "Double": "images/rooms/double.jpg",
    "Family": "images/rooms/family.jpg",
    "Couple": "images/rooms/couple.jpg",
    "VIP Suite": "images/rooms/vip.jpg",
}


def _local_room_image_path(room_type):
    return ROOM_IMAGE_MAP.get(room_type, ROOM_IMAGE_MAP["Single"])


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def offers_eligibility(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT loyalty_points FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    paid_count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE user_id = ? AND payment_status = 'paid'",
        (user_id,),
    ).fetchone()[0]
    conn.close()

    loyalty_points = user["loyalty_points"] if user else 0
    min_points = current_app.config.get("OFFERS_MIN_POINTS", 0)
    require_first = current_app.config.get("OFFERS_REQUIRE_FIRST_BOOKING", True)
    has_first_booking = paid_count > 0
    eligible = (not require_first or has_first_booking) and loyalty_points >= min_points

    return {
        "eligible": eligible,
        "has_first_booking": has_first_booking,
        "loyalty_points": loyalty_points,
        "min_points": min_points,
        "first_booking_required": require_first,
    }


def get_current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()
    return dict(user) if user else None


@guest_bp.route("/book/<room_id>", methods=["GET", "POST"])
@login_required
def book_room(room_id):
    """Standard booking route (non-AI)"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    room = conn.execute(
        "SELECT * FROM rooms WHERE room_id = ? AND is_active = 1", (room_id,)
    ).fetchone()
    conn.close()

    if not room:
        flash("Room not found or unavailable.", "danger")
        return redirect(url_for("guest.room_listing"))

    room_dict = dict(room)

    if request.method == "POST":
        check_in = request.form.get("check_in", "")
        check_out = request.form.get("check_out", "")
        num_guests = safe_int(request.form.get("num_guests", 1), 1)

        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
            if co <= ci:
                flash("Check-out must be after check-in", "danger")
                return redirect(url_for("guest.book_room", room_id=room_id))
        except ValueError:
            flash("Invalid date format", "danger")
            return redirect(url_for("guest.book_room", room_id=room_id))

        nights = (co - ci).days
        base_amount = room_dict["current_price"] * nights
        gst_amount = base_amount * 0.18
        total_amount = base_amount + gst_amount

        # Create booking
        booking_id = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        conn = get_db()
        conn.execute(
            """INSERT INTO bookings
               (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
                base_amount, gst_amount, total_amount, status, payment_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (booking_id, user["user_id"], room_id, room_dict.get("room_number", ""), check_in, check_out,
             num_guests, base_amount, gst_amount, total_amount, "pending", "pending", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        flash("Booking created successfully!", "success")
        return redirect(url_for("guest.booking_detail", booking_id=booking_id))

    return render_template("guest/book_room.html", room=room_dict)



@guest_bp.route("/book-with-ai/<room_id>", methods=["GET", "POST"])
@login_required
def book_room_with_ai_decision(room_id):
    """AI-powered booking with Central Decision Engine"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    room = conn.execute(
        "SELECT * FROM rooms WHERE room_id = ? AND is_active = 1", (room_id,)
    ).fetchone()

    if not room:
        conn.close()
        flash("Room not found or unavailable.", "danger")
        return redirect(url_for("guest.room_listing"))

    room_dict = dict(room)
    conn.close()

    if request.method == "POST":
        check_in = request.form.get("check_in", "")
        check_out = request.form.get("check_out", "")
        num_guests = safe_int(request.form.get("num_guests", 1), 1)
        payment_method = request.form.get("payment_method", "card")

        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
            if co <= ci:
                flash("Check-out must be after check-in", "danger")
                return redirect(url_for("guest.book_room_with_ai_decision", room_id=room_id))
        except ValueError:
            flash("Invalid date format", "danger")
            return redirect(url_for("guest.book_room_with_ai_decision", room_id=room_id))

        nights = (co - ci).days
        total_amount = room_dict["current_price"] * nights
        days_until_checkin = max(0, (ci - datetime.now().date()).days)

        # Build booking + context dicts for the AI engine
        booking_data = {
            "user_id": user["user_id"],
            "room_type": room_dict.get("room_type", "Single"),
            "check_in": check_in,
            "check_out": check_out,
            "guests": num_guests,
            "total_amount": total_amount,
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "payment_method": payment_method,
            "created_at": datetime.now().isoformat(),
        }

        try:
            # Load context from DB
            db = get_db()
            all_bookings = [dict(b) for b in db.execute("SELECT * FROM bookings").fetchall()]
            all_rooms    = [dict(r) for r in db.execute("SELECT * FROM rooms").fetchall()]
            all_users    = [dict(u) for u in db.execute("SELECT * FROM users").fetchall()]
            occ_total    = db.execute("SELECT COUNT(*) FROM rooms WHERE is_active=1").fetchone()[0] or 1
            occ_occupied = db.execute("SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')").fetchone()[0]
            db.close()
            occupancy_rate = round(occ_occupied / max(occ_total, 1), 2)

            from ml_models.ai_decision_engine import evaluate_booking as _ai_eval, get_decision_summary
            ai_result = _ai_eval(
                booking=booking_data,
                room=room_dict,
                user=dict(user),
                all_bookings=all_bookings,
                all_rooms=all_rooms,
                all_users=all_users,
                occupancy_rate=occupancy_rate,
                days_until_checkin=days_until_checkin,
            )
            summary = get_decision_summary(ai_result)

            # If engine says BLOCK, reject immediately
            if ai_result["decision"] == "BLOCK":
                flash("⚠️ Booking blocked by AI security engine. " + (ai_result["reasons"][0] if ai_result["reasons"] else ""), "danger")
                return redirect(url_for("guest.room_listing"))

            # Store compact summary in session for confirmation page
            session["ai_decision_result"] = summary

            return render_template(
                "guest/ai_decision_result.html",
                room=room_dict,
                booking_data=booking_data,
                ai_result=ai_result,
                summary=summary,
            )

        except Exception as e:
            current_app.logger.error(f"AI Decision Engine error: {e}")
            flash("AI evaluation unavailable. Proceeding with standard booking.", "warning")
            return redirect(url_for("guest.book_room", room_id=room_id))

    return render_template("guest/book_with_ai.html", room=room_dict)


@guest_bp.route("/api/decision/evaluate", methods=["POST"])
@login_required
def api_evaluate_decision():
    """
    REST API endpoint — Central AI Decision Engine
    POST JSON: { room_id, check_in, check_out, num_guests, payment_method }
    Returns: full AI decision JSON with score, reasons, price, decision
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    room_id       = data.get("room_id", "")
    check_in      = data.get("check_in", "")
    check_out     = data.get("check_out", "")
    num_guests    = int(data.get("num_guests", 1))
    payment_method = data.get("payment_method", "card")

    try:
        db = get_db()
        room = db.execute("SELECT * FROM rooms WHERE room_id=?", (room_id,)).fetchone()
        if not room:
            db.close()
            return jsonify({"error": "Room not found"}), 404

        room_dict    = dict(room)
        all_bookings = [dict(b) for b in db.execute("SELECT * FROM bookings").fetchall()]
        all_rooms    = [dict(r) for r in db.execute("SELECT * FROM rooms").fetchall()]
        all_users    = [dict(u) for u in db.execute("SELECT * FROM users").fetchall()]
        occ_total    = db.execute("SELECT COUNT(*) FROM rooms WHERE is_active=1").fetchone()[0] or 1
        occ_occupied = db.execute("SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')").fetchone()[0]
        db.close()

        occupancy_rate = round(occ_occupied / max(occ_total, 1), 2)

        nights = 1
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
            nights = max(1, (co - ci).days)
            days_until = max(0, (ci - datetime.now().date()).days)
        except Exception:
            days_until = 7

        total_amount = room_dict.get("current_price", 5000) * nights

        booking_data = {
            "user_id":        user["user_id"],
            "room_type":      room_dict.get("room_type", "Single"),
            "check_in":       check_in,
            "check_out":      check_out,
            "guests":         num_guests,
            "total_amount":   total_amount,
            "email":          user.get("email", ""),
            "payment_method": payment_method,
            "created_at":     datetime.now().isoformat(),
        }

        from ml_models.ai_decision_engine import evaluate_booking as _ai_eval, get_decision_summary
        ai_result = _ai_eval(
            booking=booking_data,
            room=room_dict,
            user=dict(user),
            all_bookings=all_bookings,
            all_rooms=all_rooms,
            all_users=all_users,
            occupancy_rate=occupancy_rate,
            days_until_checkin=days_until,
        )
        return jsonify(get_decision_summary(ai_result))

    except Exception as e:
        current_app.logger.error(f"API decision error: {e}")
        return jsonify({"error": str(e), "decision": "APPROVE", "confidence": "50%", "reasons": ["AI evaluation unavailable"]}), 500




@guest_bp.route("/booking/<booking_id>")
@login_required
def booking_detail(booking_id):
    """View booking details"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    booking = conn.execute(
        """SELECT b.*, r.room_type, r.room_number, r.amenities
           FROM bookings b
           JOIN rooms r ON b.room_id = r.room_id
           WHERE b.booking_id = ? AND b.user_id = ?""",
        (booking_id, user["user_id"])
    ).fetchone()
    review_row = conn.execute(
        "SELECT review_id FROM reviews WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()
    conn.close()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("guest.my_bookings"))

    booking_dict = dict(booking)

    # Parse amenities if stored as JSON
    try:
        amenities = json.loads(booking_dict.get("amenities", "[]"))
        booking_dict["amenities"] = amenities
    except:
        booking_dict["amenities"] = []

    booking_dict["has_review"] = bool(review_row)
    return render_template("guest/booking_detail.html", booking=booking_dict)


@guest_bp.route("/payment/<booking_id>")
@guest_bp.route("/guest/payment/<booking_id>")
@login_required
def payment_page(booking_id):
    """Payment page for a booking"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()
    conn.close()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("guest.my_bookings"))

    booking_dict = dict(booking)
    if booking_dict.get("payment_status") == "paid":
        flash("Payment already completed.", "success")
        return redirect(url_for("guest.booking_detail", booking_id=booking_id))

    order_resp = create_order(
        booking_dict.get("total_amount", 0),
        booking_id,
        notes={"user_id": user.get("user_id", "")},
    )
    if not order_resp.get("success"):
        flash("Unable to initialize payment. Please try again.", "danger")
        return redirect(url_for("guest.booking_detail", booking_id=booking_id))

    order = order_resp.get("order", {})
    order_id = order.get("id", "")
    amount_paise = order.get("amount", int(booking_dict.get("total_amount", 0) * 100))

    conn = get_db()
    conn.execute(
        "UPDATE bookings SET razorpay_order_id = ?, updated_at = ? WHERE booking_id = ?",
        (order_id, datetime.now().isoformat(), booking_id),
    )
    conn.commit()
    conn.close()

    demo_mode = str(order_id).startswith("order_demo_")
    return render_template(
        "guest/payment.html",
        booking=booking_dict,
        order_id=order_id,
        amount_paise=amount_paise,
        razorpay_key_id=RAZORPAY_KEY_ID,
        demo_mode=demo_mode,
    )


@guest_bp.route("/api/payment/verify", methods=["POST"])
@login_required
def verify_payment_api():
    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")
    signature = data.get("razorpay_signature")

    if not booking_id or not order_id or not payment_id or not signature:
        return jsonify({"success": False, "message": "Missing payment details"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()
    if not booking:
        conn.close()
        return jsonify({"success": False, "message": "Booking not found"}), 404

    if booking["payment_status"] == "paid":
        conn.close()
        return jsonify({"success": True, "message": "Already paid"})

    stored_order = booking["razorpay_order_id"]
    if stored_order and stored_order != order_id:
        conn.close()
        return jsonify({"success": False, "message": "Order mismatch"}), 400

    if not verify_payment(order_id, payment_id, signature):
        conn.close()
        return jsonify({"success": False, "message": "Payment verification failed"}), 400

    conn.execute(
        """UPDATE bookings
           SET payment_status = 'paid',
               status = 'confirmed',
               payment_id = ?,
               razorpay_order_id = ?,
               updated_at = ?
           WHERE booking_id = ?""",
        (payment_id, order_id, datetime.now().isoformat(), booking_id),
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@guest_bp.route("/my-bookings")
@login_required
def my_bookings():
    """List all guest bookings"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    bookings = conn.execute(
        """SELECT b.*, r.room_type, r.room_number,
                  (SELECT COUNT(1) FROM reviews rv
                   WHERE rv.booking_id = b.booking_id AND rv.user_id = b.user_id) AS review_count
           FROM bookings b
           JOIN rooms r ON b.room_id = r.room_id
           WHERE b.user_id = ?
           ORDER BY b.created_at DESC""",
        (user["user_id"],)
    ).fetchall()
    conn.close()

    return render_template("guest/bookings.html", user=user, bookings=[dict(b) for b in bookings])


@guest_bp.route("/cancel-booking/<booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"])
    ).fetchone()

    if not booking:
        conn.close()
        flash("Booking not found.", "danger")
        return redirect(url_for("guest.my_bookings"))

    if booking["status"] in ["cancelled", "completed"]:
        conn.close()
        flash("Cannot cancel this booking.", "danger")
        return redirect(url_for("guest.my_bookings"))

    # Calculate refund
    check_in = datetime.strptime(booking["check_in"], "%Y-%m-%d")
    hours_until = (check_in - datetime.now()).total_seconds() / 3600
    refund_pct = calculate_refund_pct(hours_until, booking["payment_status"])
    refund_amount = booking["total_amount"] * refund_pct

    # Update booking status
    conn.execute(
        "UPDATE bookings SET status = 'cancelled', updated_at = ? WHERE booking_id = ?",
        (datetime.now().isoformat(), booking_id)
    )

    # Free up the room
    conn.execute(
        "UPDATE rooms SET status = 'available' WHERE room_id = ?",
        (booking["room_id"],)
    )

    conn.commit()
    conn.close()

    # Send cancellation email
    try:
        send_cancellation_email(
            user["email"],
            user["first_name"],
            booking,
            refund_amount
        )
    except Exception as e:
        current_app.logger.error(f"Failed to send cancellation email: {e}")

    flash(f"Booking cancelled. Refund amount: INR {refund_amount:,.2f}", "success")
    return redirect(url_for("guest.my_bookings"))


@guest_bp.route("/dashboard")
@login_required
def dashboard():
    """Guest dashboard"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()

    # Get upcoming bookings
    today = datetime.now().date().isoformat()
    upcoming = conn.execute(
        """SELECT b.*, r.room_type, r.room_number
           FROM bookings b
           JOIN rooms r ON b.room_id = r.room_id
           WHERE b.user_id = ? AND b.check_in >= ? AND b.status IN ('confirmed', 'pending')
           ORDER BY b.check_in ASC LIMIT 5""",
        (user["user_id"], today)
    ).fetchall()

    # Get past bookings count
    past_count = conn.execute(
        """SELECT COUNT(*) FROM bookings
           WHERE user_id = ? AND status = 'completed'""",
        (user["user_id"],)
    ).fetchone()[0]

    # Get total spent
    total_spent = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) FROM bookings
           WHERE user_id = ? AND status IN ('completed', 'confirmed')""",
        (user["user_id"],)
    ).fetchone()[0]

    # Get notifications
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user["user_id"],)
    ).fetchall()
    
    # Get AI Recommendations
    recommender = get_recommendation_model()
    raw_recs = recommender.get_recommendations(user["user_id"], n=3)
    recommended_rooms = []
    for rec in raw_recs:
        r_db = conn.execute("SELECT room_id, current_price FROM rooms WHERE room_type = ? AND is_active = 1 LIMIT 1", (rec["room_type"],)).fetchone()
        if r_db:
            rec_dict = dict(rec)
            rec_dict["room_id"] = r_db["room_id"]
            rec_dict["current_price"] = r_db["current_price"]
            recommended_rooms.append(rec_dict)
            
    conn.close()

    current_tier = user.get("tier_level", "Silver")
    current_points = int(user.get("loyalty_points") or 0)
    
    if current_tier == "Silver":
        next_tier = "Gold"
        next_threshold = 5000
    elif current_tier == "Gold":
        next_tier = "Platinum"
        next_threshold = 15000
    else:
        next_tier = "Platinum"
        next_threshold = 15000
        
    tier_progress = min(100, int((current_points / next_threshold) * 100)) if next_threshold else 100

    return render_template(
        "guest/dashboard.html",
        user=user,
        upcoming_bookings=[dict(b) for b in upcoming],
        past_bookings_count=past_count,
        total_spent=total_spent,
        tier_progress=tier_progress,
        next_threshold=next_threshold,
        next_tier=next_tier,
        notifications=[dict(n) for n in notifications],
        recommended_rooms=recommended_rooms
    )


@guest_bp.route("/review/<booking_id>", methods=["GET", "POST"])
@login_required
def write_review(booking_id):
    """Write a review for a completed booking"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    booking = conn.execute(
        """SELECT b.*, r.room_id, r.room_type
           FROM bookings b
           JOIN rooms r ON b.room_id = r.room_id
           WHERE b.booking_id = ? AND b.user_id = ? AND b.status = 'completed'""",
        (booking_id, user["user_id"])
    ).fetchone()

    if not booking:
        conn.close()
        flash("Booking not found or not eligible for review.", "danger")
        return redirect(url_for("guest.my_bookings"))

    existing = conn.execute(
        "SELECT review_id FROM reviews WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()
    if existing:
        conn.close()
        flash("You have already submitted a review for this booking.", "info")
        return redirect(url_for("guest.my_bookings"))

    if request.method == "POST":
        rating = safe_int(
            request.form.get("rating") or request.form.get("overall_rating"), 5
        )
        comment = request.form.get("comment", "").strip()
        cleanliness = safe_int(
            request.form.get("cleanliness") or request.form.get("cleanliness_rating"),
            5,
        )
        staff = safe_int(
            request.form.get("staff") or request.form.get("staff_rating"), 5
        )
        location = safe_int(
            request.form.get("location") or request.form.get("location_rating"), 5
        )
        value = safe_int(request.form.get("value") or request.form.get("value_rating"), 5)
        amenities = safe_int(
            request.form.get("amenities")
            or request.form.get("amenities_rating"),
            5,
        )

        if not comment or len(comment) < 5:
            flash("Please provide a short comment (at least 5 characters).", "warning")
            return redirect(url_for("guest.write_review", booking_id=booking_id))

        rating = max(1, min(5, rating))
        cleanliness = max(1, min(5, cleanliness))
        staff = max(1, min(5, staff))
        location = max(1, min(5, location))
        value = max(1, min(5, value))
        amenities = max(1, min(5, amenities))

        review_id = f"RV{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        sentiment = get_sentiment_analyzer()
        analysis = sentiment.analyze(comment)

        conn.execute(
            """INSERT INTO reviews
               (review_id, booking_id, user_id, room_id, overall_rating, comment,
                cleanliness_rating, staff_rating, location_rating, value_rating, amenities_rating,
                verified_stay, sentiment, sentiment_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (review_id, booking_id, user["user_id"], booking["room_id"],
             rating, comment, cleanliness, staff, location, value, amenities,
             1, analysis.get("sentiment", "neutral"), analysis.get("score", 0),
             datetime.now().isoformat())
        )

        # Award loyalty points for review
        current_points = user.get("loyalty_points", 0)
        new_points = current_points + 50
        conn.execute(
            "UPDATE users SET loyalty_points = ? WHERE user_id = ?",
            (new_points, user["user_id"])
        )

        conn.commit()
        conn.close()

        flash("Review submitted successfully! You earned 50 loyalty points!", "success")
        return redirect(url_for("guest.my_bookings"))

    conn.close()
    return render_template("guest/write_review.html", booking=dict(booking))


@guest_bp.route("/loyalty")
@login_required
def loyalty():
    """View loyalty program details"""
    user = get_current_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()
    transactions = conn.execute(
        """SELECT * FROM loyalty_transactions
           WHERE user_id = ?
           ORDER BY created_at DESC LIMIT 20""",
        (user["user_id"],)
    ).fetchall()

    tiers = {
        "Silver": {"min": 0, "max": 5000, "color": "#C0C0C0", "perks": ["Priority support", "5% discount"]},
        "Gold": {"min": 5001, "max": 15000, "color": "#D4AF37", "perks": ["Late checkout 2PM", "Priority support", "10% discount", "Birthday offer"]},
        "Platinum": {"min": 15001, "max": None, "color": "#E5E4E2", "perks": ["Room upgrade", "Late checkout 3PM", "Airport pickup", "15% discount", "Dedicated manager"]}
    }

    current_tier = user.get("tier_level", "Silver")
    current_points = user.get("loyalty_points", 0)

    # Determine next tier
    sorted_tiers = sorted(tiers.keys(), key=lambda x: tiers[x]["min"])
    next_tier = None
    for tier_name in sorted_tiers:
        tier = tiers[tier_name]
        if current_points < tier["min"]:
            next_tier = tier_name
            break

    conn.close()

    return render_template(
        "guest/loyalty.html",
        user=user,
        current_points=current_points,
        current_tier=current_tier,
        next_tier=next_tier,
        transactions=[dict(t) for t in transactions],
        tiers=tiers
    )


@guest_bp.route("/rooms")
def room_listing():
    """Browse available rooms"""
    conn = get_db()
    room_rows = conn.execute(
        "SELECT * FROM rooms WHERE is_active = 1 AND status = 'available' ORDER BY current_price"
    ).fetchall()
    total_rooms = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE is_active = 1"
    ).fetchone()[0]
    ratings_rows = conn.execute(
        """SELECT room_id, COALESCE(AVG(overall_rating), 0) as rating,
                  COUNT(*) as review_count
           FROM reviews
           GROUP BY room_id"""
    ).fetchall()
    conn.close()

    ratings_map = {
        r["room_id"]: {
            "rating": round(r["rating"] or 0, 1),
            "review_count": r["review_count"] or 0,
        }
        for r in ratings_rows
    }

    all_rooms = []
    for r in room_rows:
        rd = dict(r)
        # Normalize JSON fields for templates
        amenities_val = rd.get("amenities", "[]")
        if isinstance(amenities_val, list):
            rd["amenities"] = amenities_val
        else:
            try:
                rd["amenities"] = json.loads(amenities_val or "[]")
            except Exception:
                rd["amenities"] = []
        images_val = rd.get("images", "[]")
        if isinstance(images_val, list):
            rd["images"] = images_val
        else:
            try:
                rd["images"] = json.loads(images_val or "[]")
            except Exception:
                rd["images"] = []
        # Prefer local images for room cards
        room_type = rd.get("room_type")
        local_img = _local_room_image_path(room_type)
        rd["primary_image"] = url_for("static", filename=local_img)
        # Attach rating info for sorting/labels
        rating_info = ratings_map.get(rd.get("room_id"), {})
        rd["rating"] = rating_info.get("rating", 0)
        rd["review_count"] = rating_info.get("review_count", 0)
        all_rooms.append(rd)
    room_types = sorted(
        {r.get("room_type") for r in all_rooms if r.get("room_type")}
    )
    type_counts = {}
    for r in all_rooms:
        rt = r.get("room_type") or "Unknown"
        type_counts[rt] = type_counts.get(rt, 0) + 1

    available_count = len(all_rooms)
    occupancy_pct = (
        round(((total_rooms - available_count) / total_rooms) * 100, 1)
        if total_rooms
        else 0
    )

    guests_raw = request.args.get("guests", "").strip()
    try:
        guests = int(guests_raw) if guests_raw else ""
    except Exception:
        guests = ""

    filters = {
        "type": request.args.get("type", "").strip(),
        "check_in": request.args.get("check_in", "").strip(),
        "check_out": request.args.get("check_out", "").strip(),
        "guests": guests,
        "max_price": request.args.get("max_price", "").strip(),
        "sort": request.args.get("sort", "price_asc").strip() or "price_asc",
    }

    rooms = all_rooms
    if filters["type"]:
        rooms = [r for r in rooms if r.get("room_type") == filters["type"]]
    if filters["guests"]:
        rooms = [
            r for r in rooms if (r.get("max_guests") or 0) >= filters["guests"]
        ]
    if filters["max_price"]:
        try:
            max_price = float(filters["max_price"])
            rooms = [
                r for r in rooms if float(r.get("current_price") or 0) <= max_price
            ]
        except Exception:
            pass

    if filters["sort"] == "price_desc":
        rooms = sorted(
            rooms, key=lambda r: float(r.get("current_price") or 0), reverse=True
        )
    elif filters["sort"] == "rating":
        rooms = sorted(rooms, key=lambda r: float(r.get("rating") or 0), reverse=True)
    else:
        rooms = sorted(rooms, key=lambda r: float(r.get("current_price") or 0))

    return render_template(
        "public/rooms.html",
        rooms=rooms,
        filters=filters,
        room_types=room_types,
        type_counts=type_counts,
        occupancy_pct=occupancy_pct,
    )


@guest_bp.route("/rooms/<room_id>")
def room_detail(room_id):
    conn = get_db()
    room = conn.execute(
        "SELECT * FROM rooms WHERE room_id = ? AND is_active = 1",
        (room_id,),
    ).fetchone()
    if not room:
        conn.close()
        flash("Room not found or unavailable.", "danger")
        return redirect(url_for("guest.room_listing"))

    reviews = conn.execute(
        """SELECT rv.*, u.first_name, u.last_name
           FROM reviews rv
           JOIN users u ON rv.user_id = u.user_id
           WHERE rv.room_id = ?
           ORDER BY rv.created_at DESC
           LIMIT 20""",
        (room_id,),
    ).fetchall()
    conn.close()

    room_dict = dict(room)
    amenities_val = room_dict.get("amenities", "[]")
    if isinstance(amenities_val, list):
        room_dict["amenities"] = amenities_val
    else:
        try:
            room_dict["amenities"] = json.loads(amenities_val or "[]")
        except Exception:
            room_dict["amenities"] = []

    local_img = url_for(
        "static", filename=_local_room_image_path(room_dict.get("room_type"))
    )
    room_dict["primary_image"] = local_img
    room_dict["images"] = [local_img] * 4

    return render_template(
        "public/room_detail.html",
        room=room_dict,
        reviews=[dict(r) for r in reviews],
    )


@guest_bp.route("/download-invoice/<booking_id>")
@login_required
def download_invoice(booking_id):
    """Generates and downloads a mock GST invoice PDF"""
    user = get_current_user()
    conn = get_db()
    
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"])
    ).fetchone()
    
    if not booking:
        conn.close()
        flash("Invoice not found or unauthorized.", "danger")
        return redirect(url_for("guest.dashboard"))
        
    booking_dict = dict(booking)
    room = conn.execute("SELECT room_number, room_type FROM rooms WHERE room_id = ?", (booking_dict["room_id"],)).fetchone()
    if room:
        booking_dict["room_number"] = dict(room).get("room_number")
        booking_dict["room_type"] = dict(room).get("room_type")
        
    conn.close()
    
    try:
        from services.pdf_service import generate_gst_invoice
        from flask import send_file
        import os
        
        pdf_path = generate_gst_invoice(booking_dict, user)
        
        if pdf_path and os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True)
        else:
            flash("Failed to generate invoice.", "warning")
            return redirect(url_for("guest.dashboard"))
            
    except Exception as e:
        flash(f"Error generating invoice: {str(e)}", "danger")
        return redirect(url_for("guest.dashboard"))
