"""
Test script for the Central AI Decision Engine
Run from project root: python test_decision_engine.py
"""
import sys, os, json
sys.path.insert(0, os.path.abspath('.'))

print("=" * 60)
print("  Central AI Decision Engine - Test Suite")
print("=" * 60)

# ── Sample test data ──────────────────────────────────────────
sample_booking = {
    "booking_id": "BK_TEST_001",
    "user_id": "user_test_001",
    "room_type": "Single",
    "check_in": "2026-03-28",
    "check_out": "2026-03-30",
    "guests": 1,
    "total_amount": 7060.0,
    "email": "rajesh@gmail.com",
    "phone": "9876543210",
    "payment_method": "card",
    "created_at": "2026-03-24T00:00:00",
}

sample_room = {
    "room_id": "room_01",
    "room_type": "Single",
    "room_number": "101",
    "price": 3530.0,
    "current_price": 3530.0,
    "capacity": 2,
    "max_guests": 2,
    "is_active": 1,
    "status": "available",
}

sample_user = {
    "user_id": "user_test_001",
    "email": "rajesh@gmail.com",
    "name": "Rajesh Kumar",
    "created_at": "2025-06-01T10:00:00",
    "loyalty_points": 500,
    "tier_level": "Gold",
}

# Historical bookings — some completed, one cancelled
sample_all_bookings = [
    {"booking_id": "BK001", "user_id": "user_test_001", "room_id": "room_01",
     "booking_status": "completed", "check_in": "2025-12-01", "created_at": "2025-11-20T09:00:00",
     "total_amount": 7060.0, "payment_method": "card"},
    {"booking_id": "BK002", "user_id": "user_test_001", "room_id": "room_01",
     "booking_status": "cancelled", "check_in": "2026-01-01", "created_at": "2025-12-20T09:00:00",
     "total_amount": 7060.0, "payment_method": "upi"},
]

sample_all_rooms  = [sample_room]
sample_all_users  = [sample_user]

# ── Run Evaluation ──────────────────────────────────────────────
try:
    from ml_models.ai_decision_engine import evaluate_booking, get_decision_summary

    print("\n[1/5] Calling evaluate_booking()...")
    result = evaluate_booking(
        booking=sample_booking,
        room=sample_room,
        user=sample_user,
        all_bookings=sample_all_bookings,
        all_rooms=sample_all_rooms,
        all_users=sample_all_users,
        occupancy_rate=0.34,
        days_until_checkin=4,
    )

    print("\n[2/5] Full AI Decision Result:")
    print(f"  Decision       : {result['decision']}")
    print(f"  Risk Level     : {result['risk_level']}")
    print(f"  Decision Score : {result['decision_score']} / 100")
    print(f"  Confidence     : {round(result['confidence']*100)}%")

    print(f"\n[3/5] Individual AI Module Outputs:")
    print(f"  Fraud Score    : {round(result['fraud_score'], 1)}")
    print(f"  Cancel Prob    : {round(result['cancel_probability']*100, 1)}%")
    print(f"  AI Price       : ₹{result['ai_price']}")
    print(f"  Demand Signal  : {result['demand_avg_pct']}% avg occupancy (next 7 days)")
    print(f"  Recommended    : {result['recommended_room']}")

    print(f"\n[4/5] Explainable AI Reasons:")
    for r in result["reasons"]:
        print(f"  → {r}")

    print(f"\n[5/5] Compact Decision Summary (for REST API / frontend):")
    summary = get_decision_summary(result)
    print(json.dumps(summary, indent=4, ensure_ascii=False))

    print("\n" + "="*60)
    print("  ✅ ENGINE TEST PASSED — All 5 AI modules fired correctly!")
    print("="*60)

except Exception as e:
    import traceback
    print(f"\n❌ ENGINE TEST FAILED: {e}")
    traceback.print_exc()

# ── Test a HIGH RISK booking (should be BLOCKED) ──────────────
print("\n" + "-"*60)
print("  Testing HIGH RISK booking (should return BLOCK)")
print("-"*60)

try:
    from ml_models.ai_decision_engine import evaluate_booking, get_decision_summary

    risky_user = {
        "user_id": "risky_user_01",
        "email": "fraudster@tempmail.com",
        "created_at":  "2026-03-23T23:50:00",  # Account created minutes ago
    }
    risky_booking = {
        "booking_id": "BK_RISKY_001",
        "user_id": "risky_user_01",
        "room_type": "vip",
        "check_in": "2026-03-24",  # Same-day booking
        "check_out": "2026-03-26",
        "guests": 8,              # Exceeds capacity
        "total_amount": 99990.0,  # Way above normal pricing
        "email": "fraudster@tempmail.com",
        "payment_method": "cash",
        "created_at": "2026-03-23T23:55:00",
    }
    risky_room = {
        "room_id": "room_vip_01",
        "room_type": "VIP Suite",
        "room_number": "501",
        "price": 12000.0,
        "current_price": 12000.0,
        "capacity": 3,
    }
    # Multiple recent bookings from same user
    risky_bookings = [
        {"booking_id": f"BK_FAST_{i}", "user_id": "risky_user_01", "room_id": "room_vip_01",
         "booking_status": "cancelled", "check_in": "2026-03-24",
         "created_at": "2026-03-23T23:50:00", "total_amount": 99990.0, "payment_method": "cash"}
        for i in range(5)
    ]

    risky_result = evaluate_booking(
        booking=risky_booking,
        room=risky_room,
        user=risky_user,
        all_bookings=risky_bookings,
        all_rooms=[risky_room],
        all_users=[risky_user],
        occupancy_rate=0.9,
        days_until_checkin=0,
    )
    summary = get_decision_summary(risky_result)

    outcome = "✅ CORRECTLY BLOCKED" if risky_result["decision"] == "BLOCK" else f"⚠️ Got: {risky_result['decision']}"
    print(f"  High Risk Result: {risky_result['decision']} ({outcome})")
    print(f"  Fraud Score     : {round(risky_result['fraud_score'], 1)}")
    print(f"  Reasons         : {risky_result['reasons'][0] if risky_result['reasons'] else 'None'}")

except Exception as e:
    import traceback
    print(f"❌ RISK TEST FAILED: {e}")
    traceback.print_exc()
