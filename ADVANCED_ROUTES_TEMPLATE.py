"""
Advanced Management Routes - New AI Control Center Features
Add these routes to the manager blueprint in routes/manager.py
"""

# ═══════════════════════════════════════════════════════════════════════════
# ADD THESE IMPORTS TO routes/manager.py
# ═══════════════════════════════════════════════════════════════════════════
from ml_models.advanced_management import (
    explain_fraud_reasons,
    get_fraud_risk_level,
    get_fraud_action_recommendation,
    explain_pricing_change,
    get_demand_suggestions,
    analyze_room_popularity,
    analyze_guest_preferences,
    get_popular_amenities,
    calculate_live_kpis,
)
from ml_models.ai_decision_engine import evaluate_booking


# ═══════════════════════════════════════════════════════════════════════════
# 1️⃣ AI DECISION DASHBOARD - FRAUD CONTROL PANEL
# ═══════════════════════════════════════════════════════════════════════════

@manager_bp.route("/manager/ai-decision")
@manager_required
def ai_decision_dashboard():
    """
    Advanced AI Decision Dashboard - Smart Fraud Control Center
    Shows real-time fraud detection, risk levels, and action recommendations
    """
    user = get_current_user()
    conn = get_db()
    
    # Get fraudulent/suspicious bookings
    fraudulent_bookings = conn.execute("""
        SELECT b.*, u.first_name, u.last_name, u.email, r.room_type,
               COALESCE(b.fraud_score, 0) as fraud_score,
               COALESCE(b.cancel_probability, 0) as cancel_prob
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN rooms r ON b.room_id = r.room_id
        WHERE b.fraud_score >= 35 OR b.is_flagged = 1
        ORDER BY b.fraud_score DESC
        LIMIT 50
    """).fetchall()
    
    # Process bookings with explanations
    bookings_data = []
    for booking in fraudulent_bookings:
        booking_dict = dict(booking)
        
        # Get fraud details
        fraud_result = {
            "risk_score": booking_dict.get("fraud_score", 0),
            "triggered_rules": booking_dict.get("fraud_flags", []),
        }
        
        risk_info = get_fraud_risk_level(float(booking_dict.get("fraud_score", 0)))
        action = get_fraud_action_recommendation(fraud_result)
        reasons = explain_fraud_reasons(fraud_result)
        
        booking_dict.update({
            "risk_level": risk_info,
            "recommended_action": action,
            "fraud_explanations": reasons,
            "decision_timestamp": datetime.now().isoformat(),
        })
        
        bookings_data.append(booking_dict)
    
    # Summary statistics
    total_suspicious = len(bookings_data)
    block_count = sum(1 for b in bookings_data if b["recommended_action"] == "BLOCK")
    review_count = sum(1 for b in bookings_data if b["recommended_action"] == "REVIEW")
    
    # Calculate KPIs
    kpis = calculate_live_kpis(
        [dict(b) for b in fraudulent_bookings],
        conn.execute("SELECT * FROM rooms").fetchall(),
        conn.execute("SELECT * FROM reviews").fetchall(),
    )
    
    conn.close()
    
    return render_template(
        "manager/ai_decision_dashboard.html",
        user=user,
        fraudulent_bookings=bookings_data,
        total_suspicious=total_suspicious,
        block_count=block_count,
        review_count=review_count,
        safe_count=total_suspicious - block_count - review_count,
        kpis=kpis,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2️⃣ FRAUD CONTROL PANEL - ACTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@manager_bp.route("/api/manager/fraud/<booking_id>/action", methods=["POST"])
@manager_required
def fraud_action(booking_id):
    """
    Manager action on suspicious booking: APPROVE / BLOCK / VERIFY
    """
    action = request.json.get("action")  # "approve", "block", "verify"
    notes = request.json.get("notes", "")
    
    if action not in ["approve", "block", "verify"]:
        return jsonify({"success": False, "error": "Invalid action"}), 400
    
    conn = get_db()
    
    status_map = {
        "approve": "confirmed",
        "block": "cancelled",
        "verify": "pending",
    }
    
    conn.execute("""
        UPDATE bookings 
        SET status = ?, is_flagged = ?, fraud_notes = ?
        WHERE booking_id = ?
    """, (status_map[action], 0 if action == "approve" else 1, notes, booking_id))
    
    # Log action
    conn.execute("""
        INSERT INTO audit_logs (user_id, action, resource, details)
        VALUES (?, ?, ?, ?)
    """, (session["user_id"], f"fraud_{action}", "booking", booking_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": f"Booking {action}ed"})


@manager_bp.route("/api/manager/fraud/<booking_id>/details")
@manager_required
def fraud_booking_details(booking_id):
    """
    Get detailed fraud analysis for a specific booking
    """
    conn = get_db()
    
    booking = conn.execute("""
        SELECT b.*, u.*, r.room_type
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN rooms r ON b.room_id = r.room_id
        WHERE b.booking_id = ?
    """, (booking_id,)).fetchone()
    
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    booking_dict = dict(booking)
    
    # Get all user's bookings for context
    user_bookings = conn.execute("""
        SELECT COUNT(*) as count FROM bookings WHERE user_id = ?
    """, (booking_dict["user_id"],)).fetchone()
    
    # Fraud explanation
    fraud_result = {
        "risk_score": booking_dict.get("fraud_score", 0),
        "triggered_rules": [],  # Parse from fraud_flags if available
    }
    
    fraud_explanations = explain_fraud_reasons(fraud_result)
    risk_level = get_fraud_risk_level(float(booking_dict.get("fraud_score", 0)))
    
    conn.close()
    
    return jsonify({
        "booking": booking_dict,
        "user_history": {
            "total_bookings": user_bookings["count"],
        },
        "fraud_analysis": {
            "score": float(booking_dict.get("fraud_score", 0)),
            "risk_level": risk_level,
            "explanations": fraud_explanations,
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
# 3️⃣ DYNAMIC PRICING CONTROL DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@manager_bp.route("/manager/pricing-control")
@manager_required
def pricing_control_dashboard():
    """
    Dynamic Pricing Control Panel - View and override AI prices
    """
    user = get_current_user()
    conn = get_db()
    
    # Get all rooms with pricing
    rooms = conn.execute("SELECT * FROM rooms ORDER BY room_type, floor").fetchall()
    
    pricing_engine = get_pricing_engine()
    occupancy_rate = conn.execute("""
        SELECT COUNT(*) as occupied FROM rooms 
        WHERE status IN ('occupied', 'reserved')
    """).fetchone()["occupied"] / max(len(rooms), 1)
    
    # Process pricing data
    pricing_data = []
    for room in rooms:
        room_dict = dict(room)
        base_price = room_dict.get("price", 5000)
        
        # Get AI pricing
        pricing_result = pricing_engine.compute_dynamic_price(
            room_dict, occupancy_rate, days_until_checkin=7
        )
        
        ai_price = pricing_result.get("dynamic_price", base_price)
        price_explanation = explain_pricing_change(pricing_result, base_price)
        
        room_dict.update({
            "base_price": base_price,
            "ai_price": ai_price,
            "price_explanation": price_explanation,
            "current_price": room_dict.get("current_price", base_price),
        })
        
        pricing_data.append(room_dict)
    
    conn.close()
    
    return render_template(
        "manager/pricing_control.html",
        user=user,
        pricing_data=pricing_data,
        occupancy_rate=round(occupancy_rate * 100, 1),
    )


@manager_bp.route("/api/manager/pricing/<room_id>/override", methods=["POST"])
@manager_required
def override_pricing(room_id):
    """
    Manager override dynamic pricing for a room
    """
    new_price = request.json.get("price")
    reason = request.json.get("reason", "Manager override")
    
    if not new_price or new_price <= 0:
        return jsonify({"success": False, "error": "Invalid price"}), 400
    
    conn = get_db()
    
    conn.execute("""
        UPDATE rooms 
        SET current_price = ?, price_override_reason = ?, price_override_by = ?
        WHERE room_id = ?
    """, (float(new_price), reason, session["user_id"], room_id))
    
    # Log action
    conn.execute("""
        INSERT INTO audit_logs (user_id, action, resource, details)
        VALUES (?, ?, ?, ?)
    """, (session["user_id"], "price_override", "room", 
          f"New price: {new_price}, Reason: {reason}"))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Price updated"})


# ═══════════════════════════════════════════════════════════════════════════
# 4️⃣ DEMAND FORECAST & RECOMMENDATIONS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@manager_bp.route("/manager/demand-forecast")
@manager_required
def demand_forecast_dashboard():
    """
    30-day demand forecast with AI suggestions
    """
    user = get_current_user()
    conn = get_db()
    
    demand_model = get_demand_model()
    forecast_data = demand_model.predict_next_30_days()
    
    suggestions = get_demand_suggestions(forecast_data)
    
    conn.close()
    
    return render_template(
        "manager/demand_forecast.html",
        user=user,
        forecast_data=forecast_data,
        suggestions=suggestions,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5️⃣ AI RECOMMENDATIONS INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════

@manager_bp.route("/manager/ai-insights")
@manager_required
def ai_insights_dashboard():
    """
    Analytics dashboard with AI insights on room popularity, guest preferences
    """
    user = get_current_user()
    conn = get_db()
    
    all_bookings = [dict(b) for b in conn.execute("SELECT * FROM bookings").fetchall()]
    all_rooms = [dict(r) for r in conn.execute("SELECT * FROM rooms").fetchall()]
    all_users = [dict(u) for u in conn.execute("SELECT * FROM users").fetchall()]
    all_reviews = [dict(rv) for rv in conn.execute("SELECT * FROM reviews").fetchall()]
    
    # Generate insights
    room_popularity = analyze_room_popularity(all_bookings)
    guest_preferences = analyze_guest_preferences(all_bookings, all_users)
    popular_amenities = get_popular_amenities(all_bookings, all_rooms)
    
    conn.close()
    
    return render_template(
        "manager/ai_insights.html",
        user=user,
        room_popularity=room_popularity,
        guest_preferences=guest_preferences,
        popular_amenities=popular_amenities,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6️⃣ LIVE KPI API for Real-Time Dashboard Updates
# ═══════════════════════════════════════════════════════════════════════════

@manager_bp.route("/api/manager/kpis/live")
@manager_required
def live_kpis():
    """
    Get live KPI metrics for dashboard
    """
    conn = get_db()
    
    all_bookings = [dict(b) for b in conn.execute("SELECT * FROM bookings").fetchall()]
    all_rooms = [dict(r) for r in conn.execute("SELECT * FROM rooms").fetchall()]
    all_reviews = [dict(rv) for rv in conn.execute("SELECT * FROM reviews").fetchall()]
    
    kpis = calculate_live_kpis(all_bookings, all_rooms, all_reviews)
    
    conn.close()
    
    return jsonify(kpis)
