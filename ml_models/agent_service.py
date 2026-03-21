from __future__ import annotations

import asyncio
import json
import os
import random
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.database import get_db
from services.security import hash_password
from ml_models.models import get_pricing_engine, get_recommendation_model, get_fraud_detector

types = None
Runner = None
google_search = None
LlmAgent = None
InMemorySessionService = None
_ADK_AVAILABLE = False
_ADK_ERROR = ""

chat_memory = {}


def save_chat(user_id, message):
    if not user_id or not message:
        return []
    history = chat_memory.setdefault(user_id, [])
    history.append(message)
    if len(history) > 30:
        del history[:-30]
    return history


def _try_load_adk() -> bool:
    global types, Runner, google_search, LlmAgent, InMemorySessionService
    global _ADK_AVAILABLE, _ADK_ERROR
    if _ADK_AVAILABLE:
        return True
    try:
        from google.genai import types as _types
        from google.adk.runners import Runner as _Runner
        from google.adk.tools import google_search as _google_search
        from google.adk.agents import LlmAgent as _LlmAgent
        from google.adk.sessions import InMemorySessionService as _InMemorySessionService

        types = _types
        Runner = _Runner
        google_search = _google_search
        LlmAgent = _LlmAgent
        InMemorySessionService = _InMemorySessionService
        _ADK_AVAILABLE = True
        _ADK_ERROR = ""
        return True
    except BaseException as exc:  # pragma: no cover
        _ADK_AVAILABLE = False
        _ADK_ERROR = str(exc)
        return False


APP_NAME = "hotels_app"

HOTEL_SEARCH_AGENT_INSTRUCTIONS = """
You are a hotel search assistant. Your goal is to find hotel names and basic
information based on the user's query.

Workflow:
1. Use Google Search to find hotels based on the user's location query.
2. Extract the hotel name, its general location (city), a rating, and a cost.
3. Return a JSON object with a "text" field and a "hotels" list:
   {
     "text": "Optional intro",
     "hotels": [
       {"hotel_name": "...", "location": "...", "rating": 4.5, "cost": 12000}
     ]
   }
4. Limit to 15 hotels.
"""

BOOKING_AGENT_INSTRUCTIONS = """
You are a hotel booking assistant. Help users complete bookings in a step-by-step
flow: choose room type, dates, guests, confirm.
"""


def _get_gemini_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        return api_key
    try:
        from flask import current_app

        return current_app.config.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


