"""
Advanced AI Management Features - Helper Functions
Supports the new manager dashboards and control panels
"""

from datetime import datetime, timedelta
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════
# 1️⃣ FRAUD EXPLANATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def explain_fraud_reasons(fraud_result: dict) -> list:
    """
    Generate human-readable fraud reasons from fraud detection result.
    
    Args:
        fraud_result: Dict from ai_fraud_detection.score_booking()
    
    Returns:
        List of readable explanation strings with emojis
    """
    reasons = []
    
    triggered_rules = fraud_result.get("triggered_rules", [])
    risk_score = fraud_result.get("risk_score", 0)
    
    # Build explanations based on triggered rules
    rule_explanations = {
        "rapid_multi_booking": "🚨 Multiple bookings within 1 hour detected",
        "repeat_canceller": "⚠️ User has history of frequent cancellations",
        "capacity_mismatch": "👥 Guest count exceeds room capacity",
        "new_account_luxury": "🆕 New account booking high-tier room",
        "price_anomaly": "💰 Booking amount significantly different from average",
        "last_minute_no_history": "⏰ Same-day booking with no prior stays",
    }
    
    for rule in triggered_rules:
        rule_name = rule.get("rule", "")
        rule_score = rule.get("score", 0)
        
        if rule_name in rule_explanations:
            explanation = rule_explanations[rule_name]
            reasons.append(f"{explanation} (+{rule_score} points)")
        elif rule_name == "ML Probability":
            ml_prob = rule.get("probability", 0)
            reasons.append(f"🤖 ML Model fraud probability: {ml_prob:.1%}")
    
    if not reasons:
        if risk_score >= 60:
            reasons.append("🚨 High-risk booking detected by AI")
        elif risk_score >= 35:
            reasons.append("⚠️ Moderate fraud indicators present")
        else:
            reasons.append("✅ Low fraud risk - safe booking")
    
    return reasons


def get_fraud_risk_level(fraud_score: float) -> dict:
    """
    Classify fraud risk into visual levels.
    
    Returns:
        {
            "level": "LOW" | "MEDIUM" | "HIGH",
            "emoji": "🟢" | "🟡" | "🔴",
            "color": "green" | "yellow" | "red"
        }
    """
    if fraud_score >= 60:
        return {"level": "HIGH", "emoji": "🔴", "color": "red"}
    elif fraud_score >= 35:
        return {"level": "MEDIUM", "emoji": "🟡", "color": "yellow"}
    else:
        return {"level": "LOW", "emoji": "🟢", "color": "green"}


def get_fraud_action_recommendation(fraud_result: dict) -> str:
    """
    Suggest action for manager based on fraud risk.
    
    Returns:
        "APPROVE" | "REVIEW" | "BLOCK"
    """
    fraud_score = fraud_result.get("risk_score", 0)
    
    if fraud_score >= 60:
        return "BLOCK"
    elif fraud_score >= 35:
        return "REVIEW"
    else:
        return "APPROVE"


# ═══════════════════════════════════════════════════════════════════════════
# 2️⃣ DYNAMIC PRICING EXPLANATIONS
# ═══════════════════════════════════════════════════════════════════════════

