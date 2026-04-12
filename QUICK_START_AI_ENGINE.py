#!/usr/bin/env python3
"""
🧠 AI DECISION ENGINE — QUICK START GUIDE
==========================================

Fast reference for using your complete AI Decision Engine.
"""

# ═══════════════════════════════════════════════════════════════════════════
# 1. BASIC USAGE — Single Booking Evaluation
# ═══════════════════════════════════════════════════════════════════════════

from ml_models.ai_decision_engine import evaluate_booking, get_decision_summary

# Step 1: Prepare data
booking = {
    "booking_id": "BK-001",
    "user_id": "USER-123",
    "room_id": "ROOM-VIP",
    "check_in": "2026-04-10",
    "check_out": "2026-04-12",
    "guests": 2,
}

room = {
    "room_id": "ROOM-VIP",
    "room_type": "VIP Suite",
    "price": 5000,
    "capacity": 2,
}

user = {
    "user_id": "USER-123",
    "first_name": "Rahul",
    "email": "rahul@example.com",
}

# Step 2: Evaluate
result = evaluate_booking(
    booking=booking,
    room=room,
    user=user,
    all_bookings=[booking],
    all_rooms=[room],
    all_users=[user],
    occupancy_rate=0.65,
    days_until_checkin=7,
)

# Step 3: Get summary
summary = get_decision_summary(result)

print(f"Decision: {summary['decision']}")           # "APPROVE"
print(f"Risk: {summary['risk_level']}")             # "LOW"
print(f"Price: ₹{summary['price']}")                # 5200
print(f"Confidence: {summary['confidence']}")       # "87%"
print(f"Recommendation: {summary['recommendation']}") # "VIP Suite"


# ═══════════════════════════════════════════════════════════════════════════
# 2. DETAILED ANALYSIS — What Factors Influenced the Decision?
# ═══════════════════════════════════════════════════════════════════════════

from ml_models.ai_decision_engine import analyze_decision_factors

analysis = analyze_decision_factors(result)

print("\nComponent Analysis:")
print(f"  Fraud Detection: {analysis['component_analysis']['fraud_detection']['score']}/100")
print(f"  Cancellation Risk: {analysis['component_analysis']['cancellation_prediction']['score']}/100")
print(f"  Demand Signal: {analysis['component_analysis']['demand_forecasting']['score']}/100")
print(f"  User Profile: {analysis['component_analysis']['user_profile']['score']}/100")

