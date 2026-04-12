"""
Blissful Abodes - AI Decision Engine Routes
=========================================
Integrates the Central AI Decision Engine into the booking flow
"""

from flask import Blueprint, request, jsonify, session, redirect, url_for
from ml_models.ai_decision_engine import (
    evaluate_booking,
    get_decision_summary,
    analyze_decision_factors,
)

ai_decision_bp = Blueprint("ai_decision", __name__)


@ai_decision_bp.route("/api/ai/evaluate-booking", methods=["POST"])
def api_evaluate_booking():
    """
    API endpoint to evaluate a booking using the AI Decision Engine
    Returns decision with explanations and recommended actions
    """
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
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

        # Simplified decision for demo - in production, use full evaluate_booking with DB data
        summary = get_decision_summary({
            "decision": "APPROVE",
            "risk_level": "LOW",
            "fraud_score": 0,
            "cancel_probability": 0.1,
            "dynamic_price": booking_data["total_amount"],
            "reasons": ["Booking evaluation successful"]
        })

        return jsonify({
            "success": True,
            "summary": summary,
            "booking_data": booking_data,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ai_decision_bp.route("/api/ai/booking-decision/<booking_id>")
def get_booking_decision(booking_id: str):
    """Get AI decision for an existing booking"""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        # In production, fetch booking from database and evaluate
        return jsonify({
            "success": True,
            "booking_id": booking_id,
            "message": "Booking decision endpoint - implement with database integration"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ai_decision_bp.route("/api/ai/decision-stats")
def get_decision_statistics():
    """Get AI decision statistics"""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        # In production, aggregate decision statistics from database
        return jsonify({
            "success": True,
            "statistics": {
                "total_decisions": 0,
                "approvals": 0,
                "reviews": 0,
                "blocks": 0,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
