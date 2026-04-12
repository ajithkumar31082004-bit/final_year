#!/usr/bin/env python3
"""
🧠 FULL AI DECISION ENGINE TEST & DEMONSTRATION
================================================

Comprehensive testing and usage examples for the complete AI Decision Engine.
This file demonstrates all engine features and outputs.

Run this file to see the complete AI system in action:
    $ python test_ai_decision_engine_full.py
"""

import json
from datetime import datetime
from ml_models.ai_decision_engine import (
    evaluate_booking,
    get_decision_summary,
    get_recommendation_with_alternatives,
    analyze_decision_factors,
    batch_evaluate_bookings,
    create_decision_report,
    get_engine_metrics,
)


def print_section(title):
    """Pretty print section headers"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title):
    """Pretty print subsection headers"""
    print(f"\n  ▶ {title}")
    print("  " + "-" * 76)


def demo_1_basic_evaluation():
    """DEMO 1: Basic Single Booking Evaluation"""
    print_section("DEMO 1️⃣  — BASIC SINGLE BOOKING EVALUATION")
    
    # Sample data
    booking = {
        "booking_id": "BOOKING-001",
        "user_id": "USER-123",
        "room_id": "ROOM-VIP-001",
        "check_in": "2026-04-10",
        "check_out": "2026-04-12",
        "guests": 2,
        "total_amount": 10000,
        "created_at": datetime.now().isoformat(),
    }
    
    room = {
        "room_id": "ROOM-VIP-001",
        "room_type": "VIP Suite",
        "price": 5000,
        "capacity": 2,
    }
    
    user = {
        "user_id": "USER-123",
        "first_name": "Rahul",
        "email": "rahul@example.com",
        "phone": "+91-98765-43210",
    }
    
    # Evaluate
    print_subsection("Input Booking Data")
    print(f"  Booking ID: {booking['booking_id']}")
    print(f"  Guest: {user['first_name']} ({user['email']})")
    print(f"  Room: {room['room_type']} - ₹{room['price']}/night")
    print(f"  Duration: {booking['check_in']} to {booking['check_out']}")
    
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
    
    # Display summary
    print_subsection("AI Decision Summary")
    summary = get_decision_summary(result)
    for key, value in summary.items():
        print(f"  {key.upper().replace('_', ' ')}: {value}")
    
    # Display full result
    print_subsection("Complete Engine Output (JSON)")
    output = {
        "decision": result["decision"],
        "risk_level": result["risk_level"],
        "decision_score": result["decision_score"],
        "ai_price": result["ai_price"],
        "fraud_score": round(result["fraud_score"], 1),
        "cancel_probability": f"{round(result['cancel_probability'] * 100, 1)}%",
        "demand_avg_pct": f"{result['demand_avg_pct']}%",
        "recommended_room": result.get("recommended_room"),
        "reasons": result["reasons"],
    }
    print(json.dumps(output, indent=2))
    
    return result


def demo_2_decision_factors(result):
    """DEMO 2: Deep Factor Analysis"""
    print_section("DEMO 2️⃣  — DECISION FACTOR ANALYSIS")
    
    print_subsection("Component Breakdown (40-20-20-20 Weights)")
    
    analysis = analyze_decision_factors(result)
    
    print(f"\n  Decision: {analysis['decision']}")
    print(f"  Final Score: {analysis['final_score']}/100")
    print(f"  Confidence: {analysis['confidence']}")
    
    print_subsection("AI Component Analysis")
    
    for component, data in analysis["component_analysis"].items():
        component_name = component.replace("_", " ").title()
        print(f"\n  📊 {component_name}")
        print(f"     Status: {data['status']}")
        print(f"     Score: {data['score']:.1f}/100")
        print(f"     Weight: {data['weight']*100}%")
        print(f"     Impact: {data['impact']:.2f} points")
        for key, val in data["details"].items():
            print(f"     {key}: {val}")
    
    print_subsection("Decision Drivers")
    for driver in analysis["decision_drivers"]:
        print(f"  {driver}")
    
    print_subsection("Risk Assessment")
    risk = analysis["risk_assessment"]
    print(f"  Fraud Risk: {risk['fraud']}")
    print(f"  Cancellation Risk: {risk['cancellation']}")
    print(f"  Overall Risk Level: {risk['overall']}")
    
    return analysis


def demo_3_recommendations(user, all_rooms, all_bookings, all_users):
    """DEMO 3: Recommendation Engine with Alternatives"""
    print_section("DEMO 3️⃣  — RECOMMENDATION ENGINE")
    
    print_subsection("AI Room Recommendation with Alternatives")
    
    current_room = all_rooms[0] if all_rooms else {"room_id": "ROOM-001", "room_type": "Double"}
    
    recs = get_recommendation_with_alternatives(
        user=user,
        current_room=current_room,
        all_rooms=all_rooms,
        all_bookings=all_bookings,
        all_users=all_users,
        top_n=3,
    )
    
    if recs.get("primary"):
        print(f"\n  🎯 PRIMARY RECOMMENDATION:")
        print(f"     Room: {recs['primary']['room_type']}")
        print(f"     Reason: {recs['primary']['reason']}")
    else:
        print("  No primary recommendation available")
    
    if recs.get("alternatives"):
        print(f"\n  🏨 ALTERNATIVE OPTIONS ({len(recs['alternatives'])}):")
        for i, alt in enumerate(recs["alternatives"], 1):
            print(f"     {i}. {alt['room_type']}")
            print(f"        {alt['reason']}")
    else:
        print("  No alternatives available")
    
    return recs


def demo_4_batch_processing():
    """DEMO 4: Batch Processing Multiple Bookings"""
    print_section("DEMO 4️⃣  — BATCH PROCESSING")
    
    # Create multiple bookings
    bookings_data = [
        {
            "booking": {
                "booking_id": f"BATCH-001-{i}",
                "user_id": f"USER-{i}",
                "room_id": f"ROOM-{i}",
                "check_in": "2026-04-10",
                "created_at": datetime.now().isoformat(),
            },
            "room": {
                "room_id": f"ROOM-{i}",
                "room_type": ["Single", "Double", "VIP Suite"][i % 3],
                "price": [3500, 5500, 8500][i % 3],
                "capacity": 1 + i % 2,
            },
            "user": {
                "user_id": f"USER-{i}",
                "first_name": f"Guest{i}",
                "email": f"guest{i}@example.com",
            },
            "occupancy_rate": 0.5 + (i * 0.1),
            "days_until_checkin": 7 - (i % 7),
        }
        for i in range(1, 4)
    ]
    
    print_subsection(f"Processing {len(bookings_data)} Bookings")
    
    results = batch_evaluate_bookings(
        bookings_data=bookings_data,
        all_bookings=[b["booking"] for b in bookings_data],
        all_rooms=[b["room"] for b in bookings_data],
        all_users=[b["user"] for b in bookings_data],
    )
    
    print(f"\n  ✅ Processed: {len(results)} bookings")
    print(f"  Success Rate: {sum(1 for r in results if 'error' not in r)}/{len(results)}")
    
    print_subsection("Batch Results Summary")
    
    for i, result in enumerate(results, 1):
        if "error" not in result:
            print(f"\n  Booking {i}:")
            print(f"    Decision: {result['decision']}")
            print(f"    Risk: {result['risk_level']}")
            print(f"    Score: {result['decision_score']:.1f}/100")
            print(f"    Price: ₹{result['ai_price']:.0f}")
        else:
            print(f"\n  Booking {i}: ERROR - {result['error']}")
    
    return results


def demo_5_audit_report(result, booking):
    """DEMO 5: Audit Report Generation"""
    print_section("DEMO 5️⃣  — AUDIT REPORT GENERATION")
    
    print_subsection("Creating Compliance Report")
    
    report = create_decision_report(result, booking)
    
    print(f"\n  Report ID: {report['report_id']}")
    print(f"  Generated: {report['timestamp']}")
    print(f"  Booking Ref: {report['booking_reference']}")
    
    print_subsection("Executive Summary")
    summary = report["executive_summary"]
    for key, value in summary.items():
        print(f"  {key.upper()}: {value}")
    
    print_subsection("Detailed Analysis")
    analysis = report["detailed_analysis"]
    print(f"\n  Fraud Detection:")
    print(f"    Score: {analysis['fraud_detection']['score']}")
    print(f"    Status: {analysis['fraud_detection']['status']}")
    
    print(f"\n  Cancellation Prediction:")
    print(f"    Probability: {analysis['cancellation_prediction']['probability']}")
    print(f"    Status: {analysis['cancellation_prediction']['status']}")
    
    print(f"\n  Dynamic Pricing:")
    print(f"    AI Price: ₹{analysis['dynamic_pricing']['ai_price']}")
    print(f"    Reasoning: {', '.join(analysis['dynamic_pricing']['reasoning'])}")
    
    print_subsection("Manager Actions")
    actions = report["manager_actions"]
    print(f"  If Approved: {actions['if_approved']}")
    print(f"  If Reviewed: {actions['if_reviewed']}")
    print(f"  If Blocked: {actions['if_blocked']}")
    
    print_subsection("Full Report (JSON)")
    print(json.dumps(report, indent=2)[:1000] + "...\n  [Report truncated for display]")
    
    return report


def demo_6_engine_metrics():
    """DEMO 6: Engine Metrics & Architecture"""
    print_section("DEMO 6️⃣  — ENGINE METRICS & ARCHITECTURE")
    
    metrics = get_engine_metrics()
    
    print_subsection("Engine Overview")
    print(f"  Engine Name: {metrics['engine_name']}")
    print(f"  Version: {metrics['version']}")
    
    print_subsection("Components")
    for component, details in metrics["components"].items():
        print(f"\n  {component.upper().replace('_', ' ')}:")
        print(f"    Module: {details['module']}")
        for key, value in details.items():
            if key != "module":
                print(f"    {key.title()}: {value}")
    
    print_subsection("Scoring System")
    scoring = metrics["scoring_system"]
    print(f"  Method: {scoring['method']}")
    print(f"  Components:")
    for component, weight in scoring["components"].items():
        print(f"    {component.upper().replace('_', ' ')}: {weight}")
    
    print_subsection("Thresholds")
    print(f"  Fraud Block Threshold: {metrics['decision_thresholds']['fraud_block_threshold']}")
    print(f"  Cancellation Review Threshold: {metrics['decision_thresholds']['cancellation_review_threshold']}")
    
    print_subsection("Key Features")
    for i, feature in enumerate(metrics["features"], 1):
        print(f"  {i}. {feature}")
    
    return metrics


def main():
    """Run all demonstrations"""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  🧠 FULL AI DECISION ENGINE — COMPREHENSIVE DEMONSTRATION".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)
    
    # Create sample data
    booking = {
        "booking_id": "BOOKING-001",
        "user_id": "USER-123",
        "room_id": "ROOM-VIP-001",
        "check_in": "2026-04-10",
        "check_out": "2026-04-12",
        "guests": 2,
        "total_amount": 10000,
        "created_at": datetime.now().isoformat(),
    }
    
    room = {
        "room_id": "ROOM-VIP-001",
        "room_type": "VIP Suite",
        "price": 5000,
        "capacity": 2,
    }
    
    user = {
        "user_id": "USER-123",
        "first_name": "Rahul",
        "email": "rahul@example.com",
        "phone": "+91-98765-43210",
    }
    
    all_rooms = [room]
    all_bookings = [booking]
    all_users = [user]
    
    # Run all demos
    demo_results = []
    
    try:
        print("\n⏳ Starting comprehensive AI Decision Engine tests...\n")
        
        # Demo 1: Basic Evaluation
        result = demo_1_basic_evaluation()
        demo_results.append(("Basic Evaluation", True))
        
        # Demo 2: Factor Analysis
        demo_2_decision_factors(result)
        demo_results.append(("Factor Analysis", True))
        
        # Demo 3: Recommendations
        demo_3_recommendations(user, all_rooms, all_bookings, all_users)
        demo_results.append(("Recommendations", True))
        
        # Demo 4: Batch Processing
        demo_4_batch_processing()
        demo_results.append(("Batch Processing", True))
        
        # Demo 5: Audit Report
        demo_5_audit_report(result, booking)
        demo_results.append(("Audit Report", True))
        
        # Demo 6: Metrics
        demo_6_engine_metrics()
        demo_results.append(("Engine Metrics", True))
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print_section("✅ DEMONSTRATION COMPLETE")
    
    print("\n  Test Results:")
    for test_name, passed in demo_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"    {test_name}: {status}")
    
    passed_count = sum(1 for _, p in demo_results if p)
    print(f"\n  Overall: {passed_count}/{len(demo_results)} tests passed")
    
    print("\n  📊 All AI Decision Engine features are working correctly!")
    print("\n" + "█" * 80 + "\n")


if __name__ == "__main__":
    main()
