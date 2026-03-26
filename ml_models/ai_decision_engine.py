"""
Central AI Decision Engine — Blissful Abodes Chennai
=====================================================
Unified orchestration layer that combines ALL 5 ML AI modules:
  1. Fraud Detection AI       (RandomForest + Rules)
  2. Cancellation Prediction  (RandomForest)
  3. Dynamic Pricing AI       (RandomForestRegressor)
  4. Demand Forecasting AI    (RandomForestRegressor)
  5. Recommendation Engine    (Hybrid Collaborative + ML)

Flow:
    User Booking Request
            ↓
    evaluate_booking()
            ↓
    ┌─────────────────────────────────────────────────┐
    │  Fraud AI ▸ Cancel AI ▸ Price AI ▸ Demand AI    │
    └─────────────────────────────────────────────────┘
            ↓
    Decision Scoring Layer
            ↓
    Final Output: APPROVE / REVIEW / BLOCK
"""

from datetime import datetime


# ---------------------------------------------------------------------------
# DECISION THRESHOLDS
# ---------------------------------------------------------------------------
BLOCK_FRAUD_THRESHOLD   = 60   # Fraud score >= 60  → BLOCK
REVIEW_CANCEL_THRESHOLD = 0.60 # Cancel prob >= 0.6 → REVIEW


# ---------------------------------------------------------------------------
# SCORE CALCULATION
# ---------------------------------------------------------------------------
def _compute_decision_score(fraud_score: float, cancel_prob: float,
                             demand_pct: float, user_score: float = 70.0) -> float:
    """
    Unified weighted decision score (0-100, higher = better booking prospect).

    Weights:
        Fraud Safety     40%
        Cancel Safety    20%
        Demand Signal    20%
        User Score       20%
    """
    fraud_safety   = max(0.0, 100.0 - float(fraud_score))
    cancel_safety  = max(0.0, 100.0 - float(cancel_prob * 100))
    demand_signal  = max(0.0, min(100.0, float(demand_pct)))
    usr            = max(0.0, min(100.0, float(user_score)))

    score = (
        fraud_safety  * 0.40 +
        cancel_safety * 0.20 +
        demand_signal * 0.20 +
        usr           * 0.20
    )
    return round(score, 2)


def _classify_decision(fraud_score: float, cancel_prob: float) -> str:
    """Smart decision rules based on individual risk signals."""
    if fraud_score >= BLOCK_FRAUD_THRESHOLD:
        return "BLOCK"
    if cancel_prob >= REVIEW_CANCEL_THRESHOLD:
        return "REVIEW"
    return "APPROVE"


def _build_risk_level(fraud_score: float, cancel_prob: float) -> str:
    if fraud_score >= 60 or cancel_prob >= 0.60:
        return "HIGH"
    if fraud_score >= 35 or cancel_prob >= 0.35:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# EXPLAINABLE AI — Reason Generation
