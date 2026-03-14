"""
Blissful Abodes - Guest Routes
Guest dashboard, room browsing, booking, reviews, loyalty
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
    send_file,
    current_app,
)
import uuid
import json
from datetime import datetime, timedelta
from functools import wraps
from models.database import get_db
from ml_models.models import (
    get_recommendation_model,
    get_pricing_engine,
    get_demand_model,
    get_cancellation_predictor,
    get_fraud_detector,
)
from services.email_service import (
    send_booking_confirmation,
    send_cancellation_email,
    send_review_request,
)
from services.pdf_service import generate_gst_invoice, generate_booking_qr
from services.payment_service import create_order, verify_payment, RAZORPAY_KEY_ID

guest_bp = Blueprint("guest", __name__)


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


def get_unread_notifications(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_status = 0",
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return count


@guest_bp.route("/guest/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    conn = get_db()

    # Stats
    today = datetime.now().strftime("%Y-%m-%d")

    upcoming = conn.execute(
        """SELECT b.*, r.room_type, r.amenities FROM bookings b 
                              JOIN rooms r ON b.room_id = r.room_id
                              WHERE b.user_id = ? AND b.check_in >= ? AND b.status = 'confirmed'
                              ORDER BY b.check_in ASC LIMIT 5""",
        (user["user_id"], today),
    ).fetchall()

    past_bks = conn.execute(
        """SELECT COUNT(*) FROM bookings WHERE user_id = ? AND status = 'completed' """,
        (user["user_id"],),
    ).fetchone()[0]

    total_spent = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) FROM bookings 
                                 WHERE user_id = ? AND status IN ('completed', 'confirmed') AND payment_status = 'paid' """,
        (user["user_id"],),
    ).fetchone()[0]

    notifications = conn.execute(
        """SELECT * FROM notifications WHERE user_id = ? 
                                   ORDER BY created_at DESC LIMIT 10""",
        (user["user_id"],),
    ).fetchall()

    unread_count = get_unread_notifications(user["user_id"])

    wishlist = conn.execute(
        """SELECT r.* FROM wishlists w JOIN rooms r ON w.room_id = r.room_id 
                               WHERE w.user_id = ?""",
        (user["user_id"],),
    ).fetchall()

    reviews = conn.execute(
        """SELECT v.*, r.room_number, r.room_type FROM reviews v 
                              JOIN rooms r ON v.room_id = r.room_id WHERE v.user_id = ? 
                              ORDER BY v.created_at DESC""",
        (user["user_id"],),
    ).fetchall()

    conn.close()

    # AI recommendations
    rec_model = get_recommendation_model()
    recommendations = rec_model.get_recommendations(user["user_id"], n=4)

    # Get recommended rooms from DB
    rec_rooms = []
    conn = get_db()
    for rec in recommendations[:4]:
        rm = conn.execute(
            'SELECT * FROM rooms WHERE room_type = ? AND status = "available" LIMIT 1',
            (rec["room_type"],),
        ).fetchone()
        if rm:
            rm_dict = dict(rm)
            rm_dict["match_score"] = rec["match_score"]
            rm_dict["reason"] = rec["reason"]
            rm_dict["amenities"] = json.loads(rm_dict.get("amenities", "[]"))
            rec_rooms.append(rm_dict)
    conn.close()

    # Tier info
    tiers = {"Silver": 5000, "Gold": 15000, "Platinum": None}
    current_tier = user.get("tier_level", "Silver")
    next_tier = {"Silver": "Gold", "Gold": "Platinum", "Platinum": None}.get(
        current_tier
    )
    next_threshold = tiers.get(next_tier, 0) if next_tier else 0
    tier_progress = (
        min(100, int(user.get("loyalty_points", 0) / max(next_threshold, 1) * 100))
        if next_threshold
        else 100
    )

    upcoming_list = [dict(b) for b in upcoming]
    for b in upcoming_list:
        try:
            ci = datetime.strptime(b["check_in"], "%Y-%m-%d")
            b["days_until"] = (ci - datetime.now()).days
            b["amenities"] = json.loads(b.get("amenities", "[]"))
        except Exception:
            b["days_until"] = 0

    return render_template(
        "guest/dashboard.html",
        user=user,
        upcoming_bookings=upcoming_list,
        past_bookings_count=past_bks,
        total_spent=total_spent,
        notifications=[dict(n) for n in notifications],
        unread_count=unread_count,
        wishlist=[dict(w) for w in wishlist],
        reviews=[dict(r) for r in reviews],
        recommended_rooms=rec_rooms,
        current_tier=current_tier,
        next_tier=next_tier,
        tier_progress=tier_progress,
        next_threshold=next_threshold,
    )


