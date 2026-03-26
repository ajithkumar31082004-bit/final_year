"""
Blissful Abodes Hotel Management System
Main Flask Application Entry Point
"""

import os
from datetime import datetime, timedelta
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    jsonify,
    request,
    flash,
)
from flask_wtf.csrf import CSRFProtect
from config import config
import time


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    CSRFProtect(app)

    # Initialize DB
    from models.database import init_db

    with app.app_context():
        init_db()
        # Seed database on first run
        from models.database import get_db

        conn = get_db()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        if user_count == 0:
            from models.seed import seed_all

            seed_all()

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.guest import guest_bp
    from routes.staff import staff_bp
    from routes.manager import manager_bp
    from routes.admin import admin_bp
    from routes.superadmin import superadmin_bp
    from routes.agent import agent_bp
    from routes.chatbot import chatbot_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(guest_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(chatbot_bp)

    # DB teardown
    from models.database import close_db

    @app.teardown_appcontext
    def _teardown_db(error=None):
        close_db(error)

    # Context processor - inject user data to all templates
    @app.context_processor
    def inject_globals():
        from models.database import get_db

        user_data = None
        unread_notifications = 0
        notifications = []

        if "user_id" in session:
            try:
                cache = session.get("_ui_cache") or {}
                now = time.time()
                cached_user_id = cache.get("user_id")
                cached_at = cache.get("ts", 0)
                if cached_user_id == session["user_id"] and (now - cached_at) < 30:
                    user_data = cache.get("user")
                    unread_notifications = cache.get("unread", 0)
                    notifications = cache.get("notifications", [])
                else:
                    conn = get_db()
                    user_data = conn.execute(
                        "SELECT * FROM users WHERE user_id = ?", (session["user_id"],)
                    ).fetchone()
                    if user_data:
                        unread_notifications = conn.execute(
                            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_status = 0",
                            (session["user_id"],),
                        ).fetchone()[0]
                        notifications = conn.execute(
                            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                            (session["user_id"],),
                        ).fetchall()
                        user_data = dict(user_data)
                        notifications = [dict(n) for n in notifications]
                        user_data["notifications_list"] = notifications
                        session["_ui_cache"] = {
                            "user_id": session["user_id"],
                            "ts": now,
                            "user": user_data,
                            "unread": unread_notifications,
                            "notifications": notifications,
                        }
                    conn.close()
            except Exception:
                app.logger.exception("Failed to build context processor data")

        return {
            "current_user": user_data,
            "unread_notifications": unread_notifications,
            "hotel_name": "Blissful Abodes Chennai",
            "hotel_phone": "+91 44 2345 6789",
            "hotel_email": "info@blissfulabodes.com",
            "current_year": datetime.now().year,
            "now": datetime.now(),
            "google_maps_api_key": app.config.get("GOOGLE_MAPS_API_KEY", ""),
        }

    # Main routes
    @app.route("/")
    def index():
        from models.database import get_db
        import json

        conn = get_db()
        featured_rooms = conn.execute(
            "SELECT * FROM rooms WHERE status != 'out_of_service' ORDER BY current_price DESC LIMIT 6"
        ).fetchall()
        reviews = conn.execute(
            "SELECT rv.*, u.first_name, u.last_name FROM reviews rv JOIN users u ON rv.user_id = u.user_id WHERE rv.featured = 1 OR rv.overall_rating >= 4 ORDER BY rv.overall_rating DESC LIMIT 6"
        ).fetchall()
        stats = {
            "rooms": conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0],
            "bookings": conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE payment_status = 'paid'"
            ).fetchone()[0],
            "guests": conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'guest'"
            ).fetchone()[0],
            "rating": round(
                conn.execute(
                    "SELECT COALESCE(AVG(overall_rating), 4.7) FROM reviews"
                ).fetchone()[0],
                1,
            ),
        }
        conn.close()

        rooms_list = []
        photo_map = {
            "Single": "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg",
            "Double": "https://cdn.pixabay.com/photo/2020/12/24/19/10/hotel-room-5858068_1280.jpg",
            "Family": "https://cdn.pixabay.com/photo/2020/12/24/19/11/hotel-room-5858069_1280.jpg",
            "Couple": "https://cdn.pixabay.com/photo/2021/02/07/20/08/luxury-5992539_1280.jpg",
            "VIP Suite": "https://cdn.pixabay.com/photo/2019/12/26/16/51/luxury-suite-4720815_1280.jpg",
        }
        fallback_map = {
            "Single": "single.jpg",
            "Double": "double.jpg",
            "Family": "family.jpg",
            "Couple": "couple.jpg",
            "VIP Suite": "vip.jpg",
        }
        for r in featured_rooms:
            rd = dict(r)
            rd["amenities"] = json.loads(rd.get("amenities", "[]"))
            rd["images"] = json.loads(rd.get("images", "[]"))
            fallback_img = f'/static/images/rooms/{fallback_map.get(rd["room_type"], "single.jpg")}'

            # Prefer valid room images from DB; otherwise use local fallback
            primary_img = fallback_img
            if rd["images"] and isinstance(rd["images"], list):
                first_img = rd["images"][0]
                if isinstance(first_img, str) and first_img.strip():
                    img = first_img.strip()
                    if img.startswith("http://") or img.startswith("https://"):
                        primary_img = img
                    else:
                        if img.startswith("static/"):
                            img = "/" + img
                        if not img.startswith("/"):
                            img = "/static/images/rooms/" + img
                        # Ignore svg placeholders
                        if not img.lower().endswith(".svg"):
                            primary_img = img

            rd["primary_image"] = primary_img
            rd["fallback_image"] = fallback_img
            rooms_list.append(rd)

        return render_template(
            "public/index.html",
            featured_rooms=rooms_list,
            reviews=[dict(r) for r in reviews],
            stats=stats,
        )

    @app.route("/redirect-dashboard")
    def redirect_dashboard():
        role = session.get("user_role", "guest")
        redirects = {
            "superadmin": "/superadmin/dashboard",
            "admin": "/admin/dashboard",
            "manager": "/manager/dashboard",
            "staff": "/staff/dashboard",
            "guest": "/dashboard",
        }
        return redirect(redirects.get(role, "/"))

    @app.route("/about")
    def about():
        return render_template("public/about.html")

    @app.route("/contact")
    def contact():
        return render_template("public/contact.html")

    @app.route("/offers")
    def offers():
        from models.database import get_db

        if "user_id" not in session:
            flash("Please login to view offers.", "warning")
            return redirect(url_for("auth.login"))

        conn = get_db()
        coupons = conn.execute(
            "SELECT * FROM coupons WHERE is_active = 1 ORDER BY discount_value DESC"
        ).fetchall()

        role = session.get("user_role", "guest")
        if role in ["admin", "superadmin"]:
            conn.close()
            return render_template(
                "public/offers.html",
                coupons=[dict(c) for c in coupons],
                eligible=True,
                is_admin=True,
                has_first_booking=True,
                loyalty_points=0,
                min_points=app.config.get("OFFERS_MIN_POINTS", 0),
                first_booking_required=app.config.get(
                    "OFFERS_REQUIRE_FIRST_BOOKING", True
                ),
            )

        user_id = session["user_id"]
        user = conn.execute(
            "SELECT loyalty_points FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        paid_count = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE user_id = ? AND payment_status = 'paid'",
            (user_id,),
        ).fetchone()[0]
        conn.close()

        loyalty_points = user["loyalty_points"] if user else 0
        min_points = app.config.get("OFFERS_MIN_POINTS", 0)
        require_first = app.config.get("OFFERS_REQUIRE_FIRST_BOOKING", True)
        has_first_booking = paid_count > 0
        eligible = (not require_first or has_first_booking) and loyalty_points >= min_points

        return render_template(
            "public/offers.html",
            coupons=[dict(c) for c in coupons] if eligible else [],
            eligible=eligible,
            is_admin=False,
            has_first_booking=has_first_booking,
            loyalty_points=loyalty_points,
            min_points=min_points,
            first_booking_required=require_first,
        )

    @app.route("/checkin/<booking_id>")
    def quick_checkin(booking_id):
        """QR Code check-in page"""
        from models.database import get_db

        conn = get_db()
        booking = conn.execute(
            """SELECT b.*, u.first_name, u.last_name, u.phone, r.room_type
                                  FROM bookings b JOIN users u ON b.user_id = u.user_id
                                  JOIN rooms r ON b.room_id = r.room_id
                                  WHERE b.booking_id = ?""",
            (booking_id,),
        ).fetchone()
        conn.close()
        return render_template(
            "public/checkin_qr.html", booking=dict(booking) if booking else None
        )

    # API
    @app.route("/api/rooms/availability")
    def api_rooms_availability():
        from models.database import get_db

        conn = get_db()
        rooms = conn.execute(
            "SELECT room_number, status, room_type, floor FROM rooms ORDER BY room_number"
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rooms])

    @app.route("/api/price-calculator", methods=["POST"])
    def api_price_calculator():
        from ml_models.models import get_pricing_engine
        from models.database import get_db
        import json

        data = request.json
        room_type = data.get("room_type", "Single")
        room_id = data.get("room_id", "")
        check_in = data.get("check_in", "")
        check_out = data.get("check_out", "")

        if not check_in or not check_out:
            return jsonify({"error": "Dates required"})

        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            nights = max(1, (co - ci).days)
            days_until = (ci.date() - datetime.now().date()).days

            conn = get_db()
            occupied = conn.execute(
                "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
            ).fetchone()[0]
            total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
            base_price = None
            if room_id:
                row = conn.execute(
                    "SELECT current_price FROM rooms WHERE room_id = ?",
                    (room_id,),
                ).fetchone()
                if row:
                    base_price = row[0]
            conn.close()

            pricing = get_pricing_engine()
            occupied_pct = round(occupied / max(total_rooms, 1) * 100, 1)
            result = pricing.calculate_price(
                room_type, check_in, occupied_pct, days_until, base_price=base_price
            )

            base = result["final_price"] * nights
            gst = base * 0.18

            return jsonify(
                {
                    "base_price": result["base_price"],
                    "per_night": result["final_price"],
                    "nights": nights,
                    "base_amount": base,
                    "gst": gst,
                    "gst_rate": "18%",
                    "total": base + gst,
                    "rules_applied": result["rules_applied"],
                    "multiplier": result["multiplier"],
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route("/api/notifications/<user_id>")
    def api_notifications(user_id):
        if session.get("user_id") != user_id:
            return jsonify({"error": "Unauthorized"}), 403
        from models.database import get_db

        conn = get_db()
        notifs = conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,),
        ).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_status = 0",
            (user_id,),
        ).fetchone()[0]
        conn.close()
        return jsonify({"notifications": [dict(n) for n in notifs], "unread": unread})

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # Background scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        def auto_update_prices():
            """Update dynamic prices hourly"""
            try:
                with app.app_context():
                    from ml_models.models import get_pricing_engine
                    from models.database import get_db

                    conn = get_db()
                    occ = conn.execute(
                        "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
                    ).fetchone()[0]
                    total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
                    occupied_pct = round(occ / max(total_rooms, 1) * 100, 1)

                    pricing = get_pricing_engine()
                    today = datetime.now().date()

                    prices = pricing.get_all_current_prices(occupied_pct)
                    for room_type, data in prices.items():
                        conn.execute(
                            "UPDATE rooms SET current_price = ? WHERE room_type = ?",
                            (data["final_price"], room_type),
                        )
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[SCHEDULER] Price update error: {e}")

        scheduler = BackgroundScheduler()
        scheduler.add_job(auto_update_prices, "interval", hours=1)
        scheduler.start()
        print("[SCHEDULER] Background scheduler started")
    except Exception as e:
        print(f"[SCHEDULER] Could not start scheduler: {e}")

    # Auto-train ALL ML Models on startup
    try:
        from models.database import get_db
        conn = get_db()
        _rooms = [dict(r) for r in conn.execute('SELECT * FROM rooms WHERE is_active=1').fetchall()]
        _bks = [dict(r) for r in conn.execute('SELECT * FROM bookings').fetchall()]
        _users = [dict(r) for r in conn.execute('SELECT * FROM users').fetchall()]
        conn.close()

        # 1. Recommender
        from ml_models.ai_recommender import train_recommender, _load_model as _l1, _MODEL as _m1
        _l1()
        import ml_models.ai_recommender as _rm1
        if _rm1._MODEL is None: print(f"[ML] Recommender: {train_recommender(_rooms, _bks, _users).get('message')}")
        else: print(f"[ML] Recommender loaded.")

        # 2. Demand Forecast
        from ml_models.ai_demand_forecast import load_or_train_model as _l2
        _l2([{'created_at': b.get('created_at')} for b in _bks if b.get('created_at')])
        print(f"[ML] Demand Forecasting loaded.")

        # 3. Cancellation
        from ml_models.ai_cancellation import train_cancellation_model, _load_model as _l3
        _l3()
        import ml_models.ai_cancellation as _cm3
        if _cm3._MODEL is None: print(f"[ML] Cancellation: {train_cancellation_model(_bks, _users).get('message')}")
        else: print(f"[ML] Cancellation loaded.")

        # 4. Dynamic Pricing
        from ml_models.ai_dynamic_pricing import train_pricing_model, _load_model as _l4
        _l4()
        import ml_models.ai_dynamic_pricing as _pm4
        if _pm4._MODEL is None: print(f"[ML] Pricing: {train_pricing_model().get('message')}")
        else: print(f"[ML] Pricing loaded.")
    except Exception as _me:
        print(f"[ML] Auto-train skipped or failed: {_me}")

    return app


if __name__ == "__main__":
    app = create_app("development")
    print("BLISSFUL ABODES HOTEL MANAGEMENT SYSTEM")
    print("URL: http://localhost:5000")
    print("LOGIN CREDENTIALS:")
    print("  Super Admin: vikram@blissfulabodes.com / Admin@123")
    print("  Admin:       anil@blissfulabodes.com  / Admin@123")
    print("  Manager:     suresh@blissfulabodes.com / Staff@123")
    print("  Staff:       priya@blissfulabodes.com  / Staff@123")
    print("  Guest:       rajesh@example.com        / Guest@123")
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)