# ---------------------------------------------------------------------------
def _explain_decision(fraud_result: dict, cancel_result: dict,
                       pricing_result: dict, demand_avg: float,
                       decision: str, decision_score: float) -> list:
    """Generates a list of human-readable AI explanations for the decision."""
    reasons = []
    fraud_score  = fraud_result.get("risk_score", 0)
    cancel_prob  = cancel_result.get("cancel_probability", 0)

    # Fraud reasons
    if fraud_score >= 60:
        reasons.append(f"🚨 High fraud risk detected (score: {round(fraud_score)}%)")
    elif fraud_score >= 35:
        reasons.append(f"⚠️ Moderate fraud indicators (score: {round(fraud_score)}%)")
    else:
        reasons.append(f"✅ Low fraud risk (score: {round(fraud_score)}%)")

    # Cancellation reasons
    cancel_pct = round(cancel_prob * 100, 1)
    if cancel_prob >= 0.60:
        reasons.append(f"📉 High cancellation probability ({cancel_pct}%) — manual review recommended")
    elif cancel_prob >= 0.35:
        reasons.append(f"🔔 Moderate cancellation risk ({cancel_pct}%) — send reminder")
    else:
        reasons.append(f"✅ Low cancellation risk ({cancel_pct}%)")

    # Pricing reasons
    price_reasons = pricing_result.get("reasons", [])
    if price_reasons:
        reasons.append(f"💰 Pricing: {price_reasons[0]}")

    # Demand reasons
    if demand_avg > 70:
        reasons.append(f"📈 High demand period ({round(demand_avg)}% occupancy forecast)")
    elif demand_avg < 40:
        reasons.append(f"📉 Low demand period — consider discount ({round(demand_avg)}% forecast)")
    else:
        reasons.append(f"📊 Moderate demand period ({round(demand_avg)}% occupancy forecast)")

    # Triggered fraud rules
    for rule in fraud_result.get("triggered_rules", [])[:2]:
        rule_name = rule.get("rule", "")
        if rule_name and rule_name != "ML Probability" and "External API" not in rule_name:
            reasons.append(f"🔍 Fraud rule triggered: {rule_name}")

    # Decision summary with confidence
    confidence_pct = round(decision_score)
    if decision == "APPROVE":
        reasons.append(f"🎯 Decision confidence: {confidence_pct}% — Booking approved by AI Engine")
    elif decision == "REVIEW":
        reasons.append(f"🔎 Decision confidence: {confidence_pct}% — Flagged for manager review")
    else:
        reasons.append(f"🛑 Booking blocked by AI Engine (confidence: {confidence_pct}%)")

    return reasons