@guest_bp.route("/rooms")
def room_listing():
    room_type = request.args.get("type", "")
    check_in = request.args.get("check_in", "")
    check_out = request.args.get("check_out", "")
    guests = safe_int(request.args.get("guests", 1), 1)
    max_price = request.args.get("max_price", "")
    sort_by = request.args.get("sort", "price_asc")

    conn = get_db()
    query = 'SELECT * FROM rooms WHERE is_active = 1 AND status = "available"'
    params = []

    if room_type:
        query += " AND room_type = ?"
        params.append(room_type)
    if guests:
        query += " AND max_guests >= ?"
        params.append(guests)
    if max_price:
        query += " AND current_price <= ?"
        params.append(float(max_price))

    if sort_by == "price_asc":
        query += " ORDER BY current_price ASC"
    elif sort_by == "price_desc":
        query += " ORDER BY current_price DESC"
    elif sort_by == "rating":
        query += " ORDER BY current_price DESC"

    rooms = conn.execute(query, params).fetchall()

    # Get occupancy for scarcity indicators
    occupied_count = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
    ).fetchone()[0]
    total_count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    occupancy_pct = round(occupied_count / max(total_count, 1) * 100, 1)

    # Room counts by type for availability indicators
    type_counts = {}
    for rt in ["Single", "Double", "Family", "Couple", "VIP Suite"]:
        avail = conn.execute(
            "SELECT COUNT(*) FROM rooms WHERE room_type=? AND status='available'", (rt,)
        ).fetchone()[0]
        type_counts[rt] = avail

    conn.close()

    pricing_engine = get_pricing_engine()
    days_until = None
    if check_in:
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            days_until = (ci.date() - datetime.now().date()).days
        except Exception:
            days_until = None
    rooms_list = []
    photo_map = {
        "Single": "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg",
        "Double": "https://cdn.pixabay.com/photo/2020/12/24/19/10/hotel-room-5858068_1280.jpg",
        "Family": "https://cdn.pixabay.com/photo/2020/12/24/19/11/hotel-room-5858069_1280.jpg",
        "Couple": "https://cdn.pixabay.com/photo/2021/02/07/20/08/luxury-5992539_1280.jpg",
        "VIP Suite": "https://cdn.pixabay.com/photo/2019/12/26/16/51/luxury-suite-4720815_1280.jpg",
    }
    svg_map = {
        "Single": "single.svg",
        "Double": "double.svg",
        "Family": "family.svg",
        "Couple": "couple.svg",
        "VIP Suite": "vip.svg",
    }
    for r in rooms:
        rd = dict(r)
        rd["amenities"] = json.loads(rd.get("amenities", "[]"))
        rd["images"] = json.loads(rd.get("images", "[]"))
        placeholder = None
        if rd["images"] and isinstance(rd["images"], list):
            placeholder = rd["images"][0]
        svg_fallback = f'/static/images/rooms/{svg_map.get(rd["room_type"], "single.svg")}'
        photo_primary = photo_map.get(rd["room_type"], svg_fallback)
        if placeholder and isinstance(placeholder, str):
            if placeholder.startswith("/static/images/rooms/"):
                rd["primary_image"] = photo_primary
                rd["images"] = [photo_primary, svg_fallback]
            else:
                rd["primary_image"] = placeholder
        else:
            rd["primary_image"] = photo_primary

        # Dynamic pricing
        if check_in:
            try:
                pricing = pricing_engine.calculate_price(
                    rd["room_type"],
                    check_in,
                    occupancy_pct,
                    days_until,
                    base_price=rd.get("current_price"),
                )
                rd["dynamic_price"] = pricing["final_price"]
                rd["price_rules"] = pricing["rules_applied"]
            except Exception:
                rd["dynamic_price"] = rd["current_price"]
                rd["price_rules"] = []
        else:
            rd["dynamic_price"] = rd["current_price"]
            rd["price_rules"] = []

        rd["available_count"] = type_counts.get(rd["room_type"], 0)
        rooms_list.append(rd)

    return render_template(
        "public/rooms.html",
        rooms=rooms_list,
        occupancy_pct=occupancy_pct,
        type_counts=type_counts,
        filters={
            "type": room_type,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "max_price": max_price,
        },
        room_types=["Single", "Double", "Family", "Couple", "VIP Suite"],
    )


