"""
Blissful Abodes - AWS EC2 Service
Provides EC2 instance health monitoring, metadata retrieval, and
auto-scaling status checks. Used by the admin dashboard to display
live cloud infrastructure information.
"""
import os
from botocore.exceptions import ClientError

_ec2_client = None

REGION          = os.environ.get('AWS_REGION', 'ap-south-1')
INSTANCE_ID     = os.environ.get('EC2_INSTANCE_ID', '')       # e.g. i-0abc1234def56789
INSTANCE_TYPE   = os.environ.get('EC2_INSTANCE_TYPE', 't2.micro')
APP_SERVER_IP   = os.environ.get('EC2_PUBLIC_IP', '44.208.253.176')


def _get_ec2():
    """Lazily create EC2 client."""
    global _ec2_client
    if _ec2_client is None:
        import boto3
        _ec2_client = boto3.client(
            'ec2',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=REGION
        )
    return _ec2_client


def is_configured() -> bool:
    """Return True if AWS credentials are present."""
    return (
        bool(os.environ.get('AWS_ACCESS_KEY_ID')) and
        bool(os.environ.get('AWS_SECRET_ACCESS_KEY'))
    )


# ── Instance Info ──────────────────────────────────────────────────────────────

def get_instance_info(instance_id: str = None) -> dict:
    """
    Retrieve metadata about the EC2 instance running the application.
    Returns instance type, state, public IP, launch time, and AZ.
    """
    instance_id = instance_id or INSTANCE_ID
    if not is_configured() or not instance_id:
        return {
            'instance_id':   instance_id or 'not-configured',
            'instance_type': INSTANCE_TYPE,
            'public_ip':     APP_SERVER_IP,
            'state':         'unknown',
            'region':        REGION,
            'note':          'AWS credentials not configured — showing static values',
        }
    try:
        resp = _get_ec2().describe_instances(InstanceIds=[instance_id])
        reservations = resp.get('Reservations', [])
        if not reservations:
            return {'error': f'Instance {instance_id} not found'}
        instance = reservations[0]['Instances'][0]
        return {
            'instance_id':   instance.get('InstanceId'),
            'instance_type': instance.get('InstanceType'),
            'state':         instance['State']['Name'],
            'public_ip':     instance.get('PublicIpAddress', ''),
            'private_ip':    instance.get('PrivateIpAddress', ''),
            'launch_time':   str(instance.get('LaunchTime', '')),
            'availability_zone': instance.get('Placement', {}).get('AvailabilityZone', ''),
            'region':        REGION,
            'ami_id':        instance.get('ImageId', ''),
            'key_name':      instance.get('KeyName', ''),
        }
    except ClientError as e:
        print(f"[EC2] get_instance_info failed: {e}")
        return {'error': str(e)}


def get_instance_status(instance_id: str = None) -> dict:
    """
    Retrieve the system and instance status checks for the EC2 instance.
    Status checks catch hardware/OS level problems (reachability, disk, network).
    Returns: 'ok', 'impaired', or 'insufficient-data' for each check.
    """
    instance_id = instance_id or INSTANCE_ID
    if not is_configured() or not instance_id:
        return {'system_status': 'ok', 'instance_status': 'ok', 'note': 'Static fallback — AWS not configured'}
    try:
        resp = _get_ec2().describe_instance_status(InstanceIds=[instance_id])
        statuses = resp.get('InstanceStatuses', [])
        if not statuses:
            return {'system_status': 'ok', 'instance_status': 'ok'}
        s = statuses[0]
        return {
            'instance_id':     s.get('InstanceId'),
            'availability_zone': s.get('AvailabilityZone'),
            'instance_state':  s['InstanceState']['Name'],
            'system_status':   s['SystemStatus']['Status'],
            'instance_status': s['InstanceStatus']['Status'],
        }
    except ClientError as e:
        print(f"[EC2] get_instance_status failed: {e}")
        return {'error': str(e)}


# ── Security Groups ────────────────────────────────────────────────────────────

def list_security_groups(instance_id: str = None) -> list:
    """
    Return the security groups attached to the EC2 instance.
    Used by the admin dashboard to show which ports are open.
    """
    instance_id = instance_id or INSTANCE_ID
    if not is_configured() or not instance_id:
        return [
            {'group_id': 'sg-xxxxxxxx', 'group_name': 'blissful-abodes-sg',
             'description': 'Port 22 (SSH), 80 (HTTP), 443 (HTTPS)'}
        ]
    try:
        resp = _get_ec2().describe_instances(InstanceIds=[instance_id])
        reservations = resp.get('Reservations', [])
        if not reservations:
            return []
        instance = reservations[0]['Instances'][0]
        return [
            {'group_id': sg['GroupId'], 'group_name': sg['GroupName']}
            for sg in instance.get('SecurityGroups', [])
        ]
    except ClientError as e:
        print(f"[EC2] list_security_groups failed: {e}")
        return []


# ── Start / Stop (Admin Only) ──────────────────────────────────────────────────

def stop_instance(instance_id: str = None) -> bool:
    """
    Stop the EC2 instance (admin action).
    ⚠️ This will take the application offline. Use with caution.
    """
    instance_id = instance_id or INSTANCE_ID
    if not is_configured() or not instance_id:
        print("[EC2] Cannot stop — not configured.")
        return False
    try:
        _get_ec2().stop_instances(InstanceIds=[instance_id])
        print(f"[EC2] Stop requested for {instance_id}")
        return True
    except ClientError as e:
        print(f"[EC2] stop_instance failed: {e}")
        return False


def start_instance(instance_id: str = None) -> bool:
    """Start a previously stopped EC2 instance."""
    instance_id = instance_id or INSTANCE_ID
    if not is_configured() or not instance_id:
        return False
    try:
        _get_ec2().start_instances(InstanceIds=[instance_id])
        print(f"[EC2] Start requested for {instance_id}")
        return True
    except ClientError as e:
        print(f"[EC2] start_instance failed: {e}")
        return False


# ── Dashboard Summary ──────────────────────────────────────────────────────────

def get_infrastructure_summary() -> dict:
    """
    Return a consolidated infrastructure summary for the admin dashboard.
    Combines instance info, status checks, and security groups.
    Falls back to static values if AWS is not configured.
    """
    info   = get_instance_info()
    status = get_instance_status()
    groups = list_security_groups()

    return {
        'instance':         info,
        'status_checks':    status,
        'security_groups':  groups,
        'region':           REGION,
        'app_url':          f"http://{APP_SERVER_IP}",
        'services_running': ['Flask/Gunicorn', 'Nginx', 'APScheduler', 'ML Models (×5)'],
        'aws_configured':   is_configured(),
    }
