"""
Blissful Abodes - AWS Cognito Authentication Service
Enterprise-grade login with JWT tokens, MFA, and OAuth
"""
import os
import boto3
from botocore.exceptions import ClientError

_cognito_client = None

USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID', '')
REGION = os.environ.get('COGNITO_REGION', os.environ.get('AWS_REGION', 'ap-south-1'))

def _get_cognito():
    global _cognito_client
    if _cognito_client is None:
        _cognito_client = boto3.client(
            'cognito-idp',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=REGION
        )
    return _cognito_client

def is_configured():
    return bool(USER_POOL_ID) and bool(CLIENT_ID)

def register_user(email: str, password: str, first_name: str, last_name: str, role: str = 'guest') -> dict:
    """Register a new user in Cognito User Pool."""
    if not is_configured():
        return {'success': False, 'error': 'Cognito not configured'}
    try:
        _get_cognito().sign_up(
            ClientId=CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'given_name', 'Value': first_name},
                {'Name': 'family_name', 'Value': last_name},
                {'Name': 'custom:role', 'Value': role},
            ]
        )
        return {'success': True}
    except ClientError as e:
        return {'success': False, 'error': str(e)}

def login_user(email: str, password: str) -> dict:
    """Authenticate user with Cognito. Returns JWT tokens on success."""
    if not is_configured():
        return {'success': False, 'error': 'Cognito not configured'}
    try:
        response = _get_cognito().initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': email, 'PASSWORD': password}
        )
        auth = response.get('AuthenticationResult', {})
        return {
            'success': True,
            'access_token': auth.get('AccessToken'),
            'id_token': auth.get('IdToken'),
            'refresh_token': auth.get('RefreshToken'),
            'expires_in': auth.get('ExpiresIn', 3600)
        }
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NotAuthorizedException':
            return {'success': False, 'error': 'Invalid email or password'}
        elif error_code == 'UserNotConfirmedException':
            return {'success': False, 'error': 'Please verify your email first'}
        return {'success': False, 'error': str(e)}

def get_user_from_token(access_token: str) -> dict:
    """Fetch user attributes from a Cognito access token."""
    if not is_configured():
        return {}
    try:
        response = _get_cognito().get_user(AccessToken=access_token)
        attrs = {a['Name']: a['Value'] for a in response.get('UserAttributes', [])}
        return {
            'email': attrs.get('email', ''),
            'first_name': attrs.get('given_name', ''),
            'last_name': attrs.get('family_name', ''),
            'role': attrs.get('custom:role', 'guest'),
            'cognito_sub': attrs.get('sub', '')
        }
    except ClientError:
        return {}

def confirm_signup(email: str, code: str) -> dict:
    """Confirm user registration with the verification code sent to email."""
    if not is_configured():
        return {'success': False, 'error': 'Cognito not configured'}
    try:
        _get_cognito().confirm_sign_up(
            ClientId=CLIENT_ID,
            Username=email,
            ConfirmationCode=code
        )
        return {'success': True}
    except ClientError as e:
        return {'success': False, 'error': str(e)}

def forgot_password(email: str) -> dict:
    """Initiate forgot password flow."""
    if not is_configured():
        return {'success': False}
    try:
        _get_cognito().forgot_password(ClientId=CLIENT_ID, Username=email)
        return {'success': True}
    except ClientError as e:
        return {'success': False, 'error': str(e)}

def reset_password(email: str, code: str, new_password: str) -> dict:
    """Reset password with the code sent to email."""
    if not is_configured():
        return {'success': False}
    try:
        _get_cognito().confirm_forgot_password(
            ClientId=CLIENT_ID,
            Username=email,
            ConfirmationCode=code,
            Password=new_password
        )
        return {'success': True}
    except ClientError as e:
        return {'success': False, 'error': str(e)}

def signout_user(access_token: str) -> bool:
    """Sign out user from all devices."""
    if not is_configured():
        return False
    try:
        _get_cognito().global_sign_out(AccessToken=access_token)
        return True
    except ClientError:
        return False
