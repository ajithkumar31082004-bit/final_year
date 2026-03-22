"""
Blissful Abodes - AWS S3 Service
Handles image, QR code, and PDF invoice uploads to S3
"""
import os
import boto3
from botocore.exceptions import ClientError

_s3_client = None

def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'ap-south-1')
        )
    return _s3_client

BUCKET = os.environ.get('S3_BUCKET', 'blissful-abodes-media')
REGION = os.environ.get('AWS_REGION', 'ap-south-1')

def is_configured():
    return bool(os.environ.get('AWS_ACCESS_KEY_ID')) and bool(os.environ.get('AWS_SECRET_ACCESS_KEY'))

def upload_file(local_path: str, s3_key: str, public: bool = True) -> str:
    """Upload a local file to S3. Returns the public URL."""
    if not is_configured():
        return local_path  # fallback to local path if S3 not configured
    try:
        extra_args = {'ACL': 'public-read'} if public else {}
        _get_s3().upload_file(local_path, BUCKET, s3_key, ExtraArgs=extra_args)
        return f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{s3_key}"
    except ClientError as e:
        print(f"[S3] Upload failed: {e}")
        return local_path

def upload_invoice(local_path: str, booking_id: str) -> str:
    """Upload a GST invoice PDF to S3."""
    key = f"invoices/{booking_id}.pdf"
    return upload_file(local_path, key, public=False)

def upload_qr(local_path: str, booking_id: str) -> str:
    """Upload a booking QR code image to S3."""
    key = f"qrcodes/{booking_id}.png"
    return upload_file(local_path, key, public=True)

def upload_room_image(local_path: str, room_id: str, index: int = 0) -> str:
    """Upload a room image to S3."""
    ext = os.path.splitext(local_path)[1] or '.jpg'
    key = f"rooms/{room_id}/{index}{ext}"
    return upload_file(local_path, key, public=True)

def get_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for private files (invoices)."""
    if not is_configured():
        return ""
    try:
        return _get_s3().generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET, 'Key': s3_key},
            ExpiresIn=expires_in
        )
    except ClientError:
        return ""
