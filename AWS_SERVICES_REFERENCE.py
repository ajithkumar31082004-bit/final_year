"""
AWS Services Reference Guide - Complete Implementation
======================================================

This guide provides a complete reference for all AWS services integrated
into the Blissful Abodes application.
"""

# ═══════════════════════════════════════════════════════════════════════════
# 1. AWS S3 - SIMPLE STORAGE SERVICE
# ═══════════════════════════════════════════════════════════════════════════

"""
📋 SERVICE: AWS S3 (Simple Storage Service)
🎯 PURPOSE: Cloud file storage for images, QR codes, and invoices
📁 LOCATION: services/s3_service.py

FUNCTIONS:
-----------
• upload_file(local_path, s3_key, public=True) → str
  - Upload any file to S3
  - Returns S3 public URL or local fallback
  - Example: upload_file("invoice.pdf", "invoices/BOOKING-123.pdf")
  
• upload_qr(local_path, booking_id) → str
  - Upload booking QR code to S3/qrcodes/
  - Automatically named and stored
  
• upload_room_image(local_path, room_id, index=0) → str
  - Upload room photo to S3/rooms/
  - Supports multiple images per room
  
• upload_invoice(local_path, booking_id) → str
  - Upload GST invoice PDF to S3/invoices/
  - Stored securely with no public access
  
• is_configured() → bool
  - Check if AWS credentials are available

ENVIRONMENT VARIABLES:
----------------------
AWS_ACCESS_KEY_ID          - AWS API key
AWS_SECRET_ACCESS_KEY      - AWS API secret
AWS_REGION                 - Default: ap-south-1
S3_BUCKET                  - Default: blissful-abodes-media

USAGE EXAMPLE:
--------------
from services.s3_service import upload_room_image

url = upload_room_image("local/bedroom.jpg", room_id="101", index=1)
# Returns: https://blissful-abodes-media.s3.ap-south-1.amazonaws.com/rooms/101_1.jpg

FALLBACK:
---------
If AWS credentials are not configured, files are stored locally
and local path is returned instead of S3 URL.
"""


# ═══════════════════════════════════════════════════════════════════════════
# 2. AWS DynamoDB - NOSQL DATABASE
# ═══════════════════════════════════════════════════════════════════════════

"""
📋 SERVICE: AWS DynamoDB (NoSQL Database)
🎯 PURPOSE: Store sessions, chat history, and audit logs
📁 LOCATION: services/dynamodb_service.py

TABLES STRUCTURE:
-----------------
1. blissful-sessions
   • PK: session_id (String)
   • Attributes: user_id, data (JSON), updated_at, ttl
   • TTL: 24 hours
   • Use: Store Flask session data across EC2 instances

2. blissful-chatbot-history
   • PK: user_id (String) | SK: timestamp (String)
   • Attributes: role, content, ttl
   • TTL: 30 days
   • Use: Unlimited chat history without bloating SQL DB

3. blissful-audit-logs
   • PK: user_id (String) | SK: timestamp (String)
   • Attributes: action, details (JSON)
   • TTL: Disabled (permanent audit trail)
   • Use: Tamper-proof compliance logging

FUNCTIONS:
----------
• save_session(session_id, user_id, data) → bool
  - Persist Flask sessions to DynamoDB
  
• load_session(session_id) → dict
  - Retrieve session data
  
• save_chat_message(user_id, role, content) → bool
  - Store chatbot messages
  
• get_chat_history(user_id, limit=20) → list
  - Retrieve last N messages
  
• log_audit_event(user_id, action, details) → bool
  - Write audit log entry
  
• get_audit_logs(user_id, limit=50) → list
  - Retrieve audit history

ENVIRONMENT VARIABLES:
----------------------
DYNAMODB_SESSIONS_TABLE     - Default: blissful-sessions
DYNAMODB_CHATBOT_TABLE      - Default: blissful-chatbot-history
DYNAMODB_AUDIT_TABLE        - Default: blissful-audit-logs
AWS_REGION                  - Default: ap-south-1

USAGE EXAMPLE:
--------------
from services.dynamodb_service import save_session, log_audit_event

# Save session
save_session("sess-xyz", "user-123", {"cart": [1, 2, 3]})

# Log audit event
log_audit_event("user-123", "booking_created", {
    "booking_id": "BOOK-456",
    "room_id": "101",
    "amount": 5000
})

COST MODEL:
-----------
DynamoDB uses PAY_PER_REQUEST (on-demand) billing:
• Read: $0.25 per million read units
• Write: $1.25 per million write units
• Estimated cost: $2-10/month for low traffic

SCALING:
--------
DynamoDB automatically scales to handle:
• Backup: Point-in-time recovery enabled
• Replication: Multi-region replication available
• Monitoring: CloudWatch metrics available
"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. AWS EC2 - ELASTIC COMPUTE CLOUD
# ═══════════════════════════════════════════════════════════════════════════

"""
📋 SERVICE: AWS EC2 (Elastic Compute Cloud)
🎯 PURPOSE: Monitor cloud instance health and retrieve metadata
📁 LOCATION: services/ec2_service.py

