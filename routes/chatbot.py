import re
import uuid
import json
from datetime import datetime
import html
from flask import Blueprint, jsonify, request, session, current_app
from models.database import get_db
from ml_models.agent_service import detect_intent
from ml_models.models import (
    get_pricing_engine,
    get_sentiment_analyzer,
    get_recommendation_model,
    get_fraud_detector,
)
from ml_models.agent_service import save_chat
from services.ai_chat_service import generate_ai_reply
from services.refund_policy import calculate_refund_pct, get_refund_thresholds

chatbot_bp = Blueprint("chatbot", __name__)

ROOM_TYPES = ["Single", "Double", "Family", "Couple", "VIP Suite"]
PAYMENT_METHODS = ["upi", "card", "cash", "netbanking"]


def _normalize(text):
    return (text or "").lower().strip()


def _detect_room_type(message):
    m = _normalize(message)
    if "vip" in m or "suite" in m:
        return "VIP Suite"
    if "couple" in m:
        return "Couple"
    if "family" in m:
        return "Family"
    if "double" in m:
        return "Double"
    if "single" in m:
        return "Single"
    return None


def _extract_dates(message):
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", message)
    if len(dates) >= 2:
        return dates[0], dates[1]

    # Support DD-MM-YYYY or DD/MM/YYYY
    raw = re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", message)
    if len(raw) >= 2:
        def _fmt(d, m, y):
            return f"{y}-{int(m):02d}-{int(d):02d}"
        return _fmt(*raw[0]), _fmt(*raw[1])

    return None, None


def _extract_guests(message):
    m = _normalize(message)
    match = re.search(r"(\d+)\s*(guest|guests|people|persons|adult|adults)", m)
    if match:
        return int(match.group(1))
    match = re.search(r"(?:for|with)\s*(\d+)\s*(?:guest|guests|people|persons|adult|adults)?", m)
    if match:
        return int(match.group(1))
    return None


def _format_recommendations(user_id):
    recommender = get_recommendation_model()
    recs = recommender.get_recommendations(user_id, n=4)
    if not recs:
        return "No recommendations available right now."
    lines = ["Recommended rooms:"]
    for rec in recs:
        room_type = rec.get("room_type", "Room")
        score = rec.get("match_score", 0)
        reason = rec.get("reason", "Recommended for you")
        lines.append(f"- {room_type} | {score}% match | {reason}")
    return "\n".join(lines)


def _extract_payment_method(message):
    m = _normalize(message)
    if "cash" in m:
        return "cash"
    if "upi" in m:
        return "upi"
    if "netbank" in m:
        return "netbanking"
    if "card" in m:
        return "card"
    return None


def _extract_booking_id(message):
    match = re.search(r"\bBK[A-Z0-9]{8,}\b", message.upper())
    if match:
        return match.group(0)
    return None


def _extract_rating(message):
    m = _normalize(message)
    match = re.search(r"\b([1-5])\s*(?:star|stars|/5)?\b", m)
    if match:
        return int(match.group(1))
    match = re.search(r"rating\s*[:=]?\s*([1-5])", m)
    if match:
        return int(match.group(1))
    return None


def _extract_room_number(message):
    match = re.search(r"\b([A-Z]\d{2,4})\b", message.upper())
    if match:
        return match.group(1)
    match = re.search(r"\broom\s*(\d{2,4})\b", _normalize(message))
    if match:
        return match.group(1)
    return None


def _is_confirm(message):
    m = _normalize(message)
    if "confirm" in m:
        return True
    return any(
        phrase in m
        for phrase in ["yes", "yep", "ok", "okay", "sure", "go ahead", "book it", "proceed"]
    )


def _normalize_room_type_value(value):
    if not value:
        return None
    text = str(value)
    if text in ROOM_TYPES:
        return text
    return _detect_room_type(text)


def _normalize_payment_method(value):
    if not value:
        return None
    val = _normalize(str(value))
    if val in PAYMENT_METHODS:
        return val
    if "upi" in val:
        return "upi"
    if "netbank" in val:
        return "netbanking"
    if "card" in val:
        return "card"
    if "cash" in val:
        return "cash"
    return None


