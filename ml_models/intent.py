def detect_intent(message):
    message = (message or "").lower()

    if "book" in message or "reserve" in message:
        return "book_room"
    elif "price" in message:
        return "price"
    elif "recommend" in message:
        return "recommend"
    elif "cancel" in message:
        return "cancel"
    else:
        return "general"
