"""
AI Demand Forecasting Engine — Blissful Abodes Chennai
======================================================
Simulated LSTM-style time-series forecasting using:
  - Historical booking baseline
  - Seasonal multipliers
  - Weekday trends
  - Noise smoothing

Output: next 30 days demand with predicted occupancy.
"""

import random
from datetime import date, timedelta


SEASONAL_MULTIPLIERS = {
    1: 1.30,  # Jan
    2: 1.10,
    3: 1.00,
    4: 0.95,
    5: 1.15,
    6: 1.35,
    7: 1.25,
    8: 1.10,
    9: 0.90,
    10: 1.00,
    11: 1.15,
    12: 1.40,  # Dec
}

WEEKDAY_TRENDS = {
    0: 0.85,  # Mon
    1: 0.82,  # Tue
    2: 0.84,  # Wed
    3: 0.90,  # Thu
    4: 1.05,  # Fri
    5: 1.25,  # Sat
    6: 1.20,  # Sun
}


def _smooth(value, last_value):
    """Simple smoothing to reduce noise spikes."""
    if last_value is None:
        return value
    return round(last_value * 0.6 + value * 0.4)


def predict_next_30_days(
    historical_bookings=None,
    base_bookings=12,
    max_capacity=100,
):
    """
    Predict next 30 days demand.

    Returns list[dict]:
    {
        "date": "YYYY-MM-DD",
        "predicted_bookings": int,
        "occupancy_pct": float,
        "confidence": float
    }
    """
    today = date.today()
    predictions = []
    last_pred = None

    baseline = base_bookings
    if historical_bookings:
        try:
            baseline = max(3, int(sum(historical_bookings[-30:]) / max(1, len(historical_bookings[-30:]))))
        except Exception:
            baseline = base_bookings

    for i in range(30):
        d = today + timedelta(days=i)
        season = SEASONAL_MULTIPLIERS.get(d.month, 1.0)
        weekday = WEEKDAY_TRENDS.get(d.weekday(), 1.0)
        noise = random.uniform(0.92, 1.08)

        raw = baseline * season * weekday * noise
        pred = _smooth(int(round(raw)), last_pred)
        pred = max(3, min(25, pred))
        last_pred = pred

        occupancy = min(100.0, round(pred / max_capacity * 100, 1))
        confidence = round(random.uniform(0.82, 0.94), 2)

        predictions.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "predicted_bookings": pred,
                "occupancy_pct": occupancy,
                "confidence": confidence,
            }
        )

    return predictions


def get_next_7_days_avg():
    preds = predict_next_30_days()[:7]
    return round(sum(p["predicted_bookings"] for p in preds) / 7, 1)