FUNCTIONS:
----------
• get_instance_info(instance_id=None) → dict
  - Returns instance metadata
  - Fields: instance_id, instance_type, state, public_ip, private_ip,
            launch_time, availability_zone, ami_id, key_name
  
• get_instance_status(instance_id=None) → dict
  - Returns instance health status
  
• get_cpu_metrics(instance_id=None) → dict
  - Returns CloudWatch CPU metrics
  
• auto_scale_status() → dict
  - Returns auto-scaling group status

ENVIRONMENT VARIABLES:
----------------------
EC2_INSTANCE_ID             - e.g., i-0abc1234def56789
EC2_INSTANCE_TYPE           - e.g., t2.micro
EC2_PUBLIC_IP               - e.g., 44.208.253.176
AWS_REGION                  - Default: ap-south-1

USAGE EXAMPLE:
--------------
from services.ec2_service import get_instance_info

# Get current instance metadata
info = get_instance_info()
print(f"Instance: {info['instance_id']}")
print(f"Status: {info['state']}")
print(f"Public IP: {info['public_ip']}")

OUTPUT:
-------
{
    'instance_id': 'i-0abc1234def56789',
    'instance_type': 't2.micro',
    'state': 'running',
    'public_ip': '44.208.253.176',
    'private_ip': '172.31.0.100',
    'region': 'ap-south-1',
    'ami_id': 'ami-0123456789abcdef0',
    'key_name': 'my-key-pair'
}

INTEGRATION:
------------
• Admin dashboard displays instance health
• Auto-scaling triggers based on CPU metrics
• CloudWatch alarms notify on unhealthy instances
• Metrics available in AWS Management Console

INSTANCE TYPES:
---------------
• t2.micro (Free tier eligible) - 1 vCPU, 1 GB RAM
• t2.small - 1 vCPU, 2 GB RAM
• t2.medium - 1 vCPU, 4 GB RAM
• t2.large - 2 vCPU, 8 GB RAM
"""


# ═══════════════════════════════════════════════════════════════════════════
# 4. AWS IAM - IDENTITY & ACCESS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

"""
📋 SERVICE: AWS IAM (Identity & Access Management)
🎯 PURPOSE: Manage roles, permissions, and secure credentials
📁 LOCATION: services/iam_service.py

FUNCTIONS:
----------
• get_caller_identity() → dict
  - Returns AWS account ID, user ARN, and user ID
  - Useful for verifying credentials
  
• get_role_info(role_name=None) → dict
  - Retrieve IAM role details
  - Uses EC2_INSTANCE_ROLE by default
  
• get_role_policies(role_name=None) → dict
  - List inline policies attached to role
  
• generate_temporary_credentials(duration_seconds=3600) → dict
  - Generate temporary AWS credentials via STS
  - Uses AssumeRole for cross-account access

ENVIRONMENT VARIABLES:
----------------------
IAM_INSTANCE_ROLE           - Default: blissful-abodes-ec2-role
AWS_REGION                  - Default: ap-south-1

USAGE EXAMPLE:
--------------
from services.iam_service import get_caller_identity, get_role_info

# Get current AWS account info
identity = get_caller_identity()
print(f"Account: {identity['account_id']}")
print(f"ARN: {identity['arn']}")

# Get EC2 instance role info
role = get_role_info()
print(f"Role: {role['role_name']}")
print(f"Assumed By: {role['assume_role_policy']}")

REQUIRED PERMISSIONS (Inline Policy):
--------------------------------------
{
    "Effect": "Allow",
    "Action": [
        "iam:GetRole",
        "iam:GetUser",
        "iam:ListRolePolicies",
        "sts:GetCallerIdentity",
        "sts:AssumeRole"
    ],
    "Resource": "*"
}

SECURITY BEST PRACTICES:
------------------------
1. Use IAM roles instead of long-term access keys
2. Implement least privilege principle
3. Rotate credentials every 90 days
4. Enable MFA for admin access
5. Use temporary credentials from STS when possible
6. Enable CloudTrail for audit logging

