"""
Blissful Abodes - AWS Lambda Trigger Service
Triggers a Lambda function on booking confirmation which sends
notifications to BOTH the guest and admin via SNS/SES.
"""

import os
import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

# ─── Lambda client (lazy singleton) ───────────────────────────────────────────
_lambda_client = None

def _get_lambda():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'ap-south-1')
        )
    return _lambda_client

# Lambda function names
LAMBDA_NOTIFY_FN  = os.environ.get('LAMBDA_BOOKING_NOTIFY_FN',  'blissful-abodes-booking-notify')
LAMBDA_STORAGE_FN = os.environ.get('LAMBDA_BOOKING_STORAGE_FN', 'blissful-abodes-booking-storage')

def is_configured():
    """Check if Lambda + AWS credentials are available."""
    return bool(
        os.environ.get('AWS_ACCESS_KEY_ID') and
        os.environ.get('AWS_SECRET_ACCESS_KEY')
    )


# ─── 1. Notification Lambda (SNS email to guest + admin) ──────────────────────

def trigger_booking_notification(
    booking_id: str,
    guest_name: str,
    guest_email: str,
    room_number: str,
    room_type: str,
    check_in: str,
    check_out: str,
    total_amount: float,
    payment_id: str = "",
    admin_email: str = ""
) -> dict:
    """
    Invoke 'blissful-abodes-booking-notify' Lambda (async).
    Sends SNS email to BOTH guest and admin on booking confirmation.
    """
    if not is_configured():
        print(f"[LAMBDA] AWS not configured -- skipping notify trigger for {booking_id}")
        return {'success': False, 'message': 'AWS not configured'}

    payload = {
        'booking_id':      booking_id,
        'guest_name':      guest_name,
        'guest_email':     guest_email,
        'room_number':     room_number,
        'room_type':       room_type,
        'check_in':        check_in,
        'check_out':       check_out,
        'total_amount':    round(float(total_amount), 2),
        'payment_id':      payment_id,
        'admin_email':     admin_email or os.environ.get('ADMIN_EMAIL', 'admin@blissfulabodes.com'),
        'triggered_at':    datetime.now().isoformat(),
        'guest_topic_arn': os.environ.get('SNS_GUEST_TOPIC_ARN', ''),
        'admin_topic_arn': os.environ.get('SNS_ADMIN_TOPIC_ARN', ''),
    }

    return _invoke_async(LAMBDA_NOTIFY_FN, payload, booking_id, label='notify')


# ─── 2. Storage Lambda (DynamoDB order record + S3 invoice URL) ───────────────

def trigger_booking_storage(
    booking_id: str,
    order_id: str,
    payment_id: str,
    guest_name: str,
    guest_email: str,
    room_number: str,
    room_type: str,
    check_in: str,
    check_out: str,
    total_amount: float,
    invoice_s3_url: str = "",
    invoice_s3_key: str = "",
    num_guests: int = 1,
) -> dict:
    """
    Invoke 'blissful-abodes-booking-storage' Lambda (async).

    The Lambda will:
      1. Store the full booking record + Razorpay order_id in DynamoDB
         table 'blissful-bookings' (partition key = booking_id).
      2. Record the S3 invoice URL inside the same DynamoDB item so
         admin/guest can retrieve the invoice link any time.
    """
    if not is_configured():
        print(f"[LAMBDA] AWS not configured -- skipping storage trigger for {booking_id}")
        return {'success': False, 'message': 'AWS not configured'}

    payload = {
        # ── booking core ──────────────────────────────────────────────────────
        'booking_id':     booking_id,
        'order_id':       order_id,        # Razorpay order ID
        'payment_id':     payment_id,      # Razorpay payment ID
        'guest_name':     guest_name,
        'guest_email':    guest_email,
        'room_number':    room_number,
        'room_type':      room_type,
        'check_in':       check_in,
        'check_out':      check_out,
        'total_amount':   round(float(total_amount), 2),
        'num_guests':     num_guests,
        'status':         'confirmed',
        'payment_status': 'paid',
        # ── S3 invoice ───────────────────────────────────────────────────────
        'invoice_s3_url': invoice_s3_url,  # public/presigned URL
        'invoice_s3_key': invoice_s3_key,  # e.g. invoices/BK20260719.pdf
        # ── metadata ─────────────────────────────────────────────────────────
        'confirmed_at':   datetime.now().isoformat(),
        # DynamoDB table name passed in payload
        'dynamodb_table': os.environ.get('DYNAMODB_BOOKINGS_TABLE', 'blissful-bookings'),
        'aws_region':     os.environ.get('AWS_REGION', 'ap-south-1'),
    }

    return _invoke_async(LAMBDA_STORAGE_FN, payload, booking_id, label='storage')


# ─── Shared async invoker ─────────────────────────────────────────────────────

def _invoke_async(function_name: str, payload: dict, booking_id: str, label: str) -> dict:
    """Fire a Lambda function asynchronously (InvocationType=Event)."""
    try:
        response = _get_lambda().invoke(
            FunctionName=function_name,
            InvocationType='Event',          # 202 accepted — non-blocking
            Payload=json.dumps(payload).encode('utf-8')
        )
        status = response.get('StatusCode', 0)
        if status == 202:
            print(f"[LAMBDA:{label}] Triggered for {booking_id} (status 202)")
            return {'success': True, 'message': f'Lambda invoked (status {status})'}
        else:
            print(f"[LAMBDA:{label}] Unexpected status {status} for {booking_id}")
            return {'success': False, 'message': f'Unexpected status: {status}'}

    except ClientError as e:
        print(f"[LAMBDA:{label}] ClientError: {e}")
        return {'success': False, 'message': str(e)}
    except Exception as e:
        print(f"[LAMBDA:{label}] Error: {e}")
        return {'success': False, 'message': str(e)}
