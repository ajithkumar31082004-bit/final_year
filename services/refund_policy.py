from flask import current_app


def get_refund_thresholds():
    full_hours = current_app.config.get("REFUND_FULL_HOURS", 48)
    half_hours = current_app.config.get("REFUND_HALF_HOURS", 24)
    return full_hours, half_hours


def calculate_refund_pct(hours_until_checkin: float, payment_status: str = "paid") -> float:
    full_hours, half_hours = get_refund_thresholds()
    if str(payment_status).lower() != "paid":
        return 0.0
    if hours_until_checkin > full_hours:
        return 1.0
    if hours_until_checkin > half_hours:
        return 0.5
    return 0.0


def policy_text() -> str:
    full_hours, half_hours = get_refund_thresholds()
    return (
        f"full refund {full_hours}+ hours before check-in, "
        f"50% within {half_hours}-{full_hours} hours, "
        f"no refund within {half_hours} hours."
    )