# ---------------------------------------------------------------------------
# MASTER EVALUATION PIPELINE
# ---------------------------------------------------------------------------
def evaluate_booking(
    booking: dict,
    room: dict,
    user: dict,
    all_bookings: list,
    all_rooms: list = None,
    all_users: list = None,
    occupancy_rate: float = 0.5,
    days_until_checkin: int = 7,
) -> dict:
    """
    Master AI Decision Engine — evaluates a booking through all 5 ML modules.

    Returns:
    {
        "decision":           "APPROVE" | "REVIEW" | "BLOCK",
        "risk_level":         "LOW" | "MEDIUM" | "HIGH",
        "decision_score":     float (0-100, higher = better prospect),
        "confidence":         float (0-1),
        "fraud_score":        float (0-100),
        "cancel_probability": float (0-1),
        "dynamic_price":      float,
        "demand_avg_pct":     float,
        "recommended_room":   str | None,
        "ai_price":           float,
        "reasons":            list[str],
        "fraud_result":       dict,
        "cancel_result":      dict,
        "pricing_result":     dict,
        "demand_result":      list,
    }
    """
    result = {
        "decision": "APPROVE",
        "risk_level": "LOW",
        "decision_score": 75.0,
        "confidence": 0.85,
        "fraud_score": 0.0,
        "cancel_probability": 0.0,
        "dynamic_price": float(room.get("price", room.get("current_price", 5000)) or 5000),
        "demand_avg_pct": 50.0,
        "recommended_room": room.get("room_type"),
        "ai_price": float(room.get("price", room.get("current_price", 5000)) or 5000),
        "reasons": [],
        "fraud_result": {},
        "cancel_result": {},
        "pricing_result": {},
        "demand_result": [],
    }

    # ── 1. Fraud Detection ──────────────────────────────────────────────────
    try:
        from ml_models.ai_fraud_detection import score_booking as _score_booking
        fraud_result = _score_booking(
            booking, room, user, all_bookings,
            all_rooms=all_rooms, all_users=all_users
        )
        result["fraud_result"]  = fraud_result
        result["fraud_score"]   = float(fraud_result.get("risk_score", 0))
    except Exception as e:
        result["fraud_result"] = {"error": str(e), "risk_score": 0}

    # ── 2. Cancellation Prediction ──────────────────────────────────────────
    try:
        from ml_models.ai_cancellation import predict_cancellation
        cancel_result = predict_cancellation(
            booking, user, all_bookings, all_users or []
        )
        result["cancel_result"]      = cancel_result
        result["cancel_probability"] = float(cancel_result.get("cancel_probability", 0))
    except Exception as e:
        result["cancel_result"] = {"error": str(e), "cancel_probability": 0}

    # ── 3. Dynamic Pricing ──────────────────────────────────────────────────
    try:
        from ml_models.ai_dynamic_pricing import compute_dynamic_price
        pricing_result = compute_dynamic_price(room, occupancy_rate, days_until_checkin)
        result["pricing_result"] = pricing_result
        result["dynamic_price"]  = float(pricing_result.get("dynamic_price", result["dynamic_price"]))
        result["ai_price"]       = result["dynamic_price"]
    except Exception as e:
        result["pricing_result"] = {"error": str(e)}

    # ── 4. Demand Forecasting ───────────────────────────────────────────────
    try:
        from ml_models.ai_demand_forecast import predict_next_30_days
        demand_data = predict_next_30_days()
        next7 = demand_data[:7] if demand_data else []
        demand_avg = (
            sum(d.get("occupancy_pct", 50) for d in next7) / len(next7)
            if next7 else 50.0
        )
        result["demand_result"]  = demand_data
        result["demand_avg_pct"] = round(demand_avg, 1)
    except Exception:
        result["demand_result"]  = []
        result["demand_avg_pct"] = 50.0

    # ── 5. Recommendation Engine ────────────────────────────────────────────
    try:
        from ml_models.ai_recommender import get_recommendations
        recs = get_recommendations(
            user=user,
            all_rooms=all_rooms or [],
            all_bookings=all_bookings or [],
            all_users=all_users or [],
            top_n=1,
        )
        if recs:
            result["recommended_room"] = recs[0].get("room_type") or recs[0].get("room_id")
    except Exception:
        pass

    # ── 6. Unified Scoring & Decision ───────────────────────────────────────
    user_score = 70.0
    if all_bookings and user:
        uid = user.get("user_id")
        completed = sum(
            1 for b in all_bookings
            if b.get("user_id") == uid and
            str(b.get("booking_status", b.get("status", ""))).lower() in ("completed", "checked_out")
        )
        user_score = min(100.0, 60.0 + completed * 5.0)

    decision_score = _compute_decision_score(
        result["fraud_score"],
        result["cancel_probability"],
        result["demand_avg_pct"],
        user_score,
    )

    decision   = _classify_decision(result["fraud_score"], result["cancel_probability"])
    risk_level = _build_risk_level(result["fraud_score"], result["cancel_probability"])
    confidence = round(decision_score / 100.0, 3)

    result["decision"]       = decision
    result["risk_level"]     = risk_level
    result["decision_score"] = decision_score
    result["confidence"]     = confidence

    # ── 7. Explainable AI Reasons ───────────────────────────────────────────
    result["reasons"] = _explain_decision(
        result["fraud_result"],
        result["cancel_result"],
        result["pricing_result"],
        result["demand_avg_pct"],
        decision,
        decision_score,
    )

    return result


# ---------------------------------------------------------------------------
# CONVENIENCE: Summary dict for API responses
# ---------------------------------------------------------------------------
def get_decision_summary(eval_result: dict) -> dict:
    """Returns a compact JSON-safe summary for frontend display."""
    return {
        "decision":       eval_result["decision"],
        "risk_level":     eval_result["risk_level"],
        "price":          eval_result["ai_price"],
        "recommendation": eval_result.get("recommended_room"),
        "reasons":        eval_result["reasons"],
        "confidence":     f"{round(eval_result['confidence'] * 100)}%",
        "fraud_score":    round(eval_result["fraud_score"], 1),
        "cancel_risk":    f"{round(eval_result['cancel_probability'] * 100, 1)}%",
        "demand_signal":  f"{eval_result['demand_avg_pct']}%",
    }