def _parse_json_block(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def _ai_extract_booking(message, lang):
    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = (
        "You are a booking intent extractor. Return ONLY a JSON object with this schema: "
        "{'intent':'book'|'other','booking':{'room_type':string|null,'check_in':'YYYY-MM-DD'|null,"
        "'check_out':'YYYY-MM-DD'|null,'guests':number|null,'payment_method':string|null}}. "
        "Convert relative dates to ISO using today's date " + today + ". "
        "Room types: Single, Double, Family, Couple, VIP Suite. "
        "Payment methods: upi, card, cash, netbanking. "
        "If not a booking request, intent must be 'other'. "
        "Reply in JSON only, no extra text."
    )
    reply, err = generate_ai_reply(
        message, [], system_prompt, temperature=0.0, max_tokens=180
    )
    if not reply or err:
        return None
    return _parse_json_block(reply)


def _should_try_ai_booking(message):
    m = _normalize(message)
    return any(
        k in m
        for k in [
            "book",
            "booking",
            "reserve",
            "reservation",
            "stay",
            "suite",
            "room",
            "check-in",
            "check in",
            "check-out",
            "check out",
        ]
    )


def _detect_language(message):
    m = _normalize(message)
    if "hindi" in m or "lang:hi" in m:
        return "hi"
    if "tamil" in m or "lang:ta" in m:
        return "ta"
    if "english" in m or "lang:en" in m:
        return "en"
    return None


def _t(key, lang="en", **kwargs):
    full_hours, half_hours = get_refund_thresholds()
    messages = {
        "en": {
            "help": "I can help with room availability, prices, booking, cancellations, and services. What do you need?",
            "login_required": "Please log in as a guest to proceed.",
            "booking_start": "I can help you book a room. Which room type do you want?",
            "ask_room_type": "Please choose a room type: Single, Double, Family, Couple, or VIP Suite.",
            "ask_dates": "Please provide check-in and check-out dates in YYYY-MM-DD format.",
            "ask_guests": "How many guests will stay?",
            "ask_payment": "Preferred payment method? (UPI, card, cash, netbanking)",
            "review_start": "Sure — please share your booking ID to leave a review.",
            "ask_review_rating": "Please provide a rating from 1 to 5.",
            "ask_review_comment": "Please share your review comment.",
            "review_thanks": "Thanks! Your review has been submitted. Reference: {review_id}.",
            "support_start": "I can log a service/support request. Please describe the issue.",
            "ask_room_number": "Please share your room number (e.g., D204).",
            "support_logged": "Request logged. Reference: {ticket_id}. Our staff will assist shortly.",
            "confirm_booking": "Confirm booking? Reply 'confirm' to proceed or 'cancel' to stop.",
            "booking_cancelled": "Booking flow cancelled. How else can I help?",
            "booking_created_cash": "Booking confirmed. ID: {booking_id}. Room {room_number} is reserved.",
            "booking_created_pending": "Booking created. ID: {booking_id}. Please complete payment here: <a href=\"/guest/payment/{booking_id}\">Pay Now</a>.",
            "cancel_success": "Booking cancelled. Refund amount: INR {refund} ({refund_pct}%).",
            "cancel_fail": "Unable to cancel this booking.",
            "booking_not_found": "Booking not found. Please check the booking ID.",
            "request_routed": "Your request has been forwarded to staff. Reference: {ticket_id}.",
            "request_not_routed": "I could not reach staff right now. Please call +91 44 2345 6789.",
            "availability": "We currently have {total_available} available rooms out of {total_rooms}.",
            "availability_type": "{room_type} availability: {count} rooms available now.",
            "prices_range": "Room prices range from INR {min_price} to INR {max_price} per night.",
            "price_type": "{room_type} average price is INR {avg_price} per night (range INR {min_price} - {max_price}).",
            "booking_guidance": "To book: go to <a href=\"/rooms\">Rooms</a>, pick a room, select dates, and confirm payment.",
            "cancellation_help": "Cancel from <a href=\"/guest/bookings\">My Bookings</a>. Policy: full refund {full_hours}+ hours before check-in, 50% within {half_hours}-{full_hours} hours, no refund within {half_hours} hours.",
            "amenities_help": "Amenities: pool, fitness center, spa, restaurant & bar, business center, concierge. Wi-Fi is free.",
            "checkin_help": "Check-in: 2:00 PM. Check-out: 12:00 PM. ID required at check-in.",
            "location_help": "We are at 123 Marina Beach Road, Chennai - 600001.",
            "offers_help": "See current offers at <a href=\"/offers\">Offers</a>.",
            "gst_help": "GST is 18% on accommodation. GSTIN: 33AAACB1234F1Z5.",
            "contact_help": "Call +91 44 2345 6789 or email info@blissfulabodes.com.",
        },
        "hi": {
            "help": "Main room availability, prices, booking, cancellations, aur services mein madad kar sakta hoon.",
            "login_required": "Kripya guest account se login karein.",
            "booking_start": "Booking ke liye room type batayein.",
            "ask_room_type": "Room type choose karein: Single, Double, Family, Couple, VIP Suite.",
            "ask_dates": "Check-in aur check-out dates YYYY-MM-DD format mein batayein.",
            "ask_guests": "Kitne guests rahenge?",
            "ask_payment": "Payment method? (UPI, card, cash, netbanking)",
            "review_start": "Review ke liye booking ID batayein.",
            "ask_review_rating": "Rating 1 se 5 tak batayein.",
            "ask_review_comment": "Apna review comment likhein.",
            "review_thanks": "Shukriya! Aapka review submit ho gaya. Reference: {review_id}.",
            "support_start": "Service/support request ke liye issue batayein.",
            "ask_room_number": "Room number batayein (e.g., D204).",
            "support_logged": "Request logged. Reference: {ticket_id}. Staff jaldi help karega.",
            "confirm_booking": "Confirm karein? 'confirm' likhein ya 'cancel' karein.",
            "booking_cancelled": "Booking flow cancel ho gaya. Aur kya madad chahiye?",
            "booking_created_cash": "Booking confirm. ID: {booking_id}. Room {room_number} reserved.",
            "booking_created_pending": "Booking created. ID: {booking_id}. Payment karein: <a href=\"/guest/payment/{booking_id}\">Pay Now</a>.",
            "cancel_success": "Booking cancel ho gayi. Refund: INR {refund} ({refund_pct}%).",
            "cancel_fail": "Booking cancel nahi ho saki.",
            "booking_not_found": "Booking ID nahi mili.",
            "request_routed": "Aapka request staff ko bhej diya. Reference: {ticket_id}.",
            "request_not_routed": "Staff available nahi. Kripya +91 44 2345 6789 par call karein.",
            "availability": "{total_available} rooms available hain (total {total_rooms}).",
            "availability_type": "{room_type} availability: {count}.",
            "prices_range": "Price range: INR {min_price} - INR {max_price} per night.",
            "price_type": "{room_type} avg price INR {avg_price} (range INR {min_price}-{max_price}).",
            "booking_guidance": "Booking ke liye <a href=\"/rooms\">Rooms</a> par jayein.",
            "cancellation_help": "Cancel: <a href=\"/guest/bookings\">My Bookings</a>. Policy: {full_hours}+ hours full refund, {half_hours}-{full_hours} hours 50%, {half_hours} hours ke andar no refund.",
            "amenities_help": "Amenities: pool, gym, spa, restaurant, concierge, free Wi-Fi.",
            "checkin_help": "Check-in 2:00 PM, check-out 12:00 PM.",
            "location_help": "Address: 123 Marina Beach Road, Chennai - 600001.",
            "offers_help": "Offers: <a href=\"/offers\">Offers</a>.",
            "gst_help": "GST 18%. GSTIN: 33AAACB1234F1Z5.",
            "contact_help": "Call +91 44 2345 6789, email info@blissfulabodes.com.",
        },
        "ta": {
            "help": "Room availability, prices, booking, cancellations, services kurithu udhavi seyya mudiyum.",
            "login_required": "Guest account-il login seyyavum.",
            "booking_start": "Booking-kaga room type solunga.",
            "ask_room_type": "Room type: Single, Double, Family, Couple, VIP Suite.",
            "ask_dates": "Check-in, check-out dates YYYY-MM-DD format-il solunga.",
            "ask_guests": "Ethanai guests varuvanga?",
            "ask_payment": "Payment method? (UPI, card, cash, netbanking)",
            "review_start": "Review-ku booking ID solunga.",
            "ask_review_rating": "Rating 1-5 solunga.",
            "ask_review_comment": "Review comment solunga.",
            "review_thanks": "Nandri! Review submit aagiduchu. Reference: {review_id}.",
            "support_start": "Service/support request-ku issue sollunga.",
            "ask_room_number": "Room number solunga (e.g., D204).",
            "support_logged": "Request logged. Reference: {ticket_id}. Staff help pannuvanga.",
            "confirm_booking": "Confirm panna 'confirm' type pannunga. Cancel panna 'cancel'.",
            "booking_cancelled": "Booking flow cancel aachu.",
            "booking_created_cash": "Booking confirm. ID: {booking_id}. Room {room_number} reserved.",
            "booking_created_pending": "Booking created. ID: {booking_id}. Payment: <a href=\"/guest/payment/{booking_id}\">Pay Now</a>.",
            "cancel_success": "Booking cancel aachu. Refund INR {refund} ({refund_pct}%).",
            "cancel_fail": "Booking cancel panna mudiyala.",
            "booking_not_found": "Booking ID kidaikkala.",
            "request_routed": "Request staff-ku anuppa pattadhu. Reference: {ticket_id}.",
            "request_not_routed": "Staff reach aagala. +91 44 2345 6789 call pannunga.",
            "availability": "{total_available} rooms available (total {total_rooms}).",
            "availability_type": "{room_type} availability: {count}.",
            "prices_range": "Price range: INR {min_price} - INR {max_price} per night.",
            "price_type": "{room_type} avg price INR {avg_price} (range INR {min_price}-{max_price}).",
            "booking_guidance": "Booking-kaga <a href=\"/rooms\">Rooms</a> pogavum.",
            "cancellation_help": "Cancel: <a href=\"/guest/bookings\">My Bookings</a>. Policy: {full_hours}+ hours full refund, {half_hours}-{full_hours} hours 50%, {half_hours} hours ulla no refund.",
            "amenities_help": "Amenities: pool, gym, spa, restaurant, concierge, free Wi-Fi.",
            "checkin_help": "Check-in 2:00 PM, check-out 12:00 PM.",
            "location_help": "Address: 123 Marina Beach Road, Chennai - 600001.",
            "offers_help": "Offers: <a href=\"/offers\">Offers</a>.",
            "gst_help": "GST 18%. GSTIN: 33AAACB1234F1Z5.",
            "contact_help": "Call +91 44 2345 6789, email info@blissfulabodes.com.",
        },
    }
    template = messages.get(lang, messages["en"]).get(key, "")
    kwargs.setdefault("full_hours", full_hours)
    kwargs.setdefault("half_hours", half_hours)
    return template.format(**kwargs)


def _route_to_admin(title, message):
    conn = get_db()
    admins = conn.execute(
        "SELECT user_id FROM users WHERE role IN ('admin','superadmin') AND is_active = 1"
    ).fetchall()
    for a in admins:
        conn.execute(
            """INSERT INTO notifications
               (notification_id, user_id, title, message, notification_type, action_url)
               VALUES (?, ?, ?, ?, 'warning', ?)""",
            (
                str(uuid.uuid4()),
                a["user_id"],
                title,
                message,
                "/admin/dashboard",
            ),
        )
        conn.execute(
            """INSERT INTO messages (message_id, sender_id, recipient_id, content)
               VALUES (?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                session.get("user_id") or "guest",
                a["user_id"],
                message,
            ),
        )
    conn.commit()
    conn.close()
    return len(admins) > 0


def _availability_summary():
    conn = get_db()
    total_available = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'available' AND is_active = 1"
    ).fetchone()[0]
    total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    by_type = conn.execute(
        """SELECT room_type, COUNT(*) as cnt
           FROM rooms
           WHERE status = 'available' AND is_active = 1
           GROUP BY room_type"""
    ).fetchall()
    conn.close()
    return total_available, total_rooms, [dict(r) for r in by_type]


def _availability_for_guests(guests):
    conn = get_db()
    total_available = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status = 'available' AND is_active = 1 AND max_guests >= ?",
        (guests,),
    ).fetchone()[0]
    by_type = conn.execute(
        """SELECT room_type, COUNT(*) as cnt
           FROM rooms
           WHERE status = 'available' AND is_active = 1 AND max_guests >= ?
           GROUP BY room_type""",
        (guests,),
    ).fetchall()
    conn.close()
    return total_available, [dict(r) for r in by_type]


def _price_summary(room_type=None):
    conn = get_db()
    if room_type:
        row = conn.execute(
            """SELECT MIN(current_price) as min_price,
                      MAX(current_price) as max_price,
                      AVG(current_price) as avg_price
               FROM rooms
               WHERE room_type = ? AND is_active = 1""",
            (room_type,),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT MIN(current_price) as min_price,
                      MAX(current_price) as max_price
               FROM rooms
               WHERE is_active = 1"""
        ).fetchone()
    conn.close()
    return dict(row) if row else {}


def _num(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _get_booking_state():
    state = session.get("chatbot_booking_state")
    if not state:
        state = {
            "active": False,
            "step": "room_type",
            "room_type": "",
            "check_in": "",
            "check_out": "",
            "guests": 0,
            "payment_method": "",
        }
        session["chatbot_booking_state"] = state
    return state


def _reset_booking_state():
    session.pop("chatbot_booking_state", None)


def _get_review_state():
    state = session.get("chatbot_review_state")
    if not state:
        state = {
            "active": False,
            "booking_id": "",
            "rating": 0,
            "comment": "",
        }
        session["chatbot_review_state"] = state
    return state


def _reset_review_state():
    session.pop("chatbot_review_state", None)


def _get_support_state():
    state = session.get("chatbot_support_state")
    if not state:
        state = {
            "active": False,
            "details": "",
            "room_number": "",
            "request_type": "",
        }
        session["chatbot_support_state"] = state
    return state


def _reset_support_state():
    session.pop("chatbot_support_state", None)


def _get_chat_user_id():
    if session.get("user_id"):
        return session["user_id"]
    anon_id = session.get("chatbot_anon_id")
    if not anon_id:
        anon_id = f"anon_{uuid.uuid4().hex[:12]}"
        session["chatbot_anon_id"] = anon_id
    return anon_id


def _save_chat_message(user_id, role, content):
    if not user_id or not content:
        return
    conn = get_db()
    conn.execute(
        """INSERT INTO chatbot_messages (user_id, role, content)
           VALUES (?, ?, ?)""",
        (user_id, role, content),
    )
    conn.commit()
    conn.close()


def _load_chat_history(user_id, limit=30):
    if not user_id:
        return []
    conn = get_db()
    rows = conn.execute(
        """SELECT role, content, created_at
           FROM chatbot_messages
           WHERE user_id = ?
           ORDER BY created_at ASC
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _create_review(user_id, booking_id, rating, comment):
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user_id),
    ).fetchone()
    if not booking:
        conn.close()
        return False, "booking_not_found"

    booking = dict(booking)
    room_id = booking.get("room_id")
    verified = 1 if booking.get("status") in ("completed", "confirmed") else 0

    sentiment = get_sentiment_analyzer()
    analysis = sentiment.analyze(comment or "")
    review_id = str(uuid.uuid4())

    conn.execute(
        """INSERT INTO reviews
           (review_id, booking_id, user_id, room_id, overall_rating,
            cleanliness_rating, staff_rating, location_rating, value_rating, amenities_rating,
            comment, verified_stay, sentiment, sentiment_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            review_id,
            booking_id,
            user_id,
            room_id,
            float(rating),
            float(rating),
            float(rating),
            float(rating),
            float(rating),
            float(rating),
            comment,
            verified,
            analysis.get("sentiment", "neutral"),
            analysis.get("score", 0),
        ),
    )
    conn.commit()
    conn.close()
    return True, review_id


def _latest_booking_room(user_id):
    conn = get_db()
    row = conn.execute(
        """SELECT room_id, room_number FROM bookings
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT 1""",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _room_by_number(room_number):
    if not room_number:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT room_id, room_number FROM rooms WHERE room_number = ?",
        (room_number,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _create_support_request(user_id, details, request_type="", room_number=""):
    ticket_id = f"REQ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    room = _room_by_number(room_number)
    if not room:
        room = _latest_booking_room(user_id)

    if request_type == "housekeeping" and room:
        conn = get_db()
        conn.execute(
            """INSERT INTO housekeeping_tasks
               (task_id, room_id, room_number, assigned_to, task_type, priority, status, notes, created_by)
               VALUES (?, ?, ?, NULL, 'housekeeping', 'normal', 'pending', ?, ?)""",
            (
                ticket_id,
                room.get("room_id"),
                room.get("room_number"),
                details,
                user_id,
            ),
        )
        conn.commit()
        conn.close()
    elif request_type == "maintenance":
        conn = get_db()
        conn.execute(
            """INSERT INTO maintenance_issues
               (issue_id, room_id, room_number, reported_by, issue_type, description, priority, status)
               VALUES (?, ?, ?, ?, 'maintenance', ?, 'normal', 'open')""",
            (
                ticket_id,
                room.get("room_id") if room else None,
                room.get("room_number") if room else None,
                user_id,
                details,
            ),
        )
        conn.commit()
        conn.close()
    else:
        conn = get_db()
        conn.execute(
            """INSERT INTO service_requests
               (request_id, user_id, room_id, room_number, request_type, details, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (
                ticket_id,
                user_id,
                room.get("room_id") if room else None,
                room.get("room_number") if room else None,
                request_type or "support",
                details,
            ),
        )
        conn.commit()
        conn.close()

    routed = _route_to_admin(
        "Chatbot Service Request",
        f"{ticket_id} | User: {user_id} | Room: {room.get('room_number') if room else 'N/A'} | {details}",
    )

    conn = get_db()
    conn.execute(
        """INSERT INTO notifications (notification_id, user_id, title, message, notification_type, action_url)
           VALUES (?, ?, ?, ?, 'info', ?)""",
        (
            str(uuid.uuid4()),
            user_id,
            "Request Received",
            f"Your request has been logged. Reference: {ticket_id}",
            "/guest/dashboard",
        ),
    )
    conn.commit()
    conn.close()
    return ticket_id, routed


def _get_ai_history():
    history = session.get("chatbot_ai_history")
    if not isinstance(history, list):
        history = []
    return history


def _append_ai_history(user_message, assistant_message):
    history = _get_ai_history()
    user_text = (user_message or "")[:600]
    assistant_text = (assistant_message or "")[:600]
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": assistant_text})
    session["chatbot_ai_history"] = history[-6:]


def _sanitize_ai(text):
    return html.escape(text).replace("\n", "<br/>")


def _build_system_prompt(lang):
    hotel_name = current_app.config.get("HOTEL_NAME", "Blissful Abodes Chennai")
    hotel_address = current_app.config.get(
        "HOTEL_ADDRESS", "123 Marina Beach Road, Chennai - 600001"
    )
    hotel_phone = current_app.config.get("HOTEL_PHONE", "+91 44 2345 6789")
    hotel_email = current_app.config.get("HOTEL_EMAIL", "info@blissfulabodes.com")
    gst_rate = int(current_app.config.get("GST_RATE", 0.18) * 100)

    lang_label = {"en": "English", "hi": "Hindi", "ta": "Tamil"}.get(lang, "English")

    return (
        f"You are Aria, the AI concierge for {hotel_name}. "
        f"Hotel info: address {hotel_address}, phone {hotel_phone}, email {hotel_email}. "
        f"GST is {gst_rate}%. Keep replies concise, helpful, and factual. "
        f"Do not claim you completed bookings or payments. "
        f"If user asks to book, request room type, check-in, check-out (YYYY-MM-DD), guests, "
        f"and payment method. If all details are present, acknowledge and proceed. "
        f"Reply in {lang_label}."
    )


def _select_available_room(room_type):
    conn = get_db()
    room = conn.execute(
        """SELECT * FROM rooms
           WHERE room_type = ? AND status = 'available' AND is_active = 1
           ORDER BY current_price ASC
           LIMIT 1""",
        (room_type,),
    ).fetchone()
    conn.close()
    return dict(room) if room else None


def _create_booking(user_id, room, check_in, check_out, guests, payment_method):
    ci = datetime.strptime(check_in, "%Y-%m-%d")
    co = datetime.strptime(check_out, "%Y-%m-%d")
    if ci.date() < datetime.now().date():
        return None, "Check-in date cannot be in the past."
    nights = (co - ci).days
    if nights <= 0:
        return None, "Invalid dates."
    if guests > int(room.get("max_guests", 1)):
        return None, "Guest count exceeds room capacity."
    if str(payment_method).lower() not in PAYMENT_METHODS:
        return None, "Invalid payment method."

    conn = get_db()
    occ = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
    ).fetchone()[0]
    total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    occ_pct = round(occ / max(total_rooms, 1) * 100, 1)
    conn.close()

    days_until = (ci.date() - datetime.now().date()).days
    pricing_engine = get_pricing_engine()
    pricing = pricing_engine.calculate_price(
        room["room_type"],
        check_in,
        occ_pct,
        days_until,
        base_price=room.get("current_price"),
    )
    base_per_night = pricing["final_price"]
    base_amount = base_per_night * nights
    gst = base_amount * 0.18
    total_amount = base_amount + gst

    fraud_detector = get_fraud_detector()
    fraud_result = fraud_detector.predict(
        {
            "total_amount": total_amount,
            "payment_method": payment_method,
            "num_guests": guests,
            "is_new_user": False,
        }
    )
    if fraud_result.get("risk_level") == "HIGH":
        return None, "fraud_high", fraud_result
    is_flagged = 0

    booking_id = f"BK{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    is_cash = str(payment_method).lower() in ["cash", "cash_at_desk", "cash at desk"]
    status = "confirmed" if is_cash else "pending"
    payment_status = "paid" if is_cash else "pending"

    conn = get_db()
    conn.execute(
        """INSERT INTO bookings
        (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
         base_amount, gst_amount, total_amount, status, payment_status, payment_method,
         fraud_score, is_flagged)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            booking_id,
            user_id,
            room["room_id"],
            room["room_number"],
            check_in,
            check_out,
            guests,
            base_amount,
            gst,
            total_amount,
            status,
            payment_status,
            payment_method,
            fraud_result.get("fraud_score", 0),
            is_flagged,
        ),
    )
    conn.execute(
        "UPDATE rooms SET status = ? WHERE room_id = ?",
        ("occupied" if is_cash else "reserved", room["room_id"]),
    )
    conn.execute(
        """INSERT INTO notifications (notification_id, user_id, title, message, notification_type, action_url)
           VALUES (?, ?, ?, ?, 'info', ?)""",
        (
            str(uuid.uuid4()),
            user_id,
            "Booking Created",
            f"Room {room['room_number']} reserved for {check_in} - {check_out}.",
            f"/guest/booking/{booking_id}",
        ),
    )
    conn.commit()
    conn.close()
    return booking_id, None, fraud_result


def _cancel_booking(user_id, booking_id):
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? AND user_id = ?",
        (booking_id, user_id),
    ).fetchone()
    if not booking:
        conn.close()
        return None, "not_found"
    booking = dict(booking)
    if booking["status"] in ["cancelled", "completed"]:
        conn.close()
        return None, "not_allowed"

    ci = datetime.strptime(booking["check_in"], "%Y-%m-%d")
    hours_until = (ci - datetime.now()).total_seconds() / 3600.0
    refund_pct = calculate_refund_pct(hours_until, booking.get("payment_status"))
    refund_amount = booking["total_amount"] * refund_pct

    conn.execute(
        "UPDATE bookings SET status = 'cancelled', updated_at = ? WHERE booking_id = ?",
        (datetime.now().isoformat(), booking_id),
    )
    conn.execute(
        "UPDATE rooms SET status = 'available' WHERE room_id = ?", (booking["room_id"],)
    )
    if booking.get("loyalty_points_used", 0) > 0 and booking.get("payment_status") == "paid":
        conn.execute(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id = ?",
            (booking["loyalty_points_used"], user_id),
        )
    conn.commit()
    conn.close()
    return {"refund": refund_amount, "refund_pct": int(refund_pct * 100)}, None


def _get_user_bookings(user_id, limit=5):
    conn = get_db()
    rows = conn.execute(
        """SELECT booking_id, check_in, check_out, status, payment_status
           FROM bookings
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_booking_status(user_id, booking_id):
    conn = get_db()
    row = conn.execute(
        """SELECT booking_id, status, payment_status, check_in, check_out
           FROM bookings
           WHERE booking_id = ? AND user_id = ?""",
        (booking_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


@chatbot_bp.route("/api/chatbot/message", methods=["POST"])
def chatbot_message():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "reply": "Please enter a message."}), 400

    chat_user_id = _get_chat_user_id()
    _save_chat_message(chat_user_id, "user", message)
    save_chat(chat_user_id, message)

    def _reply(text):
        _save_chat_message(chat_user_id, "assistant", text)
        save_chat(chat_user_id, text)
        return jsonify({"ok": True, "reply": text})

    lang = session.get("chatbot_lang", "en")
    lang_detected = _detect_language(message)
    if lang_detected:
        lang = lang_detected
        session["chatbot_lang"] = lang

    m = _normalize(message)
    simple_intent = detect_intent(message)
    room_type = _detect_room_type(m)
    booking_id = _extract_booking_id(message)

    if ("cancel" in m or "refund" in m) and booking_id:
        if not session.get("user_id"):
            return _reply(_t("login_required", lang))
        result, err = _cancel_booking(session["user_id"], booking_id)
        if err == "not_found":
            return _reply(_t("booking_not_found", lang))
        if err:
            return _reply(_t("cancel_fail", lang))
        return _reply(
            _t(
                "cancel_success",
                lang,
                refund=int(result["refund"]),
                refund_pct=result["refund_pct"],
            )
        )

    if "status" in m and booking_id:
        if not session.get("user_id"):
            return _reply(_t("login_required", lang))
        status = _get_booking_status(session["user_id"], booking_id)
        if not status:
            return _reply(_t("booking_not_found", lang))
        reply = (
            f"Booking {status['booking_id']} status: {status['status']}, "
            f"payment: {status['payment_status']}. "
            f"Check-in: {status['check_in']}, Check-out: {status['check_out']}."
        )
        return _reply(reply)

    review_state = _get_review_state()
    review_active = review_state.get("active") or any(
        k in m for k in ["review", "feedback", "rating", "rate", "stars"]
    )
    if review_active:
        if not session.get("user_id") or session.get("user_role") != "guest":
            _reset_review_state()
            return _reply(_t("login_required", lang))

        review_state["active"] = True
        if booking_id and not review_state.get("booking_id"):
            review_state["booking_id"] = booking_id
        rating = _extract_rating(message)
        if rating and not review_state.get("rating"):
            review_state["rating"] = rating

        comment_candidate = message
        if booking_id:
            comment_candidate = comment_candidate.replace(booking_id, "")
        if rating:
            comment_candidate = re.sub(r"\b" + str(rating) + r"\b", "", comment_candidate)
        if not review_state.get("comment") and len(comment_candidate.strip()) > 5:
            review_state["comment"] = comment_candidate.strip()

        session["chatbot_review_state"] = review_state

        if not review_state.get("booking_id"):
            return _reply(_t("review_start", lang))
        if not review_state.get("rating"):
            return _reply(_t("ask_review_rating", lang))
        if not review_state.get("comment"):
            return _reply(_t("ask_review_comment", lang))

        ok, result = _create_review(
            session["user_id"],
            review_state["booking_id"],
            review_state["rating"],
            review_state["comment"],
        )
        _reset_review_state()
        if not ok and result == "booking_not_found":
            return _reply(_t("booking_not_found", lang))
        if not ok:
            return _reply("Unable to submit review right now.")
        return _reply(_t("review_thanks", lang, review_id=result))

    support_state = _get_support_state()
    support_keywords = [
        "support",
        "service request",
        "service",
        "room service",
        "food",
        "meal",
        "breakfast",
        "lunch",
        "dinner",
        "order",
        "housekeeping",
        "cleaning",
        "maintenance",
        "repair",
        "issue",
        "problem",
        "complaint",
        "room service",
        "towel",
        "linen",
        "ac",
        "wifi",
        "leak",
    ]
    support_active = support_state.get("active") or any(k in m for k in support_keywords)
    if support_active:
        if not session.get("user_id") or session.get("user_role") != "guest":
            _reset_support_state()
            return _reply(_t("login_required", lang))

        support_state["active"] = True
        if not support_state.get("details") and len(message.strip()) > 5:
            support_state["details"] = message.strip()
        if not support_state.get("room_number"):
            support_state["room_number"] = _extract_room_number(message) or ""
        if not support_state.get("request_type"):
            if any(k in m for k in ["housekeeping", "cleaning", "towel", "linen"]):
                support_state["request_type"] = "housekeeping"
            elif any(k in m for k in ["maintenance", "repair", "ac", "wifi", "leak", "electrical", "plumbing"]):
                support_state["request_type"] = "maintenance"
            elif any(k in m for k in ["room service", "food", "meal", "breakfast", "lunch", "dinner", "order"]):
                support_state["request_type"] = "room_service"
            else:
                support_state["request_type"] = "support"

        session["chatbot_support_state"] = support_state

        if not support_state.get("details"):
            return _reply(_t("support_start", lang))

        if support_state.get("request_type") in ["housekeeping", "maintenance"]:
            room_number = support_state.get("room_number")
            if not room_number and not _latest_booking_room(session["user_id"]):
                return _reply(_t("ask_room_number", lang))

        ticket_id, _ = _create_support_request(
            session["user_id"],
            support_state["details"],
            support_state.get("request_type", ""),
            support_state.get("room_number", ""),
        )
        _reset_support_state()
        return _reply(_t("support_logged", lang, ticket_id=ticket_id))

    if simple_intent == "recommend":
        target_id = session.get("user_id") or chat_user_id
        return _reply(_format_recommendations(target_id))

    booking_state = _get_booking_state()
    booking_active = booking_state.get("active") or (
        (simple_intent == "book_room" or any(k in m for k in ["book", "booking", "reserve", "reservation"]))
        and "cancel" not in m
        and "refund" not in m
    )

    if not booking_state.get("active") and _should_try_ai_booking(message):
        ai_result = _ai_extract_booking(message, lang)
        if ai_result and ai_result.get("intent") == "book":
            if not session.get("user_id") or session.get("user_role") != "guest":
                return _reply(_t("login_required", lang))

            booking = ai_result.get("booking") or {}
            room_type = _normalize_room_type_value(booking.get("room_type")) or _detect_room_type(message)
            check_in = booking.get("check_in")
            check_out = booking.get("check_out")
            if not check_in or not check_out:
                ci, co = _extract_dates(message)
                check_in = check_in or ci
                check_out = check_out or co

            guests = booking.get("guests")
            try:
                guests = int(guests) if guests is not None else None
            except Exception:
                guests = None
            guests = guests or _extract_guests(message)

            payment_method = _normalize_payment_method(booking.get("payment_method")) or _extract_payment_method(message)

            missing = []
            if not room_type:
                missing.append("room_type")
            if not check_in or not check_out:
                missing.append("dates")
            if not guests:
                missing.append("guests")
            if not payment_method:
                missing.append("payment_method")

            if missing:
                booking_state.update(
                    {
                        "active": True,
                        "room_type": room_type or "",
                        "check_in": check_in or "",
                        "check_out": check_out or "",
                        "guests": guests or 0,
                        "payment_method": payment_method or "",
                    }
                )
                session["chatbot_booking_state"] = booking_state
                if "room_type" in missing:
                    return _reply(_t("ask_room_type", lang))
                if "dates" in missing:
                    return _reply(_t("ask_dates", lang))
                if "guests" in missing:
                    return _reply(_t("ask_guests", lang))
                return _reply(_t("ask_payment", lang))

            room = _select_available_room(room_type)
            if not room:
                return _reply("No available rooms for that type right now.")

            booking_id, error, fraud_result = _create_booking(
                session["user_id"],
                room,
                check_in,
                check_out,
                guests,
                payment_method,
            )
            if error:
                if error == "fraud_high":
                    return _reply("Suspicious booking detected. Please contact support.")
                return _reply(f"Booking failed: {error}")

            if str(payment_method).lower() == "cash":
                return _reply(
                    _t(
                        "booking_created_cash",
                        lang,
                        booking_id=booking_id,
                        room_number=room.get("room_number", ""),
                    )
                )
            return _reply(_t("booking_created_pending", lang, booking_id=booking_id))

    if booking_active:
        if not session.get("user_id") or session.get("user_role") != "guest":
            _reset_booking_state()
            return _reply(_t("login_required", lang))

        booking_state["active"] = True
        if room_type and not booking_state.get("room_type"):
            booking_state["room_type"] = room_type
        if not booking_state.get("check_in") or not booking_state.get("check_out"):
            ci, co = _extract_dates(message)
            if ci and co:
                booking_state["check_in"] = ci
                booking_state["check_out"] = co
        if not booking_state.get("guests"):
            guests = _extract_guests(message)
            if guests:
                booking_state["guests"] = guests
        if not booking_state.get("payment_method"):
            pay = _extract_payment_method(message)
            if pay:
                booking_state["payment_method"] = pay

        if not booking_state.get("room_type"):
            session["chatbot_booking_state"] = booking_state
            return _reply(_t("ask_room_type", lang))
        if not booking_state.get("check_in") or not booking_state.get("check_out"):
            session["chatbot_booking_state"] = booking_state
            return _reply(_t("ask_dates", lang))
        if not booking_state.get("guests"):
            session["chatbot_booking_state"] = booking_state
            return _reply(_t("ask_guests", lang))
        if not booking_state.get("payment_method"):
            session["chatbot_booking_state"] = booking_state
            return _reply(_t("ask_payment", lang))

        if "cancel" in m:
            _reset_booking_state()
            return _reply(_t("booking_cancelled", lang))

        room = _select_available_room(booking_state["room_type"])
        if not room:
            _reset_booking_state()
            return _reply("No available rooms for that type right now.")

        booking_id, error, fraud_result = _create_booking(
            session["user_id"],
            room,
            booking_state["check_in"],
            booking_state["check_out"],
            booking_state["guests"],
            booking_state["payment_method"],
        )
        _reset_booking_state()
        if error:
            if error == "fraud_high":
                return _reply("Suspicious booking detected. Please contact support.")
            return _reply(f"Booking failed: {error}")

        if str(booking_state["payment_method"]).lower() == "cash":
            return _reply(
                _t(
                    "booking_created_cash",
                    lang,
                    booking_id=booking_id,
                    room_number=room.get("room_number", ""),
                )
            )
        return _reply(_t("booking_created_pending", lang, booking_id=booking_id))

    if "available" in m or "availability" in m:
        guests = _extract_guests(message)
        if guests:
            total_available, by_type = _availability_for_guests(guests)
            if room_type:
                count = 0
                for r in by_type:
                    if r["room_type"] == room_type:
                        count = r["cnt"]
                        break
                return _reply(
                    _t(
                        "availability_type",
                        lang,
                        room_type=room_type,
                        count=count,
                    )
                    + f" For {guests} guests. <a href=\"/rooms\">Rooms</a>."
                )
            breakdown = ", ".join([f"{r['room_type']}: {r['cnt']}" for r in by_type])
            reply = f"{total_available} rooms available for {guests} guests."
            if breakdown:
                reply += f" By type: {breakdown}."
            reply += ' <a href="/rooms">Rooms</a>.'
            return _reply(reply)

        total_available, total_rooms, by_type = _availability_summary()
        if room_type:
            count = 0
            for r in by_type:
                if r["room_type"] == room_type:
                    count = r["cnt"]
                    break
            return _reply(
                _t(
                    "availability_type",
                    lang,
                    room_type=room_type,
                    count=count,
                )
                + ' <a href="/rooms">Rooms</a>.'
            )
        return _reply(
            _t(
                "availability",
                lang,
                total_available=total_available,
                total_rooms=total_rooms,
            )
            + ' <a href="/rooms">Rooms</a>.'
        )

    if "price" in m or "cost" in m or "rate" in m or "tariff" in m:
        if room_type:
            price = _price_summary(room_type)
            avg_price = price.get("avg_price")
            if avg_price:
                return _reply(
                    _t(
                        "price_type",
                        lang,
                        room_type=room_type,
                        avg_price=f"{_num(avg_price):,}",
                        min_price=f"{_num(price.get('min_price')):,}",
                        max_price=f"{_num(price.get('max_price')):,}",
                    )
                )
            return _reply("Pricing not available.")
        price = _price_summary()
        return _reply(
            _t(
                "prices_range",
                lang,
                min_price=f"{_num(price.get('min_price')):,}",
                max_price=f"{_num(price.get('max_price')):,}",
            )
        )

    if "cancel" in m or "refund" in m:
        if session.get("user_id"):
            items = _get_user_bookings(session["user_id"], limit=5)
            if items:
                lines = ["Your recent bookings:"]
                for b in items:
                    lines.append(
                        f"{b['booking_id']} | {b['check_in']} to {b['check_out']} | {b['status']}"
                    )
                lines.append("Reply 'cancel <BOOKING_ID>' to cancel a booking.")
                return _reply("<br/>".join(lines))
        return _reply(_t("cancellation_help", lang))
    if "book" in m or "booking" in m or "reserve" in m:
        return _reply(_t("booking_guidance", lang))

    if any(
        k in m
        for k in ["amenity", "facility", "pool", "gym", "spa", "wifi", "restaurant", "breakfast", "food"]
    ):
        return _reply(_t("amenities_help", lang))

    if "check-in" in m or ("check" in m and "in" in m) or "check-out" in m or ("check" in m and "out" in m):
        return _reply(_t("checkin_help", lang))

    if any(k in m for k in ["location", "address", "where", "map", "direction"]):
        return _reply(_t("location_help", lang))

    if any(k in m for k in ["offer", "discount", "coupon", "promo"]):
        return _reply(_t("offers_help", lang))

    if any(k in m for k in ["gst", "invoice", "tax"]):
        return _reply(_t("gst_help", lang))

    if any(k in m for k in ["contact", "phone", "email", "call"]):
        return _reply(_t("contact_help", lang))

    if "my booking" in m or "my bookings" in m:
        if not session.get("user_id"):
            return _reply(_t("login_required", lang))
        items = _get_user_bookings(session["user_id"], limit=5)
        if not items:
            return _reply("No bookings found.")
        lines = ["Your recent bookings:"]
        for b in items:
            lines.append(
                f"{b['booking_id']} | {b['check_in']} to {b['check_out']} | {b['status']}"
            )
        lines.append("Reply 'cancel <BOOKING_ID>' to cancel a booking.")
        return _reply("<br/>".join(lines))

    if any(
        k in m
        for k in [
            "room service",
            "complaint",
            "issue",
            "problem",
            "support",
            "maintenance",
            "housekeeping",
            "cleaning",
            "lost",
        ]
    ):
        user_id = session.get("user_id")
        requester = session.get("user_name") or session.get("user_email") or "Guest"
        ticket_id = f"REQ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        routed = _route_to_admin(
            "Chatbot Request",
            f"{ticket_id} | From: {requester} | User ID: {user_id or 'N/A'} | Message: {message}",
        )
        if routed:
            return _reply(_t("request_routed", lang, ticket_id=ticket_id))
        return _reply(_t("request_not_routed", lang))

    system_prompt = _build_system_prompt(lang)
    history = _get_ai_history()
    ai_reply, ai_error = generate_ai_reply(message, history, system_prompt)
    if ai_reply:
        safe_reply = _sanitize_ai(ai_reply)
        _append_ai_history(message, ai_reply)
        return _reply(safe_reply)
    if ai_error == "missing_api_key":
        return _reply(
            "AI chatbot is not configured. Set GEMINI_API_KEY and restart the server."
        )

    return _reply(_t("help", lang))


@chatbot_bp.route("/api/chatbot/history", methods=["GET"])
def chatbot_history():
    chat_user_id = _get_chat_user_id()
    messages = _load_chat_history(chat_user_id, limit=30)
    return jsonify({"ok": True, "messages": messages})