def _extract_json_payload(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.replace("```json", "").replace("```", "").strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else None


def _fallback_local_rooms() -> Dict[str, Any]:
    try:
        conn = get_db()
        rows = conn.execute(
            """SELECT room_type, MIN(current_price) as price
               FROM rooms WHERE is_active = 1
               GROUP BY room_type
               ORDER BY price"""
        ).fetchall()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        return {
            "type": "text",
            "text": "Search is unavailable right now. Please try again later.",
        }

    lines = ["Search is unavailable. Here are our room types:"]
    for r in rows:
        price = r["price"] if isinstance(r, dict) else r[1]
        room_type = r["room_type"] if isinstance(r, dict) else r[0]
        try:
            price_text = f"INR {int(price)}"
        except Exception:
            price_text = "Price on request"
        lines.append(f"- {room_type}: {price_text} per night")
    return {"type": "text", "text": "\n".join(lines)}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _resolve_date_range(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    check_in, check_out = _parse_dates(prompt)
    if check_in and check_out:
        return check_in, check_out
    if check_in and not check_out:
        ci = datetime.strptime(check_in, "%Y-%m-%d").date()
        co = ci + timedelta(days=1)
        return ci.isoformat(), co.isoformat()
    text = _normalize(prompt)
    today = datetime.now().date()
    if "tomorrow" in text:
        ci = today + timedelta(days=1)
        co = ci + timedelta(days=1)
        return ci.isoformat(), co.isoformat()
    if "today" in text:
        ci = today
        co = today + timedelta(days=1)
        return ci.isoformat(), co.isoformat()
    if "next week" in text:
        ci = today + timedelta(days=7)
        co = ci + timedelta(days=1)
        return ci.isoformat(), co.isoformat()
    return None, None


def _get_room_types_from_db() -> List[Dict[str, str]]:
    conn = get_db()
    rows = conn.execute(
        """SELECT room_type, COALESCE(MAX(description), '') as description
           FROM rooms WHERE is_active = 1 GROUP BY room_type ORDER BY room_type"""
    ).fetchall()
    conn.close()
    return [
        {"type": r["room_type"], "description": r["description"] or ""}
        for r in rows
    ]


def _detect_room_type(prompt: str, room_types: List[Dict[str, str]]) -> Optional[str]:
    text = _normalize(prompt)
    for rt in room_types:
        if rt["type"].lower() in text:
            return rt["type"]
    if "deluxe" in text:
        return "Deluxe Room"
    if "suite" in text:
        return "Executive Suite"
    if "standard" in text:
        return "Standard Room"
    return None


def _select_available_room(room_type: str, check_in: str, check_out: str):
    conn = get_db()
    room = conn.execute(
        """SELECT * FROM rooms
           WHERE room_type = ? AND status = 'available' AND is_active = 1
           AND room_id NOT IN (
               SELECT room_id FROM bookings
               WHERE status IN ('confirmed','reserved','pending')
               AND NOT (check_out <= ? OR check_in >= ?)
           )
           ORDER BY current_price ASC
           LIMIT 1""",
        (room_type, check_in, check_out),
    ).fetchone()
    conn.close()
    return dict(room) if room else None


def _calculate_price(room_type: str, check_in: str, nights: int, base_price: float) -> float:
    try:
        conn = get_db()
        occ = conn.execute(
            "SELECT COUNT(*) FROM rooms WHERE status IN ('occupied','reserved')"
        ).fetchone()[0]
        total_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        conn.close()
        occ_pct = round(occ / max(total_rooms, 1) * 100, 1)
        days_until = (datetime.strptime(check_in, "%Y-%m-%d").date() - datetime.now().date()).days
        pricing_engine = get_pricing_engine()
        pricing = pricing_engine.calculate_price(
            room_type,
            check_in,
            occ_pct,
            days_until,
            base_price=base_price,
        )
        return float(pricing.get("final_price", base_price)) * nights
    except Exception:
        return float(base_price) * nights


def _ensure_agent_guest(agent_user_id: str) -> str:
    conn = get_db()
    row = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?", (agent_user_id,)
    ).fetchone()
    if row:
        conn.close()
        return agent_user_id

    email = f"agent_{agent_user_id}@blissful.temp"
    pwd_hash = hash_password("TempPass123")
    conn.execute(
        """INSERT INTO users
        (user_id, email, phone, password_hash, first_name, last_name, role, is_active, is_verified)
        VALUES (?, ?, '', ?, 'Agent', 'Guest', 'guest', 1, 0)""",
        (agent_user_id, email, pwd_hash),
    )
    conn.commit()
    conn.close()
    return agent_user_id


def _fraud_check_booking(
    user_id: Optional[str],
    agent_user_id: str,
    total_amount: float,
    guests: int,
    payment_method: str,
):
    uid = user_id or agent_user_id
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
    booking_count = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE user_id = ?", (uid,)
    ).fetchone()[0]
    conn.close()
    user_dict = dict(user) if user else {}
    booking_data = {
        "total_amount": total_amount,
        "payment_method": payment_method,
        "num_guests": guests,
        "is_new_user": booking_count == 0,
        "email": user_dict.get("email", ""),
    }
    fraud_detector = get_fraud_detector()
    return fraud_detector.predict(booking_data)


