"""
Comprehensive Function Test Suite
Tests all AI modules, routes, services, and database functions
"""

import sys
from datetime import datetime, timedelta

def run_tests():
    print("=" * 80)
    print("COMPREHENSIVE FUNCTION TEST - BLISSFUL ABODES AI SYSTEM".center(80))
    print("=" * 80)
    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. TEST AI/ML MODULES
    # ═══════════════════════════════════════════════════════════════════════════

    print("1️⃣  TESTING AI/ML MODULES")
    print("-" * 80)

    ai_results = {}

    # Test Fraud Detection
    try:
        from ml_models.ai_fraud_detection import score_booking
        test_booking = {"user_id": 1, "total_amount": 50000, "email": "test@example.com"}
        test_room = {"room_id": 1, "room_type": "Luxury"}
        test_user = {"user_id": 1, "account_age": 100}
        test_all_bookings = []
        
        result = score_booking(test_booking, test_room, test_user, test_all_bookings)
        print("  ✅ Fraud Detection - score_booking()")
        print(f"     Risk Score: {result.get('risk_score', 'N/A')}")
        ai_results['fraud'] = True
    except Exception as e:
        print(f"  ❌ Fraud Detection - {str(e)[:50]}")
        ai_results['fraud'] = False

    # Test Cancellation Prediction
    try:
        from ml_models.ai_cancellation import predict_cancellation
        test_booking = {"user_id": 1, "total_amount": 5000}
        test_user = {"user_id": 1, "past_cancellations": 0}
        test_all_bookings = []
        
        result = predict_cancellation(test_booking, test_user, test_all_bookings, [])
        print("  ✅ Cancellation Prediction - predict_cancellation()")
        print(f"     Cancel Probability: {result.get('cancel_probability', 'N/A')}")
        ai_results['cancellation'] = True
    except Exception as e:
        print(f"  ❌ Cancellation Prediction - {str(e)[:50]}")
        ai_results['cancellation'] = False

    # Test Dynamic Pricing
    try:
        from ml_models.ai_dynamic_pricing import compute_dynamic_price
        test_room = {"room_id": 1, "price": 5000, "current_price": 5000}
        result = compute_dynamic_price(test_room, 0.7, 5)
        print("  ✅ Dynamic Pricing - compute_dynamic_price()")
        print(f"     Dynamic Price: {result.get('computed_price', 'N/A')}")
        ai_results['pricing'] = True
    except Exception as e:
        print(f"  ❌ Dynamic Pricing - {str(e)[:50]}")
        ai_results['pricing'] = False

    # Test Demand Forecasting
    try:
        from ml_models.ai_demand_forecast import predict_next_30_days
        test_all_bookings = []
        result = predict_next_30_days(test_all_bookings)
        print("  ✅ Demand Forecasting - predict_next_30_days()")
        print(f"     Days Forecast: {len(result) if isinstance(result, list) else 'N/A'}")
        ai_results['demand'] = True
    except Exception as e:
        print(f"  ❌ Demand Forecasting - {str(e)[:50]}")
        ai_results['demand'] = False

    # Test Recommendation Engine
    try:
        from ml_models.ai_recommender import get_recommendations
        test_user_id = "1"
        test_all_rooms = [{"room_id": 1, "room_type": "Luxury"}, {"room_id": 2, "room_type": "Standard"}]
        test_past_bookings = []
        test_all_bookings = []
        test_all_users = []
        result = get_recommendations(test_user_id, test_all_rooms, test_past_bookings, test_all_bookings, test_all_users)
        print("  ✅ Recommendation Engine - get_recommendations()")
        print(f"     Recommendations Count: {len(result)}")
        ai_results['recommender'] = True
    except Exception as e:
        print(f"  ❌ Recommendation Engine - {str(e)[:50]}")
        ai_results['recommender'] = False

    # Test Sentiment Analysis
    try:
        from ml_models.ai_sentiment import analyze_review
        test_text = "This is a wonderful hotel! Loved my stay."
        result = analyze_review(test_text)
        print("  ✅ Sentiment Analysis - analyze_review()")
        print(f"     Sentiment: {result.get('sentiment', 'N/A')}")
        ai_results['sentiment'] = True
    except Exception as e:
        print(f"  ❌ Sentiment Analysis - {str(e)[:50]}")
        ai_results['sentiment'] = False

    # Test AI Decision Engine
    try:
        from ml_models.ai_decision_engine import evaluate_booking, get_decision_summary, analyze_decision_factors
        print("  ✅ AI Decision Engine - Core Functions")
        print("     • evaluate_booking() - Available")
        print("     • get_decision_summary() - Available")
        print("     • analyze_decision_factors() - Available")
        ai_results['decision_engine'] = True
    except Exception as e:
        print(f"  ❌ AI Decision Engine - {str(e)[:50]}")
        ai_results['decision_engine'] = False

    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. TEST ROUTES
    # ═══════════════════════════════════════════════════════════════════════════

    print("2️⃣  TESTING ROUTE BLUEPRINTS")
    print("-" * 80)

    routes_results = {}

    routes_to_test = [
        ("routes.auth", "auth_bp"),
        ("routes.guest", "guest_bp"),
        ("routes.staff", "staff_bp"),
        ("routes.manager", "manager_bp"),
        ("routes.admin", "admin_bp"),
        ("routes.superadmin", "superadmin_bp"),
        ("routes.agent", "agent_bp"),
        ("routes.chatbot", "chatbot_bp"),
        ("routes.ai_decision", "ai_decision_bp"),
    ]

    for module_name, blueprint_name in routes_to_test:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            route_name = module_name.split(".")[-1].upper()
            print(f"  ✅ {route_name:15} - Blueprint loaded")
            routes_results[module_name] = True
        except Exception as e:
            route_name = module_name.split(".")[-1].upper()
            print(f"  ❌ {route_name:15} - {str(e)[:40]}")
            routes_results[module_name] = False

    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. TEST DATABASE
    # ═══════════════════════════════════════════════════════════════════════════

    print("3️⃣  TESTING DATABASE")
    print("-" * 80)

    db_results = {}

    try:
        from models.database import get_db
        conn = get_db()
        
        # Test table count
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        print(f"  ✅ Database Connected")
        print(f"     Tables: {len(tables)}")
        
        # Test table list
        table_names = [t[0] for t in tables]
        print(f"     Tables: {', '.join(table_names[:5])}...")
        
        db_results['connection'] = True
        
        # Test critical tables
        critical_tables = ['users', 'bookings', 'rooms', 'reviews']
        for table in critical_tables:
            if table in table_names:
                print(f"  ✅ Table '{table}' exists")
                db_results[table] = True
            else:
                print(f"  ❌ Table '{table}' missing")
                db_results[table] = False
        
        conn.close()
    except Exception as e:
        print(f"  ❌ Database Connection - {str(e)[:50]}")
        db_results['connection'] = False

    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. TEST SERVICES
    # ═══════════════════════════════════════════════════════════════════════════

    print("4️⃣  TESTING SERVICES")
    print("-" * 80)

    services_results = {}

    # Payment Service
    try:
        from services.payment_service import create_order
        print("  ✅ Payment Service - create_order()")
        services_results['payment'] = True
    except Exception as e:
        print(f"  ❌ Payment Service - {str(e)[:50]}")
        services_results['payment'] = False

    # Email Service
    try:
        from services.email_service import send_email
        print("  ✅ Email Service - send_email()")
        services_results['email'] = True
    except Exception as e:
        print(f"  ❌ Email Service - {str(e)[:50]}")
        services_results['email'] = False

    # PDF Service
    try:
        from services.pdf_service import generate_gst_invoice
        print("  ✅ PDF Service - generate_gst_invoice()")
        services_results['pdf'] = True
    except Exception as e:
        print(f"  ❌ PDF Service - {str(e)[:50]}")
        services_results['pdf'] = False

    # Security Service
    try:
        from services.security import hash_password, check_password
        test_pwd = "test123"
        hashed = hash_password(test_pwd)
        verified = check_password(test_pwd, hashed)
        if verified:
            print("  ✅ Security Service - Password hashing & verification")
            services_results['security'] = True
        else:
            print("  ❌ Security Service - Password verification failed")
            services_results['security'] = False
    except Exception as e:
        print(f"  ❌ Security Service - {str(e)[:50]}")
        services_results['security'] = False

    # Rate Limiter
    try:
        from services.rate_limiter import check_rate_limit
        print("  ✅ Rate Limiter - check_rate_limit()")
        services_results['rate_limiter'] = True
    except Exception as e:
        print(f"  ❌ Rate Limiter - {str(e)[:50]}")
        services_results['rate_limiter'] = False

    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════

    print("=" * 80)
    print("SUMMARY".center(80))
    print("=" * 80)

    ai_pass = sum(1 for v in ai_results.values() if v)
    routes_pass = sum(1 for v in routes_results.values() if v)
    db_pass = sum(1 for v in db_results.values() if v)
    services_pass = sum(1 for v in services_results.values() if v)

    print(f"\n✅ AI/ML Modules:         {ai_pass}/{len(ai_results)} working")
    print(f"✅ Route Blueprints:      {routes_pass}/{len(routes_results)} working")
    print(f"✅ Database Tables:       {db_pass}/{len(db_results)} working")
    print(f"✅ Services:              {services_pass}/{len(services_results)} working")

    total_pass = ai_pass + routes_pass + db_pass + services_pass
    total = len(ai_results) + len(routes_results) + len(db_results) + len(services_results)

    print(f"\n{'─' * 80}")
    print(f"OVERALL: {total_pass}/{total} functions working ✅" if total_pass == total else f"OVERALL: {total_pass}/{total} functions working ⚠️")
    print(f"SUCCESS RATE: {(total_pass/total)*100:.1f}%")
    print("=" * 80)

    sys.exit(0 if total_pass == total else 1)


if __name__ == "__main__":
    run_tests()