@guest_bp.route("/room/<room_id>")
def room_detail(room_id):
    conn = get_db()
    room = conn.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,)).fetchone()
    if not room:
        flash("Room not found.", "danger")
        return redirect(url_for("guest.room_listing"))

    reviews = conn.execute(
        """SELECT rv.*, u.first_name, u.last_name FROM reviews rv 
                              JOIN users u ON rv.user_id = u.user_id 
                              WHERE rv.room_id = ? ORDER BY rv.created_at DESC LIMIT 10""",
        (room_id,),
    ).fetchall()

    avg_rating = conn.execute(
        "SELECT AVG(overall_rating) FROM reviews WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    review_count = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    conn.close()

    room_dict = dict(room)
    room_dict["amenities"] = json.loads(room_dict.get("amenities", "[]"))
    room_dict["images"] = json.loads(room_dict.get("images", "[]"))
    photo_map = {
        "Single": "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg",
        "Double": "https://cdn.pixabay.com/photo/2020/12/24/19/10/hotel-room-5858068_1280.jpg",
        "Family": "https://cdn.pixabay.com/photo/2020/12/24/19/11/hotel-room-5858069_1280.jpg",
        "Couple": "https://cdn.pixabay.com/photo/2021/02/07/20/08/luxury-5992539_1280.jpg",
        "VIP Suite": "https://cdn.pixabay.com/photo/2019/12/26/16/51/luxury-suite-4720815_1280.jpg",
    }
    svg_map = {
        "Single": "single.svg",
        "Double": "double.svg",
        "Family": "family.svg",
        "Couple": "couple.svg",
        "VIP Suite": "vip.svg",
    }
    svg_fallback = f'/static/images/rooms/{svg_map.get(room_dict["room_type"], "single.svg")}'
    photo_primary = photo_map.get(room_dict["room_type"], svg_fallback)
    if room_dict.get("images") and isinstance(room_dict["images"], list):
        first_img = room_dict["images"][0]
        if isinstance(first_img, str) and first_img.startswith("/static/images/rooms/"):
            room_dict["images"] = [photo_primary, svg_fallback]
            room_dict["primary_image"] = photo_primary
        else:
            room_dict["primary_image"] = first_img
    else:
        room_dict["images"] = [photo_primary, svg_fallback]
        room_dict["primary_image"] = photo_primary
    room_dict["avg_rating"] = round(avg_rating, 1) if avg_rating else 0
    room_dict["review_count"] = review_count

    return render_template(
        "public/room_detail.html", room=room_dict, reviews=[dict(r) for r in reviews]
    )


@guest_bp.route("/book/<room_id>", methods=["GET", "POST"])
@login_required
def book_room(room_id):
    if session.get("user_role") != "guest":
        flash("Only guest accounts can book rooms.", "warning")
        return redirect(url_for("guest.room_listing"))

    conn = get_db()
    room = conn.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,)).fetchone()
    if not room:
        flash("Room not found.", "danger")
        return redirect(url_for("guest.room_listing"))
    conn.close()

    room_dict = dict(room)
    room_dict["amenities"] = json.loads(room_dict.get("amenities", "[]"))

    if request.method == "POST":
        if room_dict.get("status") != "available":
            flash("This room is not available right now.", "danger")
            return render_template("guest/book_room.html", room=room_dict)
        check_in = request.form.get("check_in")
        check_out = request.form.get("check_out")
        num_guests = safe_int(request.form.get("num_guests", 1), 1)
        special_requests = request.form.get("special_requests", "")
        coupon_code = request.form.get("coupon_code", "").upper()
        loyalty_points = safe_int(request.form.get("loyalty_points", 0), 0)
        payment_method = request.form.get("payment_method", "UPI")

        # Validation
        if not check_in or not check_out:
            flash("Please select check-in and check-out dates.", "danger")
            return render_template("guest/book_room.html", room=room_dict)

        ci = datetime.strptime(check_in, "%Y-%m-%d")
        co = datetime.strptime(check_out, "%Y-%m-%d")

        if ci < datetime.now():
            flash("Check-in date cannot be in the past.", "danger")
            return render_template("guest/book_room.html", room=room_dict)

        if co <= ci:
            flash("Check-out must be after check-in.", "danger")
            return render_template("guest/book_room.html", room=room_dict)

        nights = (co - ci).days
        days_until = (ci.date() - datetime.now().date()).days

        # Calculate price with dynamic pricing
        pricing_engine = get_pricing_engine()
        conn = get_db()
        occ = conn.execute(
            "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
        ).fetchone()[0]
        total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        occ_pct = round(occ / max(total_rooms, 1) * 100, 1)
        conn.close()

        pricing = pricing_engine.calculate_price(
            room_dict["room_type"],
            check_in,
            occ_pct,
            days_until,
            base_price=room_dict.get("current_price"),
        )
        base_per_night = pricing["final_price"]
        base_amount = base_per_night * nights

        user = get_current_user()

        # Coupon
        discount_amount = 0
        if coupon_code:
            eligibility = offers_eligibility(user["user_id"])
            if not eligibility["eligible"]:
                coupon_code = ""
                discount_amount = 0
                if eligibility["first_booking_required"] and not eligibility[
                    "has_first_booking"
                ]:
                    flash("Offers unlock after your first paid booking.", "warning")
                elif eligibility["loyalty_points"] < eligibility["min_points"]:
                    remaining = eligibility["min_points"] - eligibility["loyalty_points"]
                    flash(
                        f"Earn {remaining} more loyalty points to unlock offers.",
                        "warning",
                    )
            else:
                conn = get_db()
                coupon = conn.execute(
                    "SELECT * FROM coupons WHERE code = ? AND is_active = 1",
                    (coupon_code,),
                ).fetchone()
                conn.close()
                if coupon:
                    coupon = dict(coupon)
                    if coupon["used_count"] < coupon["max_uses"]:
                        if coupon["discount_type"] == "percentage":
                            discount_amount = (
                                base_amount * coupon["discount_value"] / 100
                            )
                        else:
                            discount_amount = coupon["discount_value"]
                        discount_amount = min(
                            discount_amount, base_amount * 0.5
                        )  # Max 50% discount

        # Loyalty points redemption
        loyalty_discount = 0
        pts_to_use = min(loyalty_points, user.get("loyalty_points", 0))
        loyalty_discount = pts_to_use / 10  # 1000 pts = â‚¹100

        taxable = max(0, base_amount - discount_amount - loyalty_discount)
        gst = taxable * 0.18
        total_amount = taxable + gst

        # Fraud detection
        fraud_detector = get_fraud_detector()
        fraud_result = fraud_detector.predict(
            {
                "total_amount": total_amount,
                "payment_method": payment_method,
                "email": user["email"],
                "is_new_user": user.get("loyalty_points", 0) == 0,
                "num_guests": num_guests,
                "user_id": user["user_id"],
                "room_id": room_id,
                "room_type": room_dict.get("room_type"),
                "room_capacity": room_dict.get("max_guests"),
                "check_in": check_in,
                "check_out": check_out,
                "created_at": datetime.now().isoformat(),
            }
        )

        if fraud_result["should_block"]:
            flash(
                "Your booking could not be processed. Please contact support.", "danger"
            )
            return render_template("guest/book_room.html", room=room_dict)

        # Cancellation prediction
        cancel_pred = get_cancellation_predictor()
        cancel_result = cancel_pred.predict(
            {
                "days_until_checkin": days_until,
                "room_type": room_dict["room_type"],
                "total_amount": total_amount,
                "payment_method": payment_method,
                "user_id": user["user_id"],
                "room_id": room_id,
                "check_in": check_in,
                "check_out": check_out,
                "created_at": datetime.now().isoformat(),
            }
        )

        # Create booking
        booking_id = (
            f"BK{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        )
        pts_earned = int(base_amount / 10)
        is_cash = str(payment_method).lower() in ["cash", "cash_at_desk", "cash at desk"]
        status = "confirmed" if is_cash else "pending"
        payment_status = "paid" if is_cash else "pending"
        is_flagged = 1 if fraud_result.get("is_suspicious") else 0

        conn = get_db()
        conn.execute(
            """INSERT INTO bookings 
            (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
             base_amount, gst_amount, discount_amount, total_amount, coupon_code,
             loyalty_points_used, loyalty_points_earned, status, payment_status, payment_method,
             special_requests, fraud_score, is_flagged, cancellation_probability)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                booking_id,
                user["user_id"],
                room_id,
                room_dict["room_number"],
                check_in,
                check_out,
                num_guests,
                base_amount,
                gst,
                discount_amount + loyalty_discount,
                total_amount,
                coupon_code or None,
                pts_to_use,
                pts_earned,
                status,
                payment_status,
                payment_method,
                special_requests or "",
                fraud_result["fraud_score"],
                is_flagged,
                cancel_result["cancellation_probability"],
            ),
        )

        # Update room status
        conn.execute(
            "UPDATE rooms SET status = ? WHERE room_id = ?",
            ("occupied" if is_cash else "reserved", room_id),
        )

        # Add notification for guest
        conn.execute(
            """INSERT INTO notifications (notification_id, user_id, title, message, notification_type, action_url)
                       VALUES (?, ?, ?, ?, 'info', ?)""",
            (
                str(uuid.uuid4()),
                user["user_id"],
                "Booking Created",
                f'Room {room_dict["room_number"]} reserved for {check_in} - {check_out}.',
                f"/guest/booking/{booking_id}",
            ),
        )

        # Flag suspicious bookings for admin
        if is_flagged:
            admins = conn.execute(
                "SELECT user_id FROM users WHERE role IN ('admin','superadmin') AND is_active = 1"
            ).fetchall()
            for a in admins:
                conn.execute(
                    """INSERT INTO notifications (notification_id, user_id, title, message, notification_type, action_url)
                               VALUES (?, ?, ?, ?, 'warning', ?)""",
                    (
                        str(uuid.uuid4()),
                        a["user_id"],
                        "Suspicious Booking",
                        f"Booking {booking_id} flagged by fraud detection (score {fraud_result['fraud_score']}).",
                        "/admin/bookings",
                    ),
                )

        conn.commit()
        conn.close()

        if is_cash:
            # Update user loyalty points and coupon usage immediately
            conn = get_db()
            new_pts = user.get("loyalty_points", 0) - pts_to_use + pts_earned
            conn.execute(
                "UPDATE users SET loyalty_points = ? WHERE user_id = ?",
                (new_pts, user["user_id"]),
            )
            if coupon_code and discount_amount > 0:
                conn.execute(
                    "UPDATE coupons SET used_count = used_count + 1 WHERE code = ?",
                    (coupon_code,),
                )
            conn.commit()
            conn.close()

            # Generate QR code
            try:
                qr_path = generate_booking_qr(booking_id)
                conn = get_db()
                conn.execute(
                    "UPDATE bookings SET qr_code_path = ? WHERE booking_id = ?",
                    (qr_path, booking_id),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            # Send confirmation email
            try:
                invoice_path = generate_gst_invoice(
                    {
                        "booking_id": booking_id,
                        "room_number": room_dict["room_number"],
                        "room_type": room_dict["room_type"],
                        "check_in": check_in,
                        "check_out": check_out,
                        "num_guests": num_guests,
                        "base_amount": base_amount,
                        "gst_amount": gst,
                        "discount_amount": discount_amount + loyalty_discount,
                        "total_amount": total_amount,
                    },
                    user,
                )
                send_booking_confirmation(
                    user["email"],
                    user["first_name"],
                    {
                        "booking_id": booking_id,
                        "room_number": room_dict["room_number"],
                        "room_type": room_dict["room_type"],
                        "check_in": check_in,
                        "check_out": check_out,
                        "num_guests": num_guests,
                        "total_amount": total_amount,
                    },
                    invoice_path,
                )
            except Exception:
                pass

            flash(
                f"Room booked successfully! Booking ID: {booking_id} | You earned {pts_earned} loyalty points!",
                "success",
            )
            return redirect(url_for("guest.booking_detail", booking_id=booking_id))

        flash(
            "Booking created. Please complete payment to confirm your reservation.",
            "info",
        )
        return redirect(url_for("guest.payment_page", booking_id=booking_id))

    return render_template("guest/book_room.html", room=room_dict)


@guest_bp.route("/guest/bookings")
@login_required
def my_bookings():
    user = get_current_user()
    conn = get_db()
    bookings = conn.execute(
        """SELECT b.*, r.room_type, r.room_number as rnum FROM bookings b
                               JOIN rooms r ON b.room_id = r.room_id
                               WHERE b.user_id = ? ORDER BY b.created_at DESC""",
        (user["user_id"],),
    ).fetchall()
    conn.close()
    return render_template(
        "guest/bookings.html", bookings=[dict(b) for b in bookings], user=user
    )


@guest_bp.route("/guest/booking/<booking_id>")
@login_required
def booking_detail(booking_id):
    user = get_current_user()
    conn = get_db()
    booking = conn.execute(
        """SELECT b.*, r.room_type, r.amenities, r.images FROM bookings b
                              JOIN rooms r ON b.room_id = r.room_id
                              WHERE b.booking_id = ? AND b.user_id = ?""",
        (booking_id, user["user_id"]),
    ).fetchone()
    conn.close()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("guest.my_bookings"))

    booking_dict = dict(booking)
    booking_dict["amenities"] = json.loads(booking_dict.get("amenities", "[]"))

    try:
        ci = datetime.strptime(booking_dict["check_in"], "%Y-%m-%d")
        co = datetime.strptime(booking_dict["check_out"], "%Y-%m-%d")
        booking_dict["nights"] = (co - ci).days
        booking_dict["days_until"] = (ci - datetime.now()).days
    except Exception:
        booking_dict["nights"] = 1
        booking_dict["days_until"] = 0

    return render_template("guest/booking_detail.html", booking=booking_dict, user=user)


@guest_bp.route("/guest/payment/<booking_id>")
@login_required
def payment_page(booking_id):
    user = get_current_user()
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found.", "danger")
        return redirect(url_for("guest.my_bookings"))

    booking = dict(booking)
    if booking.get("payment_status") == "paid":
        conn.close()
        return redirect(url_for("guest.booking_detail", booking_id=booking_id))

    order_id = booking.get("razorpay_order_id")
    if not order_id:
        order_resp = create_order(booking["total_amount"], booking_id)
        if not order_resp.get("success"):
            conn.close()
            flash("Payment gateway unavailable. Please try again later.", "danger")
            return redirect(url_for("guest.booking_detail", booking_id=booking_id))
        order_id = order_resp["order"]["id"]
        conn.execute(
            "UPDATE bookings SET razorpay_order_id = ? WHERE booking_id = ?",
            (order_id, booking_id),
        )
        conn.commit()

    conn.close()
    demo_mode = str(order_id).startswith("order_demo") or RAZORPAY_KEY_ID.startswith(
        "rzp_test_placeholder"
    )
    return render_template(
        "guest/payment.html",
        booking=booking,
        order_id=order_id,
        amount_paise=int(booking["total_amount"] * 100),
        razorpay_key_id=RAZORPAY_KEY_ID,
        demo_mode=demo_mode,
    )


@guest_bp.route("/api/payment/verify", methods=["POST"])
@login_required
def verify_payment_api():
    data = request.json or {}
    booking_id = data.get("booking_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature", "")

    user = get_current_user()
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()
    if not booking:
        conn.close()
        return jsonify({"success": False, "message": "Booking not found"}), 404

    booking = dict(booking)
    if booking.get("payment_status") == "paid":
        conn.close()
        return jsonify({"success": True, "message": "Payment already completed"})

    order_id = razorpay_order_id or booking.get("razorpay_order_id", "")
    if not verify_payment(order_id, razorpay_payment_id, razorpay_signature):
        conn.close()
        return jsonify({"success": False, "message": "Payment verification failed"}), 400

    # Mark paid
    conn.execute(
        """UPDATE bookings 
           SET payment_status = 'paid', status = 'confirmed', payment_id = ?, razorpay_order_id = ?, updated_at = ?
           WHERE booking_id = ?""",
        (
            razorpay_payment_id or "",
            order_id,
            datetime.now().isoformat(),
            booking_id,
        ),
    )

    # Update room status to occupied
    conn.execute(
        "UPDATE rooms SET status = 'occupied' WHERE room_id = ?",
        (booking["room_id"],),
    )

    # Apply loyalty points and coupons
    new_pts = user.get("loyalty_points", 0) - booking.get(
        "loyalty_points_used", 0
    ) + booking.get("loyalty_points_earned", 0)
    conn.execute(
        "UPDATE users SET loyalty_points = ? WHERE user_id = ?",
        (new_pts, user["user_id"]),
    )
    if booking.get("coupon_code") and booking.get("discount_amount", 0) > 0:
        conn.execute(
            "UPDATE coupons SET used_count = used_count + 1 WHERE code = ?",
            (booking["coupon_code"],),
        )

    # Generate QR code
    try:
        qr_path = generate_booking_qr(booking_id)
        conn.execute(
            "UPDATE bookings SET qr_code_path = ? WHERE booking_id = ?",
            (qr_path, booking_id),
        )
    except Exception:
        pass

    # Add notification
    conn.execute(
        """INSERT INTO notifications (notification_id, user_id, title, message, notification_type, action_url)
                   VALUES (?, ?, ?, ?, 'success', ?)""",
        (
            str(uuid.uuid4()),
            user["user_id"],
            "Payment Received",
            f"Payment received for booking {booking_id}. Your stay is confirmed.",
            f"/guest/booking/{booking_id}",
        ),
    )

    conn.commit()
    conn.close()

    # Send confirmation email with invoice
    try:
        room = None
        conn = get_db()
        room = conn.execute(
            "SELECT room_type, room_number FROM rooms WHERE room_id = ?",
            (booking["room_id"],),
        ).fetchone()
        conn.close()
        if room:
            booking["room_type"] = room["room_type"]
            booking["room_number"] = room["room_number"]
        invoice_path = generate_gst_invoice(booking, user)
        send_booking_confirmation(
            user["email"],
            user["first_name"],
            {
                "booking_id": booking_id,
                "room_number": booking.get("room_number", ""),
                "room_type": booking.get("room_type", ""),
                "check_in": booking.get("check_in"),
                "check_out": booking.get("check_out"),
                "num_guests": booking.get("num_guests"),
                "total_amount": booking.get("total_amount"),
            },
            invoice_path,
        )
    except Exception:
        pass

    return jsonify({"success": True})


@guest_bp.route("/guest/cancel-booking/<booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    user = get_current_user()
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user["user_id"]),
    ).fetchone()

    if not booking:
        conn.close()
        return jsonify({"success": False, "message": "Booking not found"})

    booking = dict(booking)
    if booking["status"] in ["cancelled", "completed"]:
        conn.close()
        return jsonify({"success": False, "message": "Cannot cancel this booking"})

    # Calculate refund
    ci = datetime.strptime(booking["check_in"], "%Y-%m-%d")
    days_until = (ci - datetime.now()).days

    if days_until > 48:
        refund_pct = 1.0
    elif days_until > 24:
        refund_pct = 0.5
    else:
        refund_pct = 0.0

    if booking.get("payment_status") != "paid":
        refund_pct = 0.0
    refund_amount = booking["total_amount"] * refund_pct

    conn.execute(
        "UPDATE bookings SET status = 'cancelled', updated_at = ? WHERE booking_id = ?",
        (datetime.now().isoformat(), booking_id),
    )
    conn.execute(
        "UPDATE rooms SET status = 'available' WHERE room_id = ?", (booking["room_id"],)
    )

    # Return loyalty points
    if booking.get("loyalty_points_used", 0) > 0 and booking.get("payment_status") == "paid":
        conn.execute(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id = ?",
            (booking["loyalty_points_used"], user["user_id"]),
        )

    conn.commit()
    conn.close()

    try:
        send_cancellation_email(
            user["email"], user["first_name"], booking, refund_amount
        )
    except Exception:
        pass

    return jsonify(
        {"success": True, "refund": refund_amount, "refund_pct": int(refund_pct * 100)}
    )


@guest_bp.route("/guest/invoice/<booking_id>")
@login_required
def download_invoice(booking_id):
    user = get_current_user()
    conn = get_db()
    booking = conn.execute(
        """SELECT b.*, r.room_type FROM bookings b JOIN rooms r ON b.room_id = r.room_id 
                              WHERE b.booking_id = ? AND b.user_id = ?""",
        (booking_id, user["user_id"]),
    ).fetchone()
    conn.close()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("guest.my_bookings"))

    try:
        invoice_path = generate_gst_invoice(dict(booking), user)
        return send_file(
            invoice_path, as_attachment=True, download_name=f"Invoice_{booking_id}.pdf"
        )
    except Exception as e:
        flash(f"Invoice generation error: {str(e)}", "warning")
        return redirect(url_for("guest.booking_detail", booking_id=booking_id))


@guest_bp.route("/guest/review/<booking_id>", methods=["GET", "POST"])
@login_required
def write_review(booking_id):
    user = get_current_user()
    conn = get_db()
    booking = conn.execute(
        """SELECT b.*, r.room_type FROM bookings b JOIN rooms r ON b.room_id = r.room_id 
                              WHERE b.booking_id = ? AND b.user_id = ? AND b.status = 'completed' """,
        (booking_id, user["user_id"]),
    ).fetchone()

    if request.method == "POST":
        rating = float(request.form.get("rating", 5))
        comment = request.form.get("comment", "").strip()
        cleanliness = float(request.form.get("cleanliness", 5))
        staff_r = float(request.form.get("staff", 5))
        location = float(request.form.get("location", 5))
        value = float(request.form.get("value", 5))
        amenities_r = float(request.form.get("amenities_rating", 5))

        # Sentiment analysis
        from ml_models.models import get_sentiment_analyzer

        sentiment = get_sentiment_analyzer()
        analysis = sentiment.analyze(comment)

        if booking:
            room_id = booking["room_id"]
        else:
            conn.close()
            flash("Cannot review this booking.", "danger")
            return redirect(url_for("guest.my_bookings"))

        review_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO reviews 
            (review_id, booking_id, user_id, room_id, overall_rating, comment,
             verified_stay, sentiment, sentiment_score,
             cleanliness_rating, staff_rating, location_rating, value_rating, amenities_rating)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)""",
            (
                review_id,
                booking_id,
                user["user_id"],
                room_id,
                rating,
                comment,
                analysis["sentiment"],
                analysis["score"],
                cleanliness,
                staff_r,
                location,
                value,
                amenities_r,
            ),
        )

        # Award bonus points
        conn.execute(
            "UPDATE users SET loyalty_points = loyalty_points + 50 WHERE user_id = ?",
            (user["user_id"],),
        )

        conn.commit()
        conn.close()

        flash("Review submitted! You earned 50 bonus loyalty points! ðŸŒŸ", "success")
        return redirect(url_for("guest.dashboard"))

    booking_dict = dict(booking) if booking else None
    conn.close()
    return render_template("guest/write_review.html", booking=booking_dict, user=user)


@guest_bp.route("/guest/loyalty")
@login_required
def loyalty():
    user = get_current_user()
    conn = get_db()
    transactions = conn.execute(
        """SELECT * FROM loyalty_transactions WHERE user_id = ? 
                                   ORDER BY created_at DESC LIMIT 20""",
        (user["user_id"],),
    ).fetchall()
    conn.close()

    tiers = {
        "Silver": {
            "min": 0,
            "max": 5000,
            "color": "#C0C0C0",
            "perks": ["Priority support", "5% discount"],
        },
        "Gold": {
            "min": 5001,
            "max": 15000,
            "color": "#D4AF37",
            "perks": [
                "Late checkout 2PM",
                "Priority support",
                "10% discount",
                "Birthday offer",
            ],
        },
        "Platinum": {
            "min": 15001,
            "max": None,
            "color": "#E5E4E2",
            "perks": [
                "Room upgrade",
                "Late checkout 3PM",
                "Airport pickup",
                "15% discount",
                "Dedicated manager",
            ],
        },
    }

    return render_template(
        "guest/loyalty.html",
        user=user,
        transactions=[dict(t) for t in transactions],
        tiers=tiers,
    )


@guest_bp.route("/api/validate-coupon", methods=["POST"])
@login_required
def validate_coupon():
    code = request.json.get("code", "").upper()
    amount = float(request.json.get("amount", 0))

    eligibility = offers_eligibility(session["user_id"])
    if not eligibility["eligible"]:
        if eligibility["first_booking_required"] and not eligibility["has_first_booking"]:
            return jsonify(
                {
                    "valid": False,
                    "message": "Offers unlock after your first paid booking.",
                }
            )
        remaining = eligibility["min_points"] - eligibility["loyalty_points"]
        return jsonify(
            {
                "valid": False,
                "message": f"Earn {remaining} more loyalty points to unlock offers.",
            }
        )

    conn = get_db()
    coupon = conn.execute(
        "SELECT * FROM coupons WHERE code = ? AND is_active = 1", (code,)
    ).fetchone()
    conn.close()

    if not coupon:
        return jsonify({"valid": False, "message": "Invalid coupon code"})

    coupon = dict(coupon)
    if coupon["used_count"] >= coupon["max_uses"]:
        return jsonify({"valid": False, "message": "Coupon limit reached"})

    if coupon["valid_until"] and coupon["valid_until"] < datetime.now().strftime(
        "%Y-%m-%d"
    ):
        return jsonify({"valid": False, "message": "Coupon has expired"})

    if amount < coupon.get("min_booking_amount", 0):
        return jsonify(
            {
                "valid": False,
                "message": f'Minimum booking amount: INR {coupon["min_booking_amount"]:,.0f}',
            }
        )

    if coupon["discount_type"] == "percentage":
        discount = amount * coupon["discount_value"] / 100
    else:
        discount = coupon["discount_value"]

    return jsonify(
        {
            "valid": True,
            "discount_type": coupon["discount_type"],
            "discount_value": coupon["discount_value"],
            "discount_amount": round(discount, 0),
            "message": f"Coupon applied! You save INR {discount:,.0f}",
        }
    )


@guest_bp.route("/api/notifications/mark-read", methods=["POST"])
@login_required
def mark_notifications_read():
    user_id = session["user_id"]
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET read_status = 1 WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@guest_bp.route("/api/wishlist/toggle", methods=["POST"])
@login_required
def toggle_wishlist():
    room_id = request.json.get("room_id")
    user_id = session["user_id"]
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM wishlists WHERE user_id = ? AND room_id = ?", (user_id, room_id)
    ).fetchone()
    if existing:
        conn.execute(
            "DELETE FROM wishlists WHERE user_id = ? AND room_id = ?",
            (user_id, room_id),
        )
        action = "removed"
    else:
        conn.execute(
            "INSERT INTO wishlists (user_id, room_id) VALUES (?, ?)", (user_id, room_id)
        )
        action = "added"
    conn.commit()
    conn.close()
    return jsonify({"success": True, "action": action})