def _create_booking(user_id: Optional[str], agent_user_id: str, room, check_in, check_out, guests):
    if not user_id:
        return None, "Please log in to complete a booking.", None

    ci = datetime.strptime(check_in, "%Y-%m-%d")
    co = datetime.strptime(check_out, "%Y-%m-%d")
    if ci.date() < datetime.now().date():
        return None, "Check-in date cannot be in the past."
    nights = (co - ci).days
    if nights <= 0:
        return None, "Invalid dates."
    if guests > int(room.get("max_guests", 1)):
        return None, "Guest count exceeds room capacity."

    base_amount = _calculate_price(
        room["room_type"], check_in, nights, room["current_price"]
    )
    gst = base_amount * 0.18
    total_amount = base_amount + gst

    fraud_result = _fraud_check_booking(
        user_id, agent_user_id, total_amount, guests, "pay_at_hotel"
    )
    fraud_score = float(fraud_result.get("fraud_score", 0) or 0)
    risk_level = str(fraud_result.get("risk_level", "")).upper()
    fraud_flags = fraud_result.get("flags") or []
    if not isinstance(fraud_flags, list):
        fraud_flags = [str(fraud_flags)]
    is_flagged = 1 if (
        fraud_result.get("is_suspicious")
        or fraud_score >= 0.35
        or risk_level in ("REVIEW", "FRAUD", "HIGH")
    ) else 0
    status = "pending" if is_flagged else "confirmed"

    booking_id = f"BK{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    conn = get_db()
    conn.execute(
        """INSERT INTO bookings
        (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
         base_amount, gst_amount, total_amount, status, payment_status, payment_method,
         fraud_score, is_flagged, fraud_flags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pay_at_hotel', ?, ?, ?)""",
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
            fraud_result.get("fraud_score", 0),
            is_flagged,
            json.dumps(fraud_flags),
        ),
    )
    conn.execute(
        "UPDATE rooms SET status = ? WHERE room_id = ?",
        ("reserved", room["room_id"]),
    )
    conn.commit()
    conn.close()
    return booking_id, None, fraud_result


def _cancel_booking(user_id: Optional[str], agent_user_id: str, booking_id: str):
    if not user_id:
        user_id = agent_user_id
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
    conn.execute(
        "UPDATE bookings SET status = 'cancelled', updated_at = ? WHERE booking_id = ?",
        (datetime.now().isoformat(), booking_id),
    )
    conn.execute(
        "UPDATE rooms SET status = 'available' WHERE room_id = ?", (booking["room_id"],)
    )
    conn.commit()
    conn.close()
    return True, None


def _get_room_prices() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute(
        """SELECT room_type, MIN(current_price) as price
           FROM rooms WHERE is_active = 1 GROUP BY room_type ORDER BY price"""
    ).fetchall()
    conn.close()
    return [{"room_type": r["room_type"], "price": r["price"]} for r in rows]


def _price_map() -> Dict[str, float]:
    return {p["room_type"]: p["price"] for p in _get_room_prices() if p.get("price")}


def _hotel_information() -> str:
    try:
        from flask import current_app

        name = current_app.config.get("HOTEL_NAME", "Blissful Abodes Chennai")
        address = current_app.config.get("HOTEL_ADDRESS", "")
        phone = current_app.config.get("HOTEL_PHONE", "")
        email = current_app.config.get("HOTEL_EMAIL", "")
    except Exception:
        name = "Blissful Abodes Chennai"
        address = "123 Marina Beach Road, Chennai"
        phone = "+91 44 2345 6789"
        email = "info@blissfulabodes.com"
    return (
        f"{name}\nAddress: {address}\nPhone: {phone}\nEmail: {email}\n"
        "Amenities: Wi-Fi, AC, breakfast, room service, parking, and concierge."
    )


def _extract_booking_id(prompt: str) -> Optional[str]:
    match = re.search(r"\b(BK\d{6,}|HTL\d{6,}|WI\d{6,})\b", prompt.upper())
    return match.group(1) if match else None


def _list_available_rooms(check_in: str, check_out: str, room_type: Optional[str], limit: int = 5):
    conn = get_db()
    params = [check_in, check_out]
    room_type_clause = ""
    if room_type:
        room_type_clause = "AND room_type = ?"
        params = [room_type] + params
    query = f"""
        SELECT room_number, room_type, current_price, max_guests
        FROM rooms
        WHERE is_active = 1 AND status = 'available' {room_type_clause}
        AND room_id NOT IN (
            SELECT room_id FROM bookings
            WHERE status IN ('confirmed','reserved','pending')
            AND NOT (check_out <= ? OR check_in >= ?)
        )
        ORDER BY current_price ASC
        LIMIT {limit}
    """
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_room_availability(prompt: str) -> Dict[str, Any]:
    check_in, check_out = _resolve_date_range(prompt)
    if not check_in or not check_out:
        return {
            "type": "text",
            "text": "Please provide check-in and check-out dates (YYYY-MM-DD).",
        }
    room_types = get_room_types()
    selected_type = _detect_room_type(prompt, room_types)
    rooms = _list_available_rooms(check_in, check_out, selected_type)
    if not rooms:
        return {
            "type": "text",
            "text": f"No rooms available for {check_in} to {check_out}. Try different dates or room type.",
        }
    lines = [
        f"Available rooms for {check_in} to {check_out}:",
    ]
    for r in rooms:
        lines.append(
            f"- Room {r['room_number']} ({r['room_type']}) • ₹{int(r['current_price'])}/night • Max {r['max_guests']} guests"
        )
    return {"type": "text", "text": "\n".join(lines)}