print("\nDecision Drivers:")
for driver in analysis['decision_drivers']:
    print(f"  {driver}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. GET ALTERNATIVES — Provide Room Suggestions
# ═══════════════════════════════════════════════════════════════════════════

from ml_models.ai_decision_engine import get_recommendation_with_alternatives

recommendations = get_recommendation_with_alternatives(
    user=user,
    current_room=room,
    all_rooms=[room],
    all_bookings=[booking],
    all_users=[user],
    top_n=3,
)

print(f"\nPrimary: {recommendations['primary']['room_type']}")
for alt in recommendations['alternatives']:
    print(f"  • {alt['room_type']}")


# ═══════════════════════════════════════════════════════════════════════════
# 4. BATCH PROCESSING — Evaluate Multiple Bookings at Once
# ═══════════════════════════════════════════════════════════════════════════

from ml_models.ai_decision_engine import batch_evaluate_bookings

bookings_to_eval = [
    {
        "booking": {"booking_id": "BK-001", "user_id": "U1", "room_id": "R1"},
        "room": {"room_id": "R1", "room_type": "Double", "price": 5000},
        "user": {"user_id": "U1", "first_name": "Guest1"},
        "occupancy_rate": 0.65,
        "days_until_checkin": 7,
    },
    {
        "booking": {"booking_id": "BK-002", "user_id": "U2", "room_id": "R2"},
        "room": {"room_id": "R2", "room_type": "VIP Suite", "price": 8500},
        "user": {"user_id": "U2", "first_name": "Guest2"},
        "occupancy_rate": 0.80,
        "days_until_checkin": 3,
    },
]

batch_results = batch_evaluate_bookings(
    bookings_data=bookings_to_eval,
    all_bookings=[b["booking"] for b in bookings_to_eval],
    all_rooms=[b["room"] for b in bookings_to_eval],
    all_users=[b["user"] for b in bookings_to_eval],
)

for i, res in enumerate(batch_results, 1):
    print(f"\nBooking {i}: {res['decision']} (Score: {res['decision_score']}/100)")


# ═══════════════════════════════════════════════════════════════════════════
# 5. AUDIT REPORT — Create Compliance Trail
# ═══════════════════════════════════════════════════════════════════════════

from ml_models.ai_decision_engine import create_decision_report
import json

report = create_decision_report(result, booking)

print(f"\nAudit Report ID: {report['report_id']}")
print(f"Decision: {report['executive_summary']['decision']}")
print(f"Fraud Status: {report['detailed_analysis']['fraud_detection']['status']}")
print(f"Cancel Risk: {report['detailed_analysis']['cancellation_prediction']['probability']}")

# Save full report for compliance
with open("decision_report.json", "w") as f:
    json.dump(report, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# 6. ENGINE METRICS — System Information
# ═══════════════════════════════════════════════════════════════════════════

from ml_models.ai_decision_engine import get_engine_metrics

metrics = get_engine_metrics()

print(f"\nEngine: {metrics['engine_name']} v{metrics['version']}")
print(f"\nComponents:")
for name, detail in metrics['components'].items():
    print(f"  • {name}: {detail.get('algorithm', 'N/A')}")

print(f"\nFeatures:")
for feature in metrics['features']:
    print(f"  ✓ {feature}")


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION IN FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════════════

"""
Example integration in routes/guest.py:

@guest_bp.route('/book', methods=['POST'])
def book_room():
    booking_data = request.json
    room = get_room(booking_data['room_id'])
    user = session.get('user_id')
    
    # Run AI Decision Engine
    from ml_models.ai_decision_engine import evaluate_booking, get_decision_summary
    
    ai_result = evaluate_booking(
        booking=booking_data,
        room=room,
        user=user,
        all_bookings=get_all_bookings(),
        all_rooms=get_all_rooms(),
        all_users=get_all_users(),
        occupancy_rate=calculate_occupancy(),
        days_until_checkin=days_until(booking_data['check_in']),
    )
    
    # Check decision
    if ai_result['decision'] == 'BLOCK':
        return jsonify({'error': 'Booking cannot be processed'}), 403
    elif ai_result['decision'] == 'REVIEW':
        # Flag for manager
        save_booking_review_flag(booking_data, ai_result)
        return jsonify({
            'message': 'Booking pending manager review',
            'reasons': ai_result['reasons']
        }), 202
    else:  # APPROVE
        # Save booking with AI price and data
        booking = save_booking(
            booking_data,
            ai_price=ai_result['ai_price'],
            fraud_score=ai_result['fraud_score'],
            cancel_probability=ai_result['cancel_probability'],
            decision_score=ai_result['decision_score']
        )
        return jsonify(get_decision_summary(ai_result))
"""


# ═══════════════════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════════════════

"""
Run comprehensive tests:
    python test_ai_decision_engine_full.py

This runs 6 demonstrations:
    1. Basic single booking evaluation
    2. Decision factor analysis  
    3. Recommendation engine
    4. Batch processing
    5. Audit report generation
    6. Engine metrics
"""


# ═══════════════════════════════════════════════════════════════════════════
# API RESPONSE EXAMPLES
# ═══════════════════════════════════════════════════════════════════════════

"""
Example 1: APPROVED Booking
GET /api/booking/evaluate
Response:
{
  "decision": "APPROVE",
  "risk_level": "LOW",
  "price": 5200,
  "recommendation": "VIP Suite",
  "reasons": [
    "✅ Low fraud risk (score: 15%)",
    "✅ Low cancellation risk (28%)",
    "💰 Pricing: Weekend premium (+4%)",
    "📈 High demand period (78% forecast)",
    "🎯 Decision confidence: 84%"
  ],
  "confidence": "84%"
}

Example 2: REVIEW Needed
Response:
{
  "decision": "REVIEW",
  "risk_level": "MEDIUM",
  "price": 4500,
  "recommendation": "Double Room",
  "reasons": [
    "⚠️ Moderate cancellation risk (52%)",
    "🔔 Manual review recommended",
    "💰 Discounted price (-10%)",
  ],
  "confidence": "65%"
}

Example 3: BLOCKED Booking
Response:
{
  "decision": "BLOCK",
  "risk_level": "HIGH",
  "reasons": [
    "🚨 High fraud risk detected (score: 75%)",
    "🔍 Fraud rule triggered: Rapid multi-booking",
    "🛑 Booking blocked by AI Engine"
  ],
  "confidence": "92%"
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE FIELDS USED
# ═══════════════════════════════════════════════════════════════════════════

"""
Recommended Bookings table columns:
  - booking_id (PK)
  - user_id (FK)
  - room_id (FK)
  - check_in
  - check_out
  - total_amount
  
  # AI Engine fields (added)
  - fraud_score (FLOAT)           # From Fraud AI (0-100)
  - fraud_flags (JSON)            # Triggered rules
  - cancel_probability (FLOAT)    # From Cancel AI (0-1)
  - ai_decision_score (FLOAT)     # Final engine score (0-100)
  - ai_price (FLOAT)              # Dynamic pricing output
  - is_flagged (BOOLEAN)          # Flagged for review
  - manager_decision (VARCHAR)    # Manager override if reviewed
  - created_at
  - updated_at
"""

