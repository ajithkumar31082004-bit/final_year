"""
Blissful Abodes - AWS IAM Service
Manages IAM role validation and permission checks for the application.
Used to verify that the EC2 instance has the correct IAM roles attached,
and to generate temporary STS credentials for secure cross-service access.
"""
import os
from botocore.exceptions import ClientError

_iam_client = None
_sts_client = None

REGION = os.environ.get('AWS_REGION', 'ap-south-1')

# IAM Role expected to be attached to the EC2 instance
EC2_INSTANCE_ROLE = os.environ.get('IAM_INSTANCE_ROLE', 'blissful-abodes-ec2-role')


def _get_iam():
    """Lazily create IAM client."""
    global _iam_client
    if _iam_client is None:
        import boto3
        _iam_client = boto3.client(
            'iam',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=REGION
        )
    return _iam_client


def _get_sts():
    """Lazily create STS client for temporary credential generation."""
    global _sts_client
    if _sts_client is None:
        import boto3
        _sts_client = boto3.client(
            'sts',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=REGION
        )
    return _sts_client


def is_configured() -> bool:
    """Return True if AWS credentials are available."""
    return (
        bool(os.environ.get('AWS_ACCESS_KEY_ID')) and
        bool(os.environ.get('AWS_SECRET_ACCESS_KEY'))
    )


# ── Identity Verification ──────────────────────────────────────────────────────

def get_caller_identity() -> dict:
    """
    Return the AWS account ID, user ARN, and user ID of the current credentials.
    Useful for verifying what IAM user/role the app is running as.
    """
    if not is_configured():
        return {'error': 'AWS credentials not configured'}
    try:
        resp = _get_sts().get_caller_identity()
        return {
            'account_id': resp.get('Account'),
            'user_id':    resp.get('UserId'),
            'arn':        resp.get('Arn'),
        }
    except ClientError as e:
        print(f"[IAM] get_caller_identity failed: {e}")
        return {'error': str(e)}


# ── Role Management ────────────────────────────────────────────────────────────

def get_role_info(role_name: str = None) -> dict:
    """
    Retrieve details of an IAM role (e.g. the EC2 instance role).
    Returns role ARN, creation date, and attached policy summary.
    """
    role_name = role_name or EC2_INSTANCE_ROLE
    if not is_configured():
        return {'error': 'AWS credentials not configured'}
    try:
        resp = _get_iam().get_role(RoleName=role_name)
        role = resp['Role']
        return {
            'role_name':    role.get('RoleName'),
            'arn':          role.get('Arn'),
            'created_at':   str(role.get('CreateDate')),
            'description':  role.get('Description', ''),
        }
    except ClientError as e:
        print(f"[IAM] get_role_info failed: {e}")
        return {'error': str(e)}


def list_attached_policies(role_name: str = None) -> list:
    """
    List the IAM policies currently attached to the given role.
    Used to confirm that the EC2 role has correct permissions
    (S3, DynamoDB, SNS, CloudWatch, etc.).
    """
    role_name = role_name or EC2_INSTANCE_ROLE
    if not is_configured():
        return []
    try:
        resp = _get_iam().list_attached_role_policies(RoleName=role_name)
        return [
            {'policy_name': p['PolicyName'], 'policy_arn': p['PolicyArn']}
            for p in resp.get('AttachedPolicies', [])
        ]
    except ClientError as e:
        print(f"[IAM] list_attached_policies failed: {e}")
        return []


# ── Temporary Credentials ──────────────────────────────────────────────────────

def assume_role(role_arn: str, session_name: str = 'BlissfulAbodesSession',
                duration_seconds: int = 3600) -> dict:
    """
    Generate temporary STS credentials by assuming an IAM role.
    Use this when the app needs elevated permissions for a specific task
    (e.g., accessing a cross-account S3 bucket for backups).

    Returns: dict with AccessKeyId, SecretAccessKey, SessionToken
    """
    if not is_configured():
        return {'error': 'AWS credentials not configured'}
    try:
        resp = _get_sts().assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=duration_seconds
        )
        creds = resp['Credentials']
        return {
            'access_key_id':     creds['AccessKeyId'],
            'secret_access_key': creds['SecretAccessKey'],
            'session_token':     creds['SessionToken'],
            'expiration':        str(creds['Expiration']),
        }
    except ClientError as e:
        print(f"[IAM] assume_role failed: {e}")
        return {'error': str(e)}


# ── Permission Health Check ────────────────────────────────────────────────────

def check_service_permissions() -> dict:
    """
    Verify that the current IAM user/role has the required permissions
    for all AWS services used by the application.

    Returns a dict of service → bool (True = permission likely OK).
    This is a lightweight check — it only verifies STS identity; for full
    validation, use IAM policy simulation in the AWS Console.
    """
    result = {
        'iam_configured': is_configured(),
        'identity':       None,
        'required_services': [
            'ec2:DescribeInstances',
            's3:PutObject',
            's3:GetObject',
            'sns:Publish',
            'dynamodb:PutItem',
            'dynamodb:GetItem',
            'dynamodb:Query',
            'cloudwatch:PutMetricData',
        ]
    }
    identity = get_caller_identity()
    result['identity'] = identity
    if 'error' not in identity:
        result['sts_verified'] = True
    else:
        result['sts_verified'] = False
    return result