def get_room_prices() -> Dict[str, Any]:
    prices = _get_room_prices()
    if not prices:
        return {"type": "text", "text": "No room pricing data available."}
    lines = ["Room prices (per night):"]
    for p in prices:
        lines.append(f"- {p['room_type']}: ₹{int(p['price'])}")
    return {"type": "text", "text": "\n".join(lines)}


def recommend_rooms(user_id: Optional[str], agent_user_id: str) -> Dict[str, Any]:
    uid = user_id or agent_user_id
    recommender = get_recommendation_model()
    recs = recommender.get_recommendations(uid, n=4)
    price_map = _price_map()
    if not recs:
        return {"type": "text", "text": "No recommendations available right now."}
    lines = ["Recommended rooms for you:"]
    for rec in recs:
        room_type = rec.get("room_type", "Room")
        score = rec.get("match_score", 0)
        reason = rec.get("reason", "Recommended for you")
        price = price_map.get(room_type)
        price_text = f" • ₹{int(price)}/night" if price else ""
        lines.append(f"- {room_type}{price_text} • {score}% match • {reason}")
    return {"type": "text", "text": "\n".join(lines)}


def _fallback_search_hotels(prompt: str) -> Dict[str, Any]:
    try:
        from services.ai_chat_service import generate_ai_reply
    except Exception:
        return _fallback_local_rooms()

    system_prompt = (
        "You are a hotel search assistant. Use your knowledge to suggest hotels. "
        "Return ONLY valid JSON in this format:\n"
        '{ "text": "optional intro", "hotels": ['
        '{"hotel_name":"...", "location":"...", "rating":4.5, "cost":12000} ] } '
        "Limit to 8 hotels. If unsure, return an empty hotels list."
    )
    reply, err = generate_ai_reply(
        prompt, history=[], system_prompt=system_prompt, temperature=0.2, max_tokens=700
    )
    if err == "missing_api_key":
        return _fallback_local_rooms()
    if not reply:
        return _fallback_local_rooms()

    payload = _extract_json_payload(reply)
    if not payload:
        return {"type": "text", "text": reply} if reply else _fallback_local_rooms()

    try:
        data = json.loads(payload)
    except Exception:
        return {"type": "text", "text": reply} if reply else _fallback_local_rooms()

    hotels = []
    for item in data.get("hotels", []) or []:
        if not isinstance(item, dict):
            continue
        hotels.append(
            {
                "hotel_name": item.get("hotel_name")
                or item.get("name")
                or "Hotel",
                "location": item.get("location") or item.get("city") or "",
                "rating": item.get("rating") or item.get("stars") or 0,
                "price": item.get("cost") or item.get("price") or 0,
                "link": item.get("link") or "",
            }
        )
    if hotels:
        return {"type": "hotels", "text": data.get("text", ""), "hotels": hotels}

    if data.get("text"):
        return {"type": "text", "text": data.get("text")}
    return {"type": "text", "text": reply}


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _default_booking_state():
    return {
        "active": False,
        "hotel_name": "",
        "room_type": "",
        "check_in": "",
        "check_out": "",
        "guests": 0,
        "total_price": 0,
        "step": "initial",
        "booking_id": "",
    }


def detect_booking_intent(prompt: str) -> bool:
    booking_keywords = [
        "book",
        "booking",
        "reserve",
        "reservation",
        "proceed to booking",
        "i want to book",
        "book hotel",
        "make a booking",
        "reserve hotel",
    ]
    return any(keyword in prompt.lower() for keyword in booking_keywords)


