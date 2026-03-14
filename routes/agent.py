from flask import Blueprint, render_template, request, session, jsonify
from functools import wraps
from models.database import get_db
from ml_models.agent_service import (
    ensure_ids,
    get_agent_status,
    get_booking_state,
    handle_agent_message,
)

agent_bp = Blueprint("agent", __name__)


def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"ok": False, "error": "Login required"}), 401
        return f(*args, **kwargs)

    return decorated


def _get_agent_history_id():
    if session.get("user_id"):
        return f"agent_{session['user_id']}"
    anon = session.get("agent_user_id")
    if anon:
        return f"agent_{anon}"
    return None


def _save_agent_message(agent_history_id, role, content):
    if not agent_history_id or not content:
        return
    conn = get_db()
    conn.execute(
        """INSERT INTO chatbot_messages (user_id, role, content)
           VALUES (?, ?, ?)""",
        (agent_history_id, role, content),
    )
    conn.commit()
    conn.close()


@agent_bp.route("/agent", methods=["GET"])
def agent_home():
    messages = session.get("agent_messages", [])
    status = get_agent_status()
    return render_template("public/agent.html", messages=messages, agent_status=status)


@agent_bp.route("/agent/message", methods=["POST"])
@login_required_api
def agent_message():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("message") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "Message required"}), 400

    user_id, session_id = ensure_ids(session)
    booking_state = get_booking_state(session)

    messages = session.get("agent_messages", [])
    messages.append({"role": "user", "type": "text", "text": prompt})
    _save_agent_message(_get_agent_history_id(), "user", prompt)

    logged_in_user_id = session.get("user_id")
    try:
        response, new_state = handle_agent_message(
            prompt, booking_state, user_id, session_id, logged_in_user_id
        )
    except Exception:
        return jsonify({"ok": False, "error": "Agent is temporarily unavailable."}), 500
    session["agent_booking_state"] = new_state

    assistant_message = {
        "role": "assistant",
        "type": response.get("type", "text"),
        "text": response.get("text", ""),
        "hotels": response.get("hotels", []),
        "room_types": response.get("room_types", []),
    }
    messages.append(assistant_message)
    _save_agent_message(_get_agent_history_id(), "assistant", assistant_message.get("text", ""))
    session["agent_messages"] = messages

    return jsonify({"ok": True, "message": assistant_message})


@agent_bp.route("/agent/reset", methods=["POST"])
def agent_reset():
    session.pop("agent_messages", None)
    session.pop("agent_booking_state", None)
    return jsonify({"ok": True})
