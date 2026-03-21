"""
ai_chat_service.py
------------------
Google Gemini AI service using the official google-genai SDK.
Supports Thinking (reasoning) and Google Search grounding.
"""

import os
from flask import current_app, has_app_context

try:
    from google import genai
    from google.genai import types
    _GENAI_AVAILABLE = True
except Exception:  # pragma: no cover
    genai = None
    types = None
    _GENAI_AVAILABLE = False

# Hardcoded key to ensure .env or config.py overrides do not break the chatbot
_FALLBACK_API_KEY = "AIzaSyCB4pOLezxCsJoYge0i6KiikIeOxcpbtD0"

# ── helpers ──────────────────────────────────────────────────────────────────

def _get_api_key():
    # Force use of our known working key, ignoring whatever dummy 'your-key' 
    # might be loaded into os.environ or current_app.config by dotenv
    key = os.environ.get("GEMINI_API_KEY")
    if not key and has_app_context():
        key = current_app.config.get("GEMINI_API_KEY", "")
    
    # If the environment loaded a dummy placeholder like 'your-key' or 'placeholder_',
    # or if it's empty, use our real fallback key.
    if not key or "placeholder" in key.lower() or key == "your-key":
        return _FALLBACK_API_KEY
        
    return key


def _get_model():
    model = os.environ.get("GEMINI_MODEL")
    if not model and has_app_context():
        model = current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
    return model or "gemini-2.5-flash"

def _build_contents(history, user_message):
    """Combine chat history and new user message into SDK contents list."""
    contents = []

    for msg in (history or []):
        role = msg.get("role", "")
        text = msg.get("content", "")
        if not text:
            continue
        sdk_role = "model" if role == "assistant" else "user"
        if sdk_role not in ("user", "model"):
            continue
        contents.append(
            types.Content(
                role=sdk_role,
                parts=[types.Part.from_text(text=text)],
            )
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)],
        )
    )
    return contents


# ── public API ───────────────────────────────────────────────────────────────

def generate_ai_reply(
    user_message,
    history,
    system_prompt,
    temperature=0.4,
    max_tokens=450,
):
    """
    Generate a reply from Gemini.

    Returns (reply_text, error_string).
    On success: (str, None)
    On failure: (None, str)
    """
    api_key = _get_api_key()
    if not api_key:
        return None, "missing_api_key"

    if not _GENAI_AVAILABLE:
        return None, "genai_sdk_missing"

    model = _get_model()

    try:
        # Pass the key explicitly. The SDK might warn if GOOGLE_API_KEY is also
        # in the env, but it will use the one we pass here securely.
        client = genai.Client(api_key=api_key)
        contents = _build_contents(history, user_message)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(
                thinking_budget=512,  # lightweight reasoning
            ),
            tools=[
                types.Tool(google_search=types.GoogleSearch()),
            ],
        )

        reply_parts = []
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if chunk.text:  # guard: thinking-only chunks have no .text
                reply_parts.append(chunk.text)

        reply = "".join(reply_parts).strip()
        return (reply or None), None

    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "401" in error_msg:
            return None, "invalid_api_key: " + error_msg
        if "RATE_LIMIT" in error_msg or "429" in error_msg:
            return None, "rate_limit_exceeded"
        if "NOT_FOUND" in error_msg or "404" in error_msg:
            return None, f"model_not_found: {model}"
        return None, error_msg