def explain_pricing_change(pricing_result: dict, base_price: float) -> dict:
    """
    Explain why price changed from base.
    
    Returns:
        {
            "base_price": float,
            "dynamic_price": float,
            "change_percent": float,
            "reasons": [str],  # Human-readable explanations
        }
    """
    dynamic_price = pricing_result.get("dynamic_price", base_price)
    reasons = pricing_result.get("reasons", [])
    
    if dynamic_price > base_price:
        change_pct = round(((dynamic_price - base_price) / base_price) * 100, 1)
        direction = "⬆️ INCREASED"
    elif dynamic_price < base_price:
        change_pct = round(((base_price - dynamic_price) / base_price) * 100, 1)
        direction = "⬇️ DECREASED"
    else:
        change_pct = 0
        direction = "➡️ NO CHANGE"
    
    # Build explanation
    explanation = f"{direction} by {abs(change_pct)}%"
    
    # Add reason details
    detailed_reasons = []
    for reason in reasons[:3]:  # Top 3 reasons
        detailed_reasons.append(f"• {reason}")
    
    return {
        "base_price": round(base_price, 2),
        "dynamic_price": round(dynamic_price, 2),
        "change_percent": change_pct,
        "direction": direction,
        "summary": explanation,
        "detailed_reasons": detailed_reasons,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3️⃣ DEMAND FORECAST INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════

def get_demand_suggestions(demand_data: list) -> dict:
    """
    Generate actionable business suggestions from demand forecast.
    
    Args:
        demand_data: List of forecast dicts with occupancy_pct
    
    Returns:
        {
            "peak_days": [str],
            "low_days": [str],
            "recommendations": [str],
            "avg_occupancy": float,
        }
    """
    if not demand_data:
        return {
            "peak_days": [],
            "low_days": [],
            "recommendations": [],
            "avg_occupancy": 0,
        }
    
    occupancy_pcts = [d.get("occupancy_pct", 0) for d in demand_data]
    avg_occupancy = sum(occupancy_pcts) / len(occupancy_pcts) if occupancy_pcts else 50
    
    # Find peak and low days
    peak_days = [
        d.get("date", "") 
        for d in demand_data 
        if d.get("occupancy_pct", 0) >= 75
    ]
    
    low_days = [
        d.get("date", "") 
        for d in demand_data 
        if d.get("occupancy_pct", 0) <= 40
    ]
    
    # Generate recommendations
    recommendations = []
    
    if avg_occupancy > 70:
        recommendations.append("📈 High overall demand - consider increasing prices")
    elif avg_occupancy < 40:
        recommendations.append("📉 Low overall demand - launch promotional offers")
    
    if peak_days:
        recommendations.append(f"🔥 Peak demand expected on {len(peak_days)} days - maximize pricing")
    
    if low_days:
        recommendations.append(f"❄️ Low occupancy expected on {len(low_days)} days - offer discounts")
    
    return {
        "peak_days": peak_days,
        "low_days": low_days,
        "avg_occupancy": round(avg_occupancy, 1),
        "recommendations": recommendations,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4️⃣ RECOMMENDATION INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════

def analyze_room_popularity(all_bookings: list) -> dict:
    """
    Analyze which rooms are most popular.
    
    Returns:
        {
            "most_booked": [{"room_type": str, "count": int, "percentage": float}],
            "least_booked": [...]
        }
    """
    room_counts = defaultdict(int)
    
    for booking in all_bookings:
        room_type = booking.get("room_type")
        if room_type:
            room_counts[room_type] += 1
    
    total = sum(room_counts.values()) or 1
    
    # Sort by count
    sorted_rooms = sorted(
        room_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    most_booked = [
        {
            "room_type": room_type,
            "count": count,
            "percentage": round((count / total) * 100, 1)
        }
        for room_type, count in sorted_rooms[:5]
    ]
    
    least_booked = [
        {
            "room_type": room_type,
            "count": count,
            "percentage": round((count / total) * 100, 1)
        }
        for room_type, count in sorted_rooms[-3:]
    ]
    
    return {
        "most_booked": most_booked,
        "least_booked": least_booked,
        "total_bookings": len(all_bookings),
    }


def analyze_guest_preferences(all_bookings: list, all_users: list) -> dict:
    """
    Analyze guest preferences by user tier/type.
    
    Returns:
        {
            "tier_preferences": {
                "Platinum": ["vip", "couple"],
                "Gold": ["double", "family"],
            },
            "insights": [str],
        }
    """
    tier_rooms = defaultdict(lambda: defaultdict(int))
    
    # Map user ID to tier
    user_tiers = {u.get("user_id"): u.get("loyalty_tier") for u in all_users}
    
    for booking in all_bookings:
        user_id = booking.get("user_id")
        room_type = booking.get("room_type")
        tier = user_tiers.get(user_id, "Regular")
        
        if tier and room_type:
            tier_rooms[tier][room_type] += 1
    
    # Get top room type per tier
    tier_preferences = {}
    for tier, rooms in tier_rooms.items():
        top_rooms = sorted(rooms.items(), key=lambda x: x[1], reverse=True)
        tier_preferences[tier] = [room_type for room_type, _ in top_rooms[:2]]
    
    # Generate insights
    insights = []
    if "Platinum" in tier_preferences:
        preferred = tier_preferences["Platinum"]
        insights.append(f"💎 Platinum members prefer: {', '.join(preferred)}")
    
    if "Gold" in tier_preferences:
        preferred = tier_preferences["Gold"]
        insights.append(f"✨ Gold members popular choice: {', '.join(preferred)}")
    
    return {
        "tier_preferences": tier_preferences,
        "insights": insights,
    }


def get_popular_amenities(all_bookings: list, all_rooms: list) -> dict:
    """
    Extract popular amenities from room bookings.
    
    Returns:
        {
            "top_amenities": [{"amenity": str, "rooms": int}],
            "insights": [str],
        }
    """
    # Map room_id to amenities
    room_amenities = {}
    for room in all_rooms:
        amenities = room.get("amenities", "").split(",")
        room_amenities[room.get("room_id")] = [a.strip() for a in amenities if a.strip()]
    
    # Count amenity popularity
    amenity_counts = defaultdict(int)
    for booking in all_bookings:
        room_id = booking.get("room_id")
        amenities = room_amenities.get(room_id, [])
        for amenity in amenities:
            amenity_counts[amenity] += 1
    
    # Top amenities
    top_amenities = sorted(
        [{"amenity": a, "rooms": c} for a, c in amenity_counts.items()],
        key=lambda x: x["rooms"],
        reverse=True
    )[:5]
    
    insights = []
    if top_amenities:
        top = top_amenities[0]["amenity"]
        insights.append(f"⭐ Most desired amenity: {top}")
    
    return {
        "top_amenities": top_amenities,
        "insights": insights,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5️⃣ REAL-TIME KPI ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def calculate_live_kpis(
    all_bookings: list,
    all_rooms: list,
    all_reviews: list,
) -> dict:
    """
    Calculate live KPIs for dashboard.
    
    Returns:
        {
            "total_bookings": int,
            "occupancy_rate": float,
            "avg_rating": float,
            "fraud_bookings": int,
            "high_risk_bookings": int,
            "safe_bookings": int,
            "revenue_today": float,
            "checkins_today": int,
            "checkouts_today": int,
        }
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_bookings = len(all_bookings)
    
    # Occupancy
    occupied_rooms = sum(1 for r in all_rooms if r.get("status") in ["occupied", "reserved"])
    total_rooms = len(all_rooms)
    occupancy_rate = round((occupied_rooms / total_rooms * 100) if total_rooms else 0, 1)
    
    # Rating
    avg_rating = 0
    if all_reviews:
        ratings = [r.get("overall_rating", 0) for r in all_reviews]
        avg_rating = round(sum(ratings) / len(ratings), 1)
    
    # Fraud analysis
    fraud_bookings = sum(1 for b in all_bookings if b.get("fraud_score", 0) >= 60)
    high_risk = sum(1 for b in all_bookings if b.get("fraud_score", 0) >= 35)
    safe_bookings = total_bookings - fraud_bookings
    
    # Revenue
    revenue_today = sum(b.get("total_amount", 0) for b in all_bookings 
                       if b.get("created_at", "").startswith(today) and b.get("payment_status") == "paid")
    
    # Check-ins/outs
    checkins = sum(1 for b in all_bookings if b.get("check_in") == today)
    checkouts = sum(1 for b in all_bookings if b.get("check_out") == today)
    
    return {
        "total_bookings": total_bookings,
        "occupancy_rate": occupancy_rate,
        "avg_rating": avg_rating,
        "fraud_bookings": fraud_bookings,
        "high_risk_bookings": high_risk,
        "safe_bookings": safe_bookings,
        "revenue_today": round(revenue_today, 2),
        "checkins_today": checkins,
        "checkouts_today": checkouts,
    }
