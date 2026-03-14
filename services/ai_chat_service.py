import json
import os
import urllib.request
import urllib.error
from flask import current_app

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _get_api_key():
    return os.environ.get("GEMINI_API_KEY") or current_app.config.get(
        "GEMINI_API_KEY", ""
    )


def _get_model():
    return os.environ.get("GEMINI_MODEL") or current_app.config.get(
        "GEMINI_MODEL", "gemini-2.5-flash"
    )


def _map_history(history):
    contents = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if not content:
            continue
        if role == "assistant":
            role = "model"
        elif role != "user":
            continue
        contents.append({"role": role, "parts": [{"text": content}]})
    return contents


def generate_ai_reply(
    user_message,
    history,
    system_prompt,
    temperature=0.4,
    max_tokens=450,
):
    api_key = _get_api_key()
    if not api_key:
        return None, "missing_api_key"

    model = _get_model()
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": _map_history(history)
        + [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    req = urllib.request.Request(
        GEMINI_API_URL.format(model=model),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        return (text or None), None
    except urllib.error.HTTPError as e:
        try:
            details = json.loads(e.read().decode("utf-8"))
            return None, details.get("error", {}).get("message", "API error")
        except Exception:
            return None, f"API error: {e}"
    except Exception as e:
        return None, str(e)
