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

# Lambda function name deployed on AWS
LAMBDA_FUNCTION_NAME = os.environ.get(
    'LAMBDA_BOOKING_NOTIFY_FN',
    'blissful-abodes-booking-notify'
)

def is_configured():
    """Check if Lambda + AWS credentials are available."""
    return bool(
        os.environ.get('AWS_ACCESS_KEY_ID') and
        os.environ.get('AWS_SECRET_ACCESS_KEY')
    )


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
    Invoke the AWS Lambda function 'blissful-abodes-booking-notify'.
    The Lambda reads the payload and publishes to two SNS topics:
      - GUEST_TOPIC_ARN  -> guest booking confirmation email
      - ADMIN_TOPIC_ARN  -> admin new-booking alert email

    Invocation type: Event (asynchronous -- non-blocking).
    Returns: {'success': True/False, 'message': str}
    """
    if not is_configured():
        print(f"[LAMBDA] AWS not configured -- skipping Lambda trigger for {booking_id}")
        return {'success': False, 'message': 'AWS not configured'}

    payload = {
        'booking_id':   booking_id,
        'guest_name':   guest_name,
        'guest_email':  guest_email,
        'room_number':  room_number,
        'room_type':    room_type,
        'check_in':     check_in,
        'check_out':    check_out,
        'total_amount': round(float(total_amount), 2),
        'payment_id':   payment_id,
        'admin_email':  admin_email or os.environ.get('ADMIN_EMAIL', 'admin@blissfulabodes.com'),
        'triggered_at': datetime.now().isoformat(),
        # SNS ARNs passed in payload so Lambda doesn't need env vars of its own
        'guest_topic_arn': os.environ.get('SNS_GUEST_TOPIC_ARN', ''),
        'admin_topic_arn': os.environ.get('SNS_ADMIN_TOPIC_ARN', ''),
    }

    try:
        response = _get_lambda().invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='Event',          # async -- does not block Flask response
            Payload=json.dumps(payload).encode('utf-8')
        )
        status = response.get('StatusCode', 0)
        if status == 202:                    # 202 = accepted (async invocation)
            print(f"[LAMBDA] Booking notification Lambda triggered for {booking_id}")
            return {'success': True, 'message': f'Lambda invoked (status {status})'}
        else:
            print(f"[LAMBDA] Unexpected status {status} for {booking_id}")
            return {'success': False, 'message': f'Unexpected status: {status}'}

    except ClientError as e:
        print(f"[LAMBDA] ClientError: {e}")
        return {'success': False, 'message': str(e)}
    except Exception as e:
        print(f"[LAMBDA] Error: {e}")
        return {'success': False, 'message': str(e)}
