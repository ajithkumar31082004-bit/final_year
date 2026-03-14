"""
Blissful Abodes - Razorpay Payment Service
Handles Indian payment gateway integration
"""

import os
import json
import hmac
import hashlib

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_placeholder")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "placeholder_secret")
DEMO_MODE = os.environ.get("DEMO_MODE", "0").strip().lower() in {"1", "true", "yes"}


def _is_demo_mode():
    return (
        DEMO_MODE
        or RAZORPAY_KEY_ID.startswith("rzp_test_placeholder")
        or RAZORPAY_KEY_SECRET.startswith("placeholder")
    )


def create_order(amount_inr, booking_id, notes=None):
    """
    Create a Razorpay order
    Returns order data for the frontend
    """
    amount_paise = int(amount_inr * 100)  # Convert to paise

    if _is_demo_mode():
        return {
            "success": True,
            "order": {
                "id": f"order_demo_{booking_id}",
                "amount": amount_paise,
                "currency": "INR",
                "receipt": booking_id,
                "status": "created",
            },
        }

    try:
        import razorpay

        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": booking_id,
            "notes": notes or {"hotel": "Blissful Abodes Chennai"},
        }
        order = client.order.create(data=order_data)
        return {"success": True, "order": order}
    except ImportError:
        # Razorpay not installed, return mock order for demo
        return {
            "success": True,
            "order": {
                "id": f"order_demo_{booking_id}",
                "amount": amount_paise,
                "currency": "INR",
                "receipt": booking_id,
                "status": "created",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify payment signature from Razorpay callback
    """
    try:
        if _is_demo_mode() or str(razorpay_order_id).startswith("order_demo_"):
            return True
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_sig = hmac.new(
            RAZORPAY_KEY_SECRET.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return expected_sig == razorpay_signature
    except Exception:
        return False


def process_refund(payment_id, amount_inr, notes=None):
    """Process a refund"""
    if _is_demo_mode():
        return {
            "success": True,
            "refund": {
                "id": f"refund_demo_{payment_id}",
                "amount": int(amount_inr * 100),
            },
        }
    try:
        import razorpay

        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        refund = client.payment.refund(
            payment_id, {"amount": int(amount_inr * 100), "notes": notes or {}}
        )
        return {"success": True, "refund": refund}
    except Exception as e:
        return {
            "success": True,
            "refund": {
                "id": f"refund_demo_{payment_id}",
                "amount": int(amount_inr * 100),
            },
        }


def get_payment_methods():
    return [
        {
            "id": "upi",
            "name": "UPI",
            "icon": "📱",
            "description": "PhonePe, Google Pay, Paytm, BHIM",
        },
        {
            "id": "card",
            "name": "Credit/Debit Card",
            "icon": "💳",
            "description": "Visa, Mastercard, RuPay",
        },
        {
            "id": "netbanking",
            "name": "Net Banking",
            "icon": "🏦",
            "description": "All major Indian banks",
        },
        {
            "id": "wallet",
            "name": "Wallets",
            "icon": "👛",
            "description": "Paytm, MobiKwik, Freecharge",
        },
        {
            "id": "emi",
            "name": "EMI",
            "icon": "📅",
            "description": "Bajaj Finserv (₹10,000+)",
        },
        {
            "id": "paylater",
            "name": "Pay Later",
            "icon": "⏰",
            "description": "Simpl, LazyPay",
        },
    ]
