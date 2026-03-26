"""
Blissful Abodes - AI Decision Engine Test Script
=================================================
Demonstrates how the Central AI Decision Engine works with all 5 AI modules
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from ml_models.ai_decision_engine import (
    get_decision_engine,
    evaluate_booking,
    AIComponentScores,
    DecisionStatus,
    RiskLevel,
    DecisionFactors,
)

# Configure stdout for Unicode
sys.stdout.reconfigure(encoding='utf-8')


async def test_ai_decision_engine():
    """Test the AI Decision Engine with sample booking data"""
    print("=" * 70)
    print("BLISSFUL ABODES - CENTRAL AI DECISION ENGINE TEST")
    print("=" * 70)
    print()

    # Test cases
    test_cases = [
        {
            "name": "Trusted VIP Customer - APPROVE",
            "booking_data": {
                "user_id": "usr_vip_001",
                "room_type": "VIP Suite",
                "check_in": (datetime.now() + timedelta(days=30)).date().isoformat(),
                "check_out": (datetime.now() + timedelta(days=33)).date().isoformat(),
                "guests": 2,
                "total_amount": 45000.00,
                "payment_method": "card",
                "email": "vip@blissfulabodes.com",
                "phone": "+91-9999999999",
                "is_new_user": False,
                "loyalty_points": 15000
            }
        },
        {
            "name": "Suspicious New User - REVIEW",
            "booking_data": {
                "user_id": "usr_suspicious_001",
                "room_type": "VIP Suite",
                "check_in": (datetime.now() + timedelta(days=1)).date().isoformat(),
                "check_out": (datetime.now() + timedelta(days=2)).date().isoformat(),
                "guests": 2,
                "total_amount": 15000.00,
                "payment_method": "tempmail.com",
                "email": "temp123@tempmail.com",
                "phone": "+91-8888888888",
                "is_new_user": True,
                "loyalty_points": 0
            }
        },
        {
            "name": "High Cancellation Risk - REVIEW",
            "booking_data": {
                "user_id": "usr_regular_001",
                "room_type": "Single",
                "check_in": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "check_out": (datetime.now() + timedelta(days=61)).date().isoformat(),
                "guests": 1,
                "total_amount": 2500.00,
                "payment_method": "card",
                "email": "regular@example.com",
                "phone": "+91-7777777777",
                "is_new_user": False,
                "loyalty_points": 2000,
                "cancellation_history": 5
            }
        },
        {
            "name": "Low Score - BLOCK",
            "booking_data": {
                "user_id": "usr_blocked_001",
                "room_type": "Single",
                "check_in": (datetime.now()).date().isoformat(),
                "check_out": (datetime.now() + timedelta(days=1)).date().isoformat(),
                "guests": 1,
                "total_amount": 50000.00,
                "payment_method": "card",
                "email": "blocked@example.com",
                "phone": "+91-6666666666",
                "is_new_user": True,
                "loyalty_points": 0,
                "hours_since_registration": 0.5
            }
        }
    ]

    for test_case in test_cases:
        print(f"\n{'='*70}")
        print(f"TEST CASE: {test_case['name']}")
        print(f"{'='*70}")

        try:
            # Evaluate booking with AI Decision Engine
            result = evaluate_booking(
                test_case["booking_data"],
                user_id=test_case["booking_data"]["user_id"]
            )

            print(f"Decision: {result['decision']}")
            print(f"Risk Level: {result['risk_level']}")
            print(f"Confidence: {result['confidence']:.1f}%")
            print(f"Overall Score: {result['overall_score']:.1f}/100")
            print(f"Recommended Price: INR {result['recommended_price']:,.2f}")
            print(f"Recommended Room: {result['recommended_room']}")
            print(f"Decision ID: {result['decision_id']}")
            print(f"Processing Time: {result['processing_time_ms']:.2f}ms")

            print("\nComponent Scores:")
            print(f"  - Fraud Score: {result['component_scores']['fraud_score']:.1f}/100")
            print(f"  - Cancellation Risk: {result['component_scores']['cancellation_risk']:.1f}/100")
            print(f"  - Demand Score: {result['component_scores']['demand_score']:.1f}/100")
            print(f"  - User Score: {result['component_scores']['user_score']:.1f}/100")

            print("\nReasons:")
            for reason in result['reasons']:
                print(f"  - {reason}")

            print("\nActions:")
            for action in result['actions']:
                print(f"  - {action}")

            print("\nWarnings:")
            for warning in result['warnings']:
                print(f"  [!] {warning}")

            print("\nFactors:")
            print(f"  Fraud Flags: {', '.join(result['factors']['fraud_flags']) or 'None'}")
            print(f"  Cancellation Factors: {', '.join(result['factors']['cancellation_factors']) or 'None'}")
            print(f"  Demand Factors: {', '.join(result['factors']['demand_factors']) or 'None'}")
            print(f"  User Factors: {', '.join(result['factors']['user_factors']) or 'None'}")

        except Exception as e:
            print(f"Error: {e}")

        print()


async def test_decision_statistics():
    """Test decision statistics"""
    print("=" * 70)
    print("AI DECISION STATISTICS TEST")
    print("=" * 70)
    print()

    engine = get_decision_engine()
    stats = engine.get_decision_stats()

    print(f"Total Decisions: {stats['total']}")
    print(f"Approve Count: {stats['approve_count']}")
    print(f"Review Count: {stats['review_count']}")
    print(f"Block Count: {stats['block_count']}")
    print(f"Average Score: {stats['avg_score']:.2f}")

    if stats['recent_decisions']:
        print(f"\nRecent Decisions (last 10):")
        for d in stats['recent_decisions']:
            print(f"  • {d['decision_id']} - {d['decision']} ({d['risk_level']})")


async def test_quick_decision():
    """Test quick decision function"""
    print("=" * 70)
    print("QUICK DECISION TEST")
    print("=" * 70)
    print()

    from ml_models.ai_decision_engine import quick_decision

    result = quick_decision(
        fraud_score=25.0,
        cancel_prob=35.0,
        user_score=75.0,
        demand_score=60.0
    )

    print(f"Decision: {result['decision']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Confidence: {result['confidence']:.1f}%")
    print(f"Overall Score: {result['overall_score']:.1f}/100")

    if result['reasons']:
        print("\nReasoning:")
        for r in result['reasons']:
            print(f"  • {r}")

    if result['actions']:
        print("\nRecommended Actions:")
        for a in result['actions']:
            print(f"  → {a}")

    if result['warnings']:
        print("\nWarnings:")
        for w in result['warnings']:
            print(f"  ⚠️  {w}")


async def main():
    """Main test runner"""
    print("=" * 70)
    print("AI DECISION ENGINE COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()

    await test_ai_decision_engine()
    await test_decision_statistics()
    await test_quick_decision()

    print()
    print("=" * 70)
    print("All tests completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
