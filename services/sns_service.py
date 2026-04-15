"""
Blissful Abodes - AWS SNS Notification Service
Sends booking confirmations and fraud alerts via AWS SNS → SES/SMS
"""
import os
import boto3
from botocore.exceptions import ClientError

_sns_client = None

def _get_sns():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client(
            'sns',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'ap-south-1')
        )
    return _sns_client

ADMIN_TOPIC_ARN = os.environ.get('SNS_ADMIN_TOPIC_ARN', '')
GUEST_TOPIC_ARN = os.environ.get('SNS_GUEST_TOPIC_ARN', '')

def is_configured():
    return bool(os.environ.get('AWS_ACCESS_KEY_ID')) and bool(ADMIN_TOPIC_ARN)

def send_booking_confirmation(user_email: str, booking_id: str, room_number: str,
                               check_in: str, check_out: str, total_amount: float) -> bool:
    """Send booking confirmation to guest via SNS."""
    if not is_configured():
        print(f"[SNS] Not configured — skipping booking confirmation for {booking_id}")
        return False
    try:
        _get_sns().publish(
            TopicArn=GUEST_TOPIC_ARN,
            Subject=f"✅ Booking Confirmed — {booking_id}",
            Message=f"""Namaste! Your booking at Blissful Abodes Chennai is confirmed.

Booking ID : {booking_id}
Room       : {room_number}
Check-in   : {check_in}
Check-out  : {check_out}
Amount     : ₹{total_amount:,.2f}

Please present this Booking ID at the front desk.
Thank you for choosing Blissful Abodes!
""",
            MessageAttributes={
                'email': {'DataType': 'String', 'StringValue': user_email}
            }
        )
        print(f"[SNS] Booking confirmation sent for {booking_id}")
        return True
    except ClientError as e:
        print(f"[SNS] Failed to send booking confirmation: {e}")
        return False

def send_fraud_alert(booking_id: str, fraud_score: float, reason: str,
                      user_email: str = "") -> bool:
    """Send fraud alert to admin team via SNS."""
    if not is_configured():
        print(f"[SNS] Not configured — skipping fraud alert for {booking_id}")
        return False
    try:
        _get_sns().publish(
            TopicArn=ADMIN_TOPIC_ARN,
            Subject=f"🚨 FRAUD ALERT — Booking {booking_id}",
            Message=f"""High-risk booking detected by AI Fraud Engine!

Booking ID   : {booking_id}
Guest Email  : {user_email}
Fraud Score  : {fraud_score:.2f} / 1.00
Risk Reason  : {reason}

⚠️ ACTION REQUIRED: Review this booking in the Admin Dashboard immediately.
Dashboard: http://13.206.110.152:5000/admin/bookings
"""
        )
        print(f"[SNS] Fraud alert sent for {booking_id}")
        return True
    except ClientError as e:
        print(f"[SNS] Failed to send fraud alert: {e}")
        return False

def send_cancellation_alert(user_email: str, booking_id: str, room_number: str,
                             refund_amount: float) -> bool:
    """Send cancellation confirmation to guest via SNS."""
    if not is_configured():
        return False
    try:
        _get_sns().publish(
            TopicArn=GUEST_TOPIC_ARN,
            Subject=f"Booking Cancelled — {booking_id}",
            Message=f"""Your booking {booking_id} (Room {room_number}) has been cancelled.

Refund of ₹{refund_amount:,.2f} will be processed in 5-7 business days.

We hope to welcome you again at Blissful Abodes Chennai!
""",
            MessageAttributes={
                'email': {'DataType': 'String', 'StringValue': user_email}
            }
        )
        return True
    except ClientError as e:
        print(f"[SNS] Failed to send cancellation alert: {e}")
        return False
