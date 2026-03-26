"""
Blissful Abodes - AI Decision Engine Routes
=========================================
Integrates the Central AI Decision Engine into the booking flow
"""

from flask import Blueprint, request, jsonify, session
from services.security import require_auth
from ml_models.ai_decision_engine import (
    get_decision_engine,
    evaluate_booking,
    AIComponentScores,
    DecisionStatus,
    RiskLevel,
    DecisionFactors,
)

ai_decision_bp = Blueprint("ai_decision", __name__)


@ai_decision_bp.route("/api/ai/evaluate-booking", methods=["POST"])
@require_auth
async def api_evaluate_booking():
    """
    API endpoint to evaluate a booking using the AI Decision Engine
    Returns decision with explanations and recommended actions
    """
    user_id = session.get("user_id")
    data = request.json or {}

    booking_data = {
        "user_id": user_id,
        "room_type": data.get("room_type", "Single"),
        "check_in": data.get("check_in", ""),
        "check_out": data.get("check_out", ""),
        "guests": data.get("guests", 1),
        "total_amount": data.get("total_amount", 0),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "payment_method": data.get("payment_method", "card"),
    }

    engine = get_decision_engine()
    result = await engine.evaluate_booking(booking_data)

    return jsonify({
        "success": True,
        "decision": result.decision,
        "risk_level": result.risk_level,
        "confidence": result.confidence,
        "overall_score": result.overall_score,
        "recommended_price": result.recommended_price,
        "recommended_room": result.recommended_room,
        "reasons": result.reasons,
        "actions": result.actions,
        "warnings": result.warnings,
        "decision_id": result.decision_id,
    })


@ai_decision_bp.route("/api/ai/booking-decision/<booking_id>")
@require_auth
def get_booking_decision(booking_id: str):
    """Get AI decision for an existing booking"""
    engine = get_decision_engine()
    result = engine.get_booking_decision(booking_id)

    if not result:
        return jsonify({"success": False, "message": "Decision not found"}), 404

    return jsonify({
        "success": True,
        "decision": result.decision,
        "risk_level": result.risk_level,
        "confidence": result.confidence,
        "reasons": result.reasons,
        "actions": result.actions,
    })


@ai_decision_bp.route("/api/ai/decision-stats")
@require_auth
def get_decision_statistics():
    """Get AI decision statistics"""
    engine = get_decision_engine()
    stats = engine.get_decision_stats()

    return jsonify({
        "success": True,
        "statistics": stats,
    })