EC2 INSTANCE ROLE:
------------------
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Service": "ec2.amazonaws.com",
            "Action": "sts:AssumeRole"
        }
    ]
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# 5. AWS SNS - SIMPLE NOTIFICATION SERVICE
# ═══════════════════════════════════════════════════════════════════════════

"""
📋 SERVICE: AWS SNS (Simple Notification Service)
🎯 PURPOSE: Send notifications via email and SMS
📁 LOCATION: services/sns_service.py

TOPICS:
-------
1. blissful-admin-alerts
   • Subscribers: admin@blissfulabodes.com
   • Triggers: Fraud alerts, high-risk bookings, system issues
   
2. blissful-guest-notifications
   • Subscribers: guests (via SQS or Lambda)
   • Triggers: Booking confirmations, check-in reminders, reviews

FUNCTIONS:
----------
• send_booking_confirmation(user_email, booking_id, room_number,
                            check_in, check_out, total_amount) → bool
  - Send confirmation to guest
  
• send_fraud_alert(booking_id, fraud_score, reason,
                   user_email="") → bool
  - Send high-risk alert to admin
  
• send_cancellation_alert(booking_id, user_email, reason) → bool
  - Notify about cancellation
  
• send_sms(phone_number, message) → bool
  - Send SMS notification (requires SNS SMS configuration)

ENVIRONMENT VARIABLES:
----------------------
SNS_ADMIN_TOPIC_ARN         - ARN of admin alerts topic
SNS_GUEST_TOPIC_ARN         - ARN of guest notifications topic
AWS_REGION                  - Default: ap-south-1

USAGE EXAMPLE:
--------------
from services.sns_service import send_booking_confirmation, send_fraud_alert

# Send booking confirmation
send_booking_confirmation(
    user_email="guest@example.com",
    booking_id="BOOKING-12345",
    room_number="401",
    check_in="2026-04-15",
    check_out="2026-04-17",
    total_amount=15000
)

# Send fraud alert
send_fraud_alert(
    booking_id="BOOKING-12345",
    fraud_score=0.95,
    reason="Multiple rapid bookings from new account",
    user_email="guest@example.com"
)

MESSAGE FLOW:
-------------
send_booking_confirmation()
        ↓
  SNS Topic (guest-notifications)
        ↓
  Email Subscription
        ↓
  Guest's Email

TOPIC SETUP COMMANDS:
---------------------
# Create topic
aws sns create-topic --name blissful-admin-alerts --region ap-south-1

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:123456789012:blissful-admin-alerts \
  --protocol email \
  --notification-endpoint admin@example.com

# Confirm subscription (check email)

# Get topic ARN for .env
aws sns list-topics --region ap-south-1

COST MODEL:
-----------
• Per notification: ~$0.50 per million
• SMS: $0.00645 per SMS (India)
• Email (via SES): Free first 62k emails/month

INTEGRATION WITH EMAIL:
-----------------------
SNS can publish to:
• Email (direct)
• SQS (queue)
• Lambda (serverless function)
• HTTP endpoint (webhook)
• Mobile push notifications
"""


# ═══════════════════════════════════════════════════════════════════════════
# QUICK REFERENCE - FUNCTION CALLS
# ═══════════════════════════════════════════════════════════════════════════

QUICK_REFERENCE = """

QUICK REFERENCE - COMMON OPERATIONS
====================================

1. UPLOAD A ROOM IMAGE
from services.s3_service import upload_room_image
url = upload_room_image("local_path.jpg", "room-101")

2. SAVE CUSTOMER SESSION
from services.dynamodb_service import save_session
save_session("sess-id", "user-123", {"cart": [1, 2, 3]})

3. LOG AUDIT EVENT
from services.dynamodb_service import log_audit_event
log_audit_event("user-123", "booking_created", {"booking_id": "123"})

4. GET INSTANCE HEALTH
from services.ec2_service import get_instance_info
info = get_instance_info()

5. VERIFY AWS CREDENTIALS
from services.iam_service import get_caller_identity
identity = get_caller_identity()

6. SEND BOOKING CONFIRMATION
from services.sns_service import send_booking_confirmation
send_booking_confirmation("email", "booking-id", "room", "2026-04-15", "2026-04-17", 5000)

7. SEND FRAUD ALERT
from services.sns_service import send_fraud_alert
send_fraud_alert("booking-id", 0.95, "High-risk user")

"""

print(QUICK_REFERENCE)
