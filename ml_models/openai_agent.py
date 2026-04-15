"""
openai_agent.py
---------------
Blissful Abodes — Unified AI Decision Agent
Primary provider: Google Gemini (gemini-1.5-flash)
All three assistant roles (Guest Concierge, Manager, Staff) use Gemini.
"""

import os
import json
import warnings

try:
    import google.genai as genai
    _GENAI_AVAILABLE = True
    _GENAI_PACKAGE = "google.genai"
except ImportError:
    try:
        import google.generativeai as genai
        _GENAI_AVAILABLE = True
        _GENAI_PACKAGE = "google.generativeai"
        warnings.warn(
            "google.generativeai is deprecated. Install google-genai and update imports to google.genai.",
            DeprecationWarning,
            stacklevel=2,
        )
    except ImportError:
        _GENAI_AVAILABLE = False
        _GENAI_PACKAGE = None

from ml_models.external_apis import (
    StripeRadarAPI,
    AWSForecastAPI,
    GoogleTravelAPI,
    AWSPersonalizeAPI,
)


class OpenAIDecisionAgent:
    """
    Unified AI agent — now powered exclusively by Gemini.
    The class name is kept for backward compatibility with all existing imports.
    """

    def __init__(self):
        self._gemini_model = None

    @property
    def gemini_key(self):
        """Always read fresh from environment so dotenv changes are picked up."""
        return os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

    @property
    def gemini_model(self):
        """Lazily initialise Gemini on first real use. Retries if key is now available."""
        if self._gemini_model is None and self.gemini_key and _GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.gemini_key)
                self._gemini_model = genai.GenerativeModel("gemini-2.5-flash")
            except Exception as e:
                print(f"[Gemini] Failed to initialise: {e}")
        return self._gemini_model

    def is_configured(self):
        return bool(self.gemini_key) and _GENAI_AVAILABLE

    # ── internal helpers ──────────────────────────────────────────────────────

    def _gemini_chat(self, system_prompt: str, user_msg: str,
                     history: list = None, temperature: float = 0.4) -> str:
        """Send a message to Gemini and return the text reply."""
        if not self.gemini_model:
            return None
        try:
            full_prompt = f"{system_prompt}\n\nUser: {user_msg}"
            if history:
                # Build a simple multi-turn string context
                ctx = "\n".join(
                    f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}"
                    for m in history[-6:]
                )
                full_prompt = f"{system_prompt}\n\n{ctx}\nUser: {user_msg}"
            response = self.gemini_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            print(f"[Gemini] API error: {e}")
            return None

    def _extract_json(self, text: str):
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            return text[start:end]
        return None

    # ── public handlers ───────────────────────────────────────────────────────

    def handle_message(self, user_msg: str, user_id: str,
                       booking_state: dict, chat_history: list = None) -> dict:
        """
        Guest AI Concierge — handles booking intents, recommendations, and Q&A.
        Returns: {"text": str, "state_updates": dict}
        """
        if not self.is_configured():
            return {
                "text": "AI Concierge is offline. Please set the GEMINI_API_KEY in your .env file.",
                "state_updates": {}
            }

        system_prompt = self._get_system_prompt()
        ai_text = self._gemini_chat(system_prompt, user_msg, history=chat_history)

        if ai_text is None:
            return {"text": "Sorry, I couldn't connect to the AI right now. Please try again.", "state_updates": {}}

        result = {"text": ai_text, "state_updates": {}}

        # Try to extract structured JSON intent from the reply
        json_payload = self._extract_json(ai_text)
        if json_payload:
            try:
                data = json.loads(json_payload)
                if "reply" in data:
                    result["text"] = data["reply"]
                if "intent" in data:
                    result["state_updates"]["intent"] = data["intent"]
                if "booking" in data:
                    b = data["booking"]
                    if b.get("room_type"):
                        result["state_updates"]["room_type"] = b["room_type"]
                    if b.get("check_in"):
                        result["state_updates"]["check_in"] = b["check_in"]
                    if b.get("guests"):
                        result["state_updates"]["guests"] = b["guests"]

                # External API integrations
                if data.get("intent") == "confirm_booking":
                    fraud_res = StripeRadarAPI.analyze_transaction({
                        "total_amount": booking_state.get("total_price", 5000),
                    })
                    result["fraud_assessment"] = fraud_res
                elif data.get("intent") == "recommend":
                    rec_res = AWSPersonalizeAPI.get_user_recommendations(user_id)
                    result["aws_recommendation"] = rec_res
            except Exception:
                pass

        return result

    def handle_manager_message(self, user_msg: str, manager_context: dict) -> str:
        """Manager AI Assistant — answers operational KPI questions."""
        if not self.is_configured():
            return (
                f"AI Assistant offline. Revenue today: ₹{manager_context.get('today_revenue', 0)}"
            )

        system_prompt = f"""You are the Executive AI Assistant for the Hotel Manager at Blissful Abodes Chennai.
Answer professionally with emojis. Use ONLY the live context below for data questions.

Revenue Today     : ₹{manager_context.get('today_revenue', 0)}
Monthly Revenue   : ₹{manager_context.get('monthly_revenue', 0)}
Occupancy Rate    : {manager_context.get('occupancy', 0)}%
Pending Tasks     : {manager_context.get('pending_tasks', 0)}
Fraud Alerts      : {manager_context.get('fraud_count', 0)}
"""
        reply = self._gemini_chat(system_prompt, user_msg)
        return reply or "Sorry, I couldn't reach the AI right now. Please try again."

    def handle_staff_message(self, user_msg: str, staff_context: dict) -> str:
        """Staff Operations AI — helps with task prioritisation and check-ins."""
        if not self.is_configured():
            return (
                f"Offline Mode: You have {staff_context.get('pending_tasks', 0)} pending tasks "
                f"and {staff_context.get('checkins_today', 0)} check-ins today."
            )

        system_prompt = f"""You are the Operations AI Assistant for Hotel Staff at Blissful Abodes Chennai.
Answer professionally with emojis. Tell staff their next priority task when asked.

Pending Tasks     : {staff_context.get('pending_tasks', 0)}
Urgent Tasks      : {staff_context.get('urgent_tasks', 0)}
Check-ins Today   : {staff_context.get('checkins_today', 0)}
Rooms to Clean    : {staff_context.get('cleaning_rooms', 0)}
Next Priority Task: {staff_context.get('next_task', 'None')}
"""
        reply = self._gemini_chat(system_prompt, user_msg)
        return reply or "Sorry, I couldn't reach the AI right now. Please try again."

    def _get_system_prompt(self) -> str:
        return """You are Aria, the AI Concierge for Blissful Abodes Chennai Luxury Hotel.
You help guests book rooms, get recommendations, and answer hotel questions.

If the user wants to book a room, output a JSON block merged into your reply:
```json
{
    "reply": "Your friendly text here...",
    "intent": "book",
    "booking": {"room_type": "VIP Suite", "check_in": "YYYY-MM-DD", "guests": 2}
}
```
Possible intents: [general, search, book, confirm_booking, recommend].
Always be warm, professional, and use emojis 🌟."""


# Singleton instance — imported throughout the app
openai_agent = OpenAIDecisionAgent()