def detect_intent(prompt: str) -> str:
    text = _normalize(prompt)
    if any(k in text for k in ["cancel", "cancellation", "refund"]):
        return "cancel"
    if any(k in text for k in ["price", "cost", "rate", "tariff"]):
        return "price"
    if any(k in text for k in ["book", "booking", "reserve", "reservation"]):
        return "book"
    if any(k in text for k in ["recommend", "suggest", "best room", "which room"]):
        return "recommend"
    if any(k in text for k in ["available", "availability", "vacancy", "rooms available"]):
        return "check_room"
    if any(
        k in text
        for k in [
            "where",
            "address",
            "location",
            "wifi",
            "amenities",
            "services",
            "check-in",
            "check out",
            "contact",
            "phone",
            "email",
            "hotel info",
        ]
    ):
        return "info"
    return "search"


def detect_emotion(prompt: str) -> str:
    text = _normalize(prompt)
    if any(k in text for k in ["tired", "exhausted", "sleepy", "fatigued", "burnout", "stress"]):
        return "tired"
    if any(k in text for k in ["stressed", "anxious", "overworked", "overwhelm", "frustrated"]):
        return "stressed"
    if any(k in text for k in ["happy", "excited", "celebrating", "honeymoon", "anniversary", "birthday", "special occasion"]):
        return "celebrating"
    return "neutral"


def _emotion_suggestion(emotion: str) -> str:
    if emotion == "tired":
        return "I can see you're feeling tired. I highly recommend our Executive Suite with a deep soaking tub and blackout curtains for maximum relaxation. "
    if emotion == "stressed":
        return "Need to unwind? Our VIP Suite includes complimentary spa access to melt the stress away. "
    if emotion == "celebrating":
        return "Celebrating a special occasion? Our Couple Suite is perfect for a romantic and unforgettable getaway! "
    return ""


def extract_hotel_name_from_booking_request(prompt: str) -> str:
    prompt_lower = prompt.lower()
    if "book" in prompt_lower:
        parts = prompt_lower.split("book")
        if len(parts) > 1:
            hotel_part = parts[1].strip()
            hotel_part = hotel_part.replace("the ", "").replace("hotel", "").strip()
            if any(
                k in hotel_part
                for k in ["room", "suite", "deluxe", "standard", "executive", "vip"]
            ):
                return ""
            return hotel_part.title()
    return ""


def get_room_types():
    room_types = _get_room_types_from_db()
    if room_types:
        return room_types
    return [
        {"type": "Standard Room", "description": "Basic amenities, city view"},
        {"type": "Deluxe Room", "description": "Premium amenities, partial city view"},
        {
            "type": "Executive Suite",
            "description": "Spacious suite, city view, executive lounge access",
        },
        {
            "type": "Presidential Suite",
            "description": "Luxury suite, panoramic view, butler service",
        },
    ]


