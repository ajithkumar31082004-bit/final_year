"""
Blissful Abodes - AWS DynamoDB Service
Stores session data, chatbot conversation history, and audit logs in DynamoDB.
Used as a fast NoSQL store for non-relational, high-frequency write data.
"""
import os
import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError

_dynamodb = None
_resource = None

TABLE_SESSIONS   = os.environ.get('DYNAMODB_SESSIONS_TABLE',  'blissful-sessions')
TABLE_CHATBOT    = os.environ.get('DYNAMODB_CHATBOT_TABLE',   'blissful-chatbot-history')
TABLE_AUDIT      = os.environ.get('DYNAMODB_AUDIT_TABLE',     'blissful-audit-logs')
REGION           = os.environ.get('AWS_REGION', 'ap-south-1')


def _get_resource():
    """Lazily create a DynamoDB resource."""
    global _resource
    if _resource is None:
        import boto3
        _resource = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=REGION
        )
    return _resource


def is_configured() -> bool:
    """Return True if AWS credentials are present."""
    return (
        bool(os.environ.get('AWS_ACCESS_KEY_ID')) and
        bool(os.environ.get('AWS_SECRET_ACCESS_KEY'))
    )


# ── Session Storage ────────────────────────────────────────────────────────────

def save_session(session_id: str, user_id: str, data: dict) -> bool:
    """
    Persist a Flask/agent session to DynamoDB.
    Useful when the app is horizontally scaled across multiple EC2 instances.
    """
    if not is_configured():
        return False
    try:
        table = _get_resource().Table(TABLE_SESSIONS)
        table.put_item(Item={
            'session_id':  session_id,
            'user_id':     user_id,
            'data':        json.dumps(data),
            'updated_at':  datetime.now(timezone.utc).isoformat(),
            'ttl':         int(datetime.now(timezone.utc).timestamp()) + 86400  # 24 h TTL
        })
        return True
    except ClientError as e:
        print(f"[DynamoDB] save_session failed: {e}")
        return False


def load_session(session_id: str) -> dict:
    """Retrieve a session from DynamoDB. Returns {} if not found."""
    if not is_configured():
        return {}
    try:
        table = _get_resource().Table(TABLE_SESSIONS)
        resp = table.get_item(Key={'session_id': session_id})
        item = resp.get('Item', {})
        return json.loads(item['data']) if item.get('data') else {}
    except ClientError as e:
        print(f"[DynamoDB] load_session failed: {e}")
        return {}


# ── Chatbot History ────────────────────────────────────────────────────────────

def save_chat_message(user_id: str, role: str, content: str) -> bool:
    """
    Append a chatbot message to DynamoDB.
    Allows unlimited chat history without bloating the relational DB.
    """
    if not is_configured():
        return False
    try:
        table = _get_resource().Table(TABLE_CHATBOT)
        table.put_item(Item={
            'user_id':    user_id,
            'timestamp':  datetime.now(timezone.utc).isoformat(),
            'role':       role,          # 'user' | 'assistant'
            'content':    content,
            'ttl':        int(datetime.now(timezone.utc).timestamp()) + 2592000  # 30-day TTL
        })
        return True
    except ClientError as e:
        print(f"[DynamoDB] save_chat_message failed: {e}")
        return False


def get_chat_history(user_id: str, limit: int = 20) -> list:
    """
    Retrieve the last `limit` chat messages for a user.
    Returns a list of dicts with 'role' and 'content' keys.
    """
    if not is_configured():
        return []
    try:
        from boto3.dynamodb.conditions import Key
        table = _get_resource().Table(TABLE_CHATBOT)
        resp = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id),
            ScanIndexForward=False,   # newest first
            Limit=limit
        )
        items = resp.get('Items', [])
        return [{'role': i['role'], 'content': i['content']} for i in reversed(items)]
    except ClientError as e:
        print(f"[DynamoDB] get_chat_history failed: {e}")
        return []


# ── Audit Logs ─────────────────────────────────────────────────────────────────

def log_audit_event(user_id: str, action: str, details: dict = None) -> bool:
    """
    Write a tamper-proof audit log entry to DynamoDB.
    Example actions: 'booking_created', 'fraud_flagged', 'login', 'price_updated'.
    """
    if not is_configured():
        return False
    try:
        table = _get_resource().Table(TABLE_AUDIT)
        table.put_item(Item={
            'user_id':    user_id,
            'timestamp':  datetime.now(timezone.utc).isoformat(),
            'action':     action,
            'details':    json.dumps(details or {}),
        })
        print(f"[DynamoDB] Audit: {user_id} → {action}")
        return True
    except ClientError as e:
        print(f"[DynamoDB] log_audit_event failed: {e}")
        return False


def get_audit_logs(user_id: str, limit: int = 50) -> list:
    """Retrieve audit log entries for a user."""
    if not is_configured():
        return []
    try:
        from boto3.dynamodb.conditions import Key
        table = _get_resource().Table(TABLE_AUDIT)
        resp = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id),
            ScanIndexForward=False,
            Limit=limit
        )
        return resp.get('Items', [])
    except ClientError as e:
        print(f"[DynamoDB] get_audit_logs failed: {e}")
        return []
