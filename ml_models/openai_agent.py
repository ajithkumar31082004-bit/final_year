import os
import json
from openai import OpenAI
from ml_models.external_apis import (
    StripeRadarAPI,
    AWSForecastAPI,
    GoogleTravelAPI,
    AWSPersonalizeAPI
)

class OpenAIDecisionAgent:
    def __init__(self):
        # We initialize dynamically in case key is set later
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)

    def is_configured(self):
        return bool(self.client) and bool(self.api_key)

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

# Singleton instance
openai_agent = OpenAIDecisionAgent()