def _parse_dates(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    matches = re.findall(r"\d{4}-\d{2}-\d{2}", prompt)
    if matches:
        if len(matches) >= 2:
            return matches[0], matches[1]
        return matches[0], None

    alt_matches = re.findall(r"\d{2}[/-]\d{2}[/-]\d{4}", prompt)
    parsed = []
    for m in alt_matches:
        try:
            parsed.append(datetime.strptime(m.replace("/", "-"), "%d-%m-%Y").date().isoformat())
        except Exception:
            continue
    if len(parsed) >= 2:
        return parsed[0], parsed[1]
    if len(parsed) == 1:
        return parsed[0], None
    return None, None


def process_booking_step(
    prompt: str,
    state: Dict[str, Any],
    user_id: Optional[str],
    agent_user_id: str,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    state = dict(state or _default_booking_state())
    current_step = state.get("step", "initial")
    room_types = get_room_types()

    if current_step == "initial":
        hotel_name = extract_hotel_name_from_booking_request(prompt)
        if hotel_name:
            state["hotel_name"] = hotel_name
        state["step"] = "room_selection"
        state["active"] = True
        text = (
            f"I can help you book {state['hotel_name']}." if state["hotel_name"] else "I can help you book a hotel."
        )
        return text + " Please select a room type.", state, {"room_types": room_types}

    if current_step == "room_selection":
        selected_room = _detect_room_type(prompt, room_types)
        if selected_room:
            state["room_type"] = selected_room
            state["step"] = "date_selection"
            return (
                f"Selected {selected_room}. Provide check-in and check-out dates (YYYY-MM-DD).",
                state,
                {},
            )
        return "Please select one of the available room types.", state, {"room_types": room_types}

    if current_step == "date_selection":
        check_in, check_out = _parse_dates(prompt)
        if check_in and check_out:
            state["check_in"] = check_in
            state["check_out"] = check_out
            available_room = _select_available_room(state["room_type"], check_in, check_out)
            if not available_room:
                return (
                    "No rooms available for those dates. Please choose different dates.",
                    state,
                    {},
                )
            state["step"] = "guest_selection"
            return "Thanks. How many guests?", state, {}
        return "Please provide check-in and check-out dates (YYYY-MM-DD).", state, {}

    if current_step == "guest_selection":
        numbers = re.findall(r"\d+", prompt)
        if numbers:
            guests = int(numbers[0])
            state["guests"] = guests
            state["step"] = "confirmation"
            ci = datetime.strptime(state["check_in"], "%Y-%m-%d")
            co = datetime.strptime(state["check_out"], "%Y-%m-%d")
            nights = max((co - ci).days, 1)
            room = _select_available_room(state["room_type"], state["check_in"], state["check_out"])
            if not room:
                return (
                    "No rooms available for those dates. Please choose different dates.",
                    state,
                    {},
                )
            total_price = _calculate_price(
                room["room_type"], state["check_in"], nights, room["current_price"]
            )
            state["total_price"] = round(total_price, 2)
            text = (
                "Confirm booking details:\n"
                f"Hotel: {state.get('hotel_name', 'Selected Hotel')}\n"
                f"Room: {state['room_type']}\n"
                f"Check-in: {state['check_in']}\n"
                f"Check-out: {state['check_out']}\n"
                f"Guests: {guests}\n"
                f"Total Price: INR {total_price} ({nights} nights)\n"
                "Type 'confirm' to complete or 'cancel' to cancel."
            )
            return text, state, {}
        return "Please specify number of guests (e.g., '2 guests').", state, {}

    if current_step == "confirmation":
        if "confirm" in prompt.lower():
            room = _select_available_room(state["room_type"], state["check_in"], state["check_out"])
            if not room:
                return (
                    "No rooms available for those dates. Please choose different dates.",
                    state,
                    {},
                )
            booking_id, error, fraud_result = _create_booking(
                user_id, agent_user_id, room, state["check_in"], state["check_out"], state["guests"]
            )
            if error:
                return error, state, {}
            flagged = fraud_result and fraud_result.get("risk_level") == "HIGH"
            state["booking_id"] = booking_id
            state["step"] = "completed"
            state["active"] = False
            prefix = "Booking received and sent for review.\n" if flagged else "Booking confirmed.\n"
            text = (
                prefix
                + f"Booking ID: {booking_id}\n"
                + f"Hotel: {state.get('hotel_name', 'Selected Hotel')}\n"
                + f"Room: {state['room_type']}\n"
                + f"Check-in: {state['check_in']}\n"
                + f"Check-out: {state['check_out']}\n"
                + f"Guests: {state['guests']}\n"
                + f"Total Due: INR {state['total_price']}"
            )
            return text, state, {}
        if "cancel" in prompt.lower():
            return "Booking cancelled. How else can I help?", _default_booking_state(), {}
        return "Type 'confirm' to complete or 'cancel' to cancel.", state, {}

    return "I could not understand that. Please try again.", state, {}


def mock_api_get_hotel_prices(hotel_name: str) -> Dict[str, Dict[str, Any]]:
    booking_sites = [
        "Booking.com",
        "Agoda",
        "MakeMyTrip",
        "Trivago",
        "Hotels.com",
        "Expedia",
        "Goibibo",
        "Cleartrip",
    ]
    hotel_prices = {}
    for site in booking_sites:
        if random.random() <= 0.8:
            price = random.randint(5000, 20000)
            site_domain = site.lower().replace(" ", "").replace(".", "")
            mock_link = f"https://www.{site_domain}.com/hotel/{hotel_name.lower().replace(' ', '-')}"
            hotel_prices[site] = {
                "price": price,
                "available": True,
                "link": mock_link,
                "currency": "INR",
            }
        else:
            hotel_prices[site] = {
                "price": None,
                "available": False,
                "link": None,
                "currency": "INR",
            }
    return hotel_prices


def get_best_hotel_deals(hotels_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enhanced_hotels = []
    for hotel in hotels_list:
        hotel_name = hotel.get("hotel_name", "")
        location = hotel.get("location", "")
        site_prices = mock_api_get_hotel_prices(hotel_name)

        available_prices = [
            {"site": site, "price": details["price"], "link": details["link"]}
            for site, details in site_prices.items()
            if details["available"] and details.get("price") is not None
        ]

        rating_from_agent = hotel.get("rating")
        safe_rating = rating_from_agent if rating_from_agent is not None else 0

        if available_prices:
            best_deal = min(available_prices, key=lambda x: x["price"])
            enhanced_hotel = {
                "hotel_name": hotel_name,
                "location": location,
                "price": best_deal["price"],
                "rating": safe_rating,
                "link": best_deal["link"],
                "price_source": best_deal["site"],
                "all_prices": site_prices,
            }
        else:
            enhanced_hotel = {
                "hotel_name": hotel_name,
                "location": location,
                "price": 0,
                "rating": safe_rating,
                "link": "",
                "price_source": "Not Available",
                "all_prices": site_prices,
            }
        enhanced_hotels.append(enhanced_hotel)

    enhanced_hotels.sort(key=lambda x: (x["price"] == 0, x["price"]))
    return enhanced_hotels


class AgentRuntime:
    def __init__(self):
        self.available = False
        self.error = ""
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            self.error = "Set GEMINI_API_KEY (or GOOGLE_API_KEY) to enable the agent."
            return
        os.environ.setdefault("GOOGLE_API_KEY", api_key)
        if not _try_load_adk():
            self.error = f"Agent dependencies missing: {_ADK_ERROR}"
            return

        self.session_service = InMemorySessionService()
        self.search_agent = LlmAgent(
            name="hotel_search_agent",
            model="gemini-2.0-flash",
            description="Hotel Search Agent",
            instruction=HOTEL_SEARCH_AGENT_INSTRUCTIONS,
            generate_content_config=types.GenerateContentConfig(temperature=0),
            tools=[google_search],
        )
        self.booking_agent = LlmAgent(
            name="booking_agent",
            model="gemini-2.0-flash",
            description="Hotel Booking Agent",
            instruction=BOOKING_AGENT_INSTRUCTIONS,
            generate_content_config=types.GenerateContentConfig(temperature=0.3),
            tools=[],
        )

        self.search_runner = Runner(
            agent=self.search_agent, app_name=APP_NAME, session_service=self.session_service
        )
        self.booking_runner = Runner(
            agent=self.booking_agent, app_name=APP_NAME, session_service=self.session_service
        )
        self.available = True

    def ensure_session(self, user_id: str, session_id: str):
        if not self.available:
            return

        async def _ensure():
            try:
                await self.session_service.create_session(
                    app_name=APP_NAME, user_id=user_id, session_id=session_id
                )
            except Exception:
                return

        _run_async(_ensure())

    async def _run_agent(self, runner: Runner, user_id: str, session_id: str, prompt: str):
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        final_response_text = ""
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate:
                    final_response_text = event.error_message or "Agent escalated."
                break
        return final_response_text

    def search_hotels(self, user_id: str, session_id: str, prompt: str) -> Dict[str, Any]:
        if not self.available:
            return _fallback_search_hotels(prompt)

        self.ensure_session(user_id, session_id)
        try:
            response_text = _run_async(
                self._run_agent(self.search_runner, user_id, session_id, prompt)
            )
        except Exception:
            return _fallback_search_hotels(prompt)

        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        try:
            response_json = json.loads(cleaned)
            text_output = response_json.get("text")
            hotels = response_json.get("hotels")
            if hotels:
                enhanced = get_best_hotel_deals(hotels)
                return {"type": "hotels", "text": text_output or "", "hotels": enhanced}
            if text_output:
                return {"type": "text", "text": text_output}
            return {"type": "text", "text": response_text or "No results."}
        except Exception:
            return {"type": "text", "text": response_text or "No results."}


_runtime = AgentRuntime()


def get_agent_status() -> Dict[str, Any]:
    from ml_models.openai_agent import openai_agent
    if openai_agent.is_configured():
        return {"available": True, "message": "Unified AI Decision Layer Active (OpenAI)"}
    return {"available": False, "message": "Set OPENAI_API_KEY in environment to enable the AI Agent."}


def handle_agent_message(
    prompt: str,
    booking_state: Dict[str, Any],
    agent_user_id: str,
    session_id: str,
    logged_in_user_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    
    # --- ENTER OPENAI DECISION LAYER ---
    from ml_models.openai_agent import openai_agent
    
    ai_decision = openai_agent.handle_message(
        prompt, 
        logged_in_user_id or agent_user_id, 
        booking_state
    )
    
    text_prefix = ""
    if "fraud_assessment" in ai_decision:
        fraud = ai_decision["fraud_assessment"]
        text_prefix += f"🛡️ [Stripe/Sift API] Fraud Risk evaluated as {fraud.get('risk_assessment').upper()}.\n\n"
    if "aws_recommendation" in ai_decision:
        rec = ai_decision["aws_recommendation"]
        text_prefix += f"🎯 [AWS Personalize] AI Suggests {rec.get('recommended_tier').upper()} tier for you.\n\n"
        
    # Apply OpenAI's state mutations
    if ai_decision.get("state_updates"):
        booking_state.update(ai_decision["state_updates"])
    
    # Mix AI conversational response with logical steps
    emotion_prefix = text_prefix
    if ai_decision.get("text") and "Error contacting" not in ai_decision["text"]:
        emotion_prefix += ai_decision["text"] + "\n\n"
    else:
        emotion = detect_emotion(prompt)
        emotion_prefix += _emotion_suggestion(emotion)
        
    intent = booking_state.get("intent") or detect_intent(prompt)
    
    if emotion_prefix and intent == "search" and not booking_state.get("active"):
        intent = "recommend"

    if (booking_state.get("active") or intent == "book") and not logged_in_user_id:
        return {"type": "text", "text": emotion_prefix + "Please log in to book a room."}, booking_state
    if intent == "cancel" and not logged_in_user_id:
        return {"type": "text", "text": "Please log in to manage bookings."}, booking_state

    if booking_state.get("active") or intent == "book":
        text, new_state, extra = process_booking_step(
            prompt, booking_state, logged_in_user_id, agent_user_id
        )
        payload = {"type": "booking", "text": emotion_prefix + text}
        payload.update(extra)
        return payload, new_state

    if intent == "check_room":
        res = check_room_availability(prompt)
        if emotion_prefix and isinstance(res, dict) and "text" in res:
            res["text"] = emotion_prefix + "\n\n" + res["text"]
        return res, booking_state

    if intent == "price":
        res = get_room_prices()
        if emotion_prefix and isinstance(res, dict) and "text" in res:
            res["text"] = emotion_prefix + "\n\n" + res["text"]
        return res, booking_state

    if intent == "recommend":
        res = recommend_rooms(logged_in_user_id, agent_user_id)
        if emotion_prefix and isinstance(res, dict) and "text" in res:
            res["text"] = emotion_prefix + "\n\n" + res["text"]
        return res, booking_state

    if intent == "info":
        return {"type": "text", "text": emotion_prefix + _hotel_information()}, booking_state

    if intent == "cancel":
        booking_id = _extract_booking_id(prompt)
        if not booking_id:
            return {"type": "text", "text": "Please share your booking ID (e.g., BK20260312001)."}, booking_state
        ok, err = _cancel_booking(logged_in_user_id, agent_user_id, booking_id)
        if err == "not_found":
            return {"type": "text", "text": "Booking not found. Please verify the booking ID."}, booking_state
        if err == "not_allowed":
            return {"type": "text", "text": "This booking cannot be cancelled."}, booking_state
        return {"type": "text", "text": f"Booking {booking_id} has been cancelled."}, booking_state

    result = _runtime.search_hotels(agent_user_id, session_id, prompt)
    return result, booking_state


def ensure_ids(session: Dict[str, Any]) -> Tuple[str, str]:
    user_id = session.get("agent_user_id")
    if not user_id:
        user_id = f"web_{uuid.uuid4().hex[:12]}"
        session["agent_user_id"] = user_id
    session_id = session.get("agent_session_id")
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session["agent_session_id"] = session_id
    return user_id, session_id


def get_booking_state(session: Dict[str, Any]) -> Dict[str, Any]:
    state = session.get("agent_booking_state")
    if not state:
        state = _default_booking_state()
        session["agent_booking_state"] = state
    return state
