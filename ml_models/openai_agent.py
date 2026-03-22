import os
import json
from openai import OpenAI
from ml_models.external_apis import (
    StripeRadarAPI,
    AWSForecastAPI,
    GoogleTravelAPI,
    AWSPersonalizeAPI
)

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

class OpenAIDecisionAgent:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)

        # Gemini fallback
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_model = None
        if self.gemini_key and _GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            except Exception:
                self.gemini_model = None

    def _call_gemini(self, system_prompt: str, user_msg: str) -> str:
        """Fallback AI call using Google Gemini."""
        if not self.gemini_model:
            return None
        try:
            full_prompt = f"{system_prompt}\n\nUser: {user_msg}"
            response = self.gemini_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return None

    def is_configured(self):
        return (bool(self.client) and bool(self.api_key)) or bool(self.gemini_model)


    def handle_message(self, user_msg: str, user_id: str, booking_state: dict, chat_history: list = None) -> dict:
        """
        The central AI Decision Layer processing the user request.
        Combines OpenAI's conversational logic with real-time API integrations.
        
        Returns a dict:
        {
            "text": "The response to show the user",
            "hotels": [list of hotels if a search],
            "state_updates": {dict of updates to booking_state}
        }
        """
        if not self.is_configured():
            # FALLBACK FOR TESTING PURPOSES
            if "book" in user_msg.lower():
                mock_json_payload = '{"reply": "Let me arrange that VIP Suite for you!", "intent": "confirm_booking", "booking": {"room_type": "vip", "guests": 2, "check_in": "2026-05-01"}}'
                response = type('Response', (), {'choices': [type('Choice', (), {'message': type('Message', (), {'content': mock_json_payload})()})()]})()
                ai_text = mock_json_payload
            elif "recommend" in user_msg.lower():
                mock_json_payload = '{"reply": "Here are some great options based on your profile.", "intent": "recommend", "booking": {}}'
                response = type('Response', (), {'choices': [type('Choice', (), {'message': type('Message', (), {'content': mock_json_payload})()})()]})()
                ai_text = mock_json_payload
            else:
                return {
                    "text": "OpenAI API Key is missing. However, you can try typing 'book a VIP room' or 'recommend a room' to see the mock API system at work!",
                    "state_updates": {}
                }

        # Let's ensure the user history is passed smoothly
        messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ]
        
        if chat_history:
            messages.extend(chat_history[-6:])  # last 6 messages
            
        messages.append({"role": "user", "content": user_msg})

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
            )
            ai_text = response.choices[0].message.content
            
            # Extract JSON block if the model chose to output state commands
            json_payload = self._extract_json(ai_text)
            
            result = {
                "text": ai_text,
                "state_updates": {}
            }

            if json_payload:
                try:
                    data = json.loads(json_payload)
                    # If the AI produced JSON, separate out the text from the internal API commands
                    if "reply" in data:
                        result["text"] = data["reply"]
                    if "intent" in data:
                        result["state_updates"]["intent"] = data["intent"]
                    if "booking" in data:
                        # Extract any booking entities the AI found
                        if data["booking"].get("room_type"):
                            result["state_updates"]["room_type"] = data["booking"]["room_type"]
                        if data["booking"].get("check_in"):
                            result["state_updates"]["check_in"] = data["booking"]["check_in"]
                        if data["booking"].get("guests"):
                            result["state_updates"]["guests"] = data["booking"]["guests"]

                    # Determine if it's attempting to finalize
                    if data.get("intent") == "confirm_booking" and booking_state.get("step") == "confirmation":
                        # Integrate with Stripe Fraud + Pricing
                        fraud_res = StripeRadarAPI.analyze_transaction({
                            "total_amount": booking_state.get("total_price", 5000),
                        })
                        result["fraud_assessment"] = fraud_res
                        
                    elif data.get("intent") == "recommend":
                        rec_res = AWSPersonalizeAPI.get_user_recommendations(user_id)
                        result["aws_recommendation"] = rec_res
                        
                except Exception as e:
                    print("Could not parse AI JSON Payload:", e)
                    
            return result

        except Exception as e:
            # Try Gemini as fallback
            gemini_reply = self._call_gemini(self._get_system_prompt(), user_msg)
            if gemini_reply:
                return {"text": gemini_reply, "state_updates": {}, "provider": "gemini"}
            return {"text": f"Error contacting AI: {str(e)}", "state_updates": {}}

    def _get_system_prompt(self):
        return """You are the AI Concierge for Blissful Abodes Chennai.
You handle hotel bookings, recommendations, and pricing inquiries.

If the user wants to book, or answers a booking question, you MUST output a JSON object merged with your text response:
```json
{
    "reply": "Your friendly conversation text here...",
    "intent": "book", 
    "booking": {
        "room_type": "VIP Suite", 
        "check_in": "YYYY-MM-DD",
        "guests": 2
    }
}
```
Possible intents: [general, search, book, confirm_booking, recommend].
Always be polite, professional, and use emojis."""
        
    def _extract_json(self, text: str):
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text and "{" in text:
            return text.split("```")[1].split("```")[0].strip()
        elif "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            return text[start:end]
        return None

    def handle_manager_message(self, user_msg: str, manager_context: dict) -> str:
        """
        Specialized internal assistant for the Hotel Manager.
        Has access to live KPIs, fraud data, and revenue.
        """
        if not self.is_configured():
            return "OpenAI API Key is missing. I am running in Offline Mode. I see your daily revenue is ₹" + str(manager_context.get('today_revenue', 0))

        system_prompt = f"""You are the internal Executive AI Assistant for the Hotel Manager at Blissful Abodes.
The manager will ask you operational questions. You have access to the following live, real-time context:
Revenue Today: ₹{manager_context.get('today_revenue', 0)}
Monthly Revenue: ₹{manager_context.get('monthly_revenue', 0)}
Occupancy: {manager_context.get('occupancy', 0)}%
Pending Tasks: {manager_context.get('pending_tasks', 0)}
Flagged Fraud Bookings: {manager_context.get('fraud_count', 0)}

Answer professionally, concisely, and use emojis. Rely ONLY on the context provided above to answer data questions. 
If they ask about something not in the context, tell them you don't have that specific data layer loaded yet.
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.4,
            )
            return response.choices[0].message.content
        except Exception as e:
            # Try Gemini as fallback
            gemini_reply = self._call_gemini(system_prompt, user_msg)
            if gemini_reply:
                return gemini_reply
            return f"Error contacting AI Assistant: {str(e)}"

    def handle_staff_message(self, user_msg: str, staff_context: dict) -> str:
        """
        Specialized internal assistant for the Hotel Staff.
        Helps with task prioritization, check-ins, and room availability.
        """
        if not self.is_configured():
            return f"Offline Mode: You have {staff_context.get('pending_tasks', 0)} pending tasks and {staff_context.get('checkins_today', 0)} check-ins today."

        system_prompt = f"""You are the internal Assistant for the Hotel Staff at Blissful Abodes.
The staff member will ask you operational questions regarding tasks, rooms, and check-ins.
You have access to the following live context:
Pending Tasks: {staff_context.get('pending_tasks', 0)}
Urgent Tasks: {staff_context.get('urgent_tasks', 0)}
Today's Check-ins: {staff_context.get('checkins_today', 0)}
Rooms to Clean: {staff_context.get('cleaning_rooms', 0)}
Your Next Task: {staff_context.get('next_task', 'None')}

Answer professionally, concisely, and use emojis. Tell them their next priority if they ask what to do.
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.4,
            )
            return response.choices[0].message.content
        except Exception as e:
            # Try Gemini as fallback
            gemini_reply = self._call_gemini(system_prompt, user_msg)
            if gemini_reply:
                return gemini_reply
            return f"Error contacting AI Assistant: {str(e)}"

# Singleton instance
openai_agent = OpenAIDecisionAgent()

