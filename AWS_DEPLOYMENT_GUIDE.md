# Blissful Abodes — Full AWS Deployment Guide

## Architecture Overview

```
Internet → Route 53 → Load Balancer → EC2 (Flask App)
                                          ↓           ↓           ↓
                                        RDS         S3          SNS
                                      (SQLite→    (Images)   (Emails/SMS)
                                      PostgreSQL)
                                          ↓
                                       Cognito  ←→  OpenAI API
                                    (Auth/Login)   (AI Chatbot)
```

---

## Service 1: EC2 (Hosting the Flask App)

**What it does:** Runs your Python Flask application 24/7 in the cloud.

### Steps:
1. **Launch EC2 Instance**
   - Service: EC2 → Launch Instance
   - AMI: Ubuntu Server 22.04 LTS
   - Instance Type: `t3.small` (2 vCPU, 2GB RAM) — Free Tier eligible: `t2.micro`
   - Storage: 20 GB gp3
   - Security Group rules:
     - Port 22 (SSH) — from your IP only
     - Port 80 (HTTP) — from anywhere
     - Port 443 (HTTPS) — from anywhere
     - Port 5000 (Flask dev, optional)

2. **SSH into the instance and install dependencies:**
```bash
ssh -i "your-key.pem" ubuntu@<EC2-PUBLIC-IP>

# Install Python + Git
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git nginx

# Clone your project
git clone https://github.com/yourusername/blissful-abodes.git
cd blissful-abodes

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# Set environment variables
nano .env
# (paste your .env contents here)
```

3. **Run with Gunicorn (production-grade WSGI server):**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

4. **Configure Nginx as reverse proxy:**
```bash
sudo nano /etc/nginx/sites-available/blissful
```
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/blissful /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

5. **Auto-start with systemd:**
```bash
sudo nano /etc/systemd/system/blissful.service
```
```ini
[Unit]
Description=Blissful Abodes Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/blissful-abodes
EnvironmentFile=/home/ubuntu/blissful-abodes/.env
ExecStart=/home/ubuntu/blissful-abodes/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable blissful
sudo systemctl start blissful
```

---

## Service 2: RDS (Database — PostgreSQL replacing SQLite)

**What it does:** AWS-managed database — auto-backups, scaling, high availability.

### Steps:
1. **Create RDS Instance:**
   - Service: RDS → Create Database
   - Engine: PostgreSQL 15
   - Template: Free Tier
   - DB Instance: `db.t3.micro`
   - DB Name: `blissful_abodes`
   - Username: `admin`, Password: (strong password)

2. **Install psycopg2 in your project:**
```bash
pip install psycopg2-binary
echo "psycopg2-binary" >> requirements.txt
```

3. **Update `models/database.py`** — swap SQLite for PostgreSQL:
```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")  # postgres://user:pass@host:5432/dbname

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn
```

4. **Add to your `.env`:**
```env
DATABASE_URL=postgresql://admin:yourpassword@your-rds-endpoint.rds.amazonaws.com:5432/blissful_abodes
```

---

## Service 3: S3 (Image & File Storage)

**What it does:** Stores room photos, QR codes, and PDF invoices in the cloud instead of locally.

### Steps:
1. **Create S3 Bucket:**
   - Service: S3 → Create Bucket
   - Bucket name: `blissful-abodes-media`
   - Region: `ap-south-1` (Mumbai — closest to Chennai)
   - Uncheck "Block all public access" for images

2. **Install boto3:**
```bash
pip install boto3
echo "boto3" >> requirements.txt
```

3. **Create `services/s3_service.py`:**
```python
import boto3
import os

s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name='ap-south-1'
)
BUCKET = 'blissful-abodes-media'

def upload_file(local_path, s3_key):
    s3.upload_file(local_path, BUCKET, s3_key, ExtraArgs={'ACL': 'public-read'})
    return f"https://{BUCKET}.s3.ap-south-1.amazonaws.com/{s3_key}"

def upload_invoice(local_path, booking_id):
    key = f"invoices/{booking_id}.pdf"
    return upload_file(local_path, key)

def upload_qr(local_path, booking_id):
    key = f"qrcodes/{booking_id}.png"
    return upload_file(local_path, key)
```

4. **Add to `.env`:**
```env
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=your+secret+key+here
AWS_REGION=ap-south-1
S3_BUCKET=blissful-abodes-media
```

5. **Replace local file saves** in `pdf_service.py` and `guest.py`:
```python
from services.s3_service import upload_invoice, upload_qr
# After generating the PDF:
s3_url = upload_invoice(local_pdf_path, booking_id)
```

---

## Service 4: OpenAI API (AI Chatbot) ✅ Already Configured

**What it does:** Powers the Aria Guest Concierge, Manager AI Assistant, and Staff Operations AI.

**Status:** ✅ Already integrated in `ml_models/openai_agent.py` with Gemini fallback.

**For AWS deployment, just ensure your `.env` on EC2 has the key:**
```env
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIzaSy...
```

**Optional — AWS Secrets Manager (more secure):**
```python
import boto3, json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='ap-south-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

secrets = get_secret("blissful-abodes-secrets")
OPENAI_API_KEY = secrets['OPENAI_API_KEY']
```

---

## Service 5: SNS (Notifications — Email & SMS)

**What it does:** Replaces `email_service.py` with AWS SNS for reliable email and SMS alerts to guests and admins.

### Steps:
1. **Create SNS Topics in AWS Console:**
   - `blissful-booking-alerts` (for admin fraud alerts)
   - `blissful-guest-notifications` (for guest booking confirmations)

2. **Install boto3** (already done for S3).

3. **Create `services/sns_service.py`:**
```python
import boto3
import os

sns = boto3.client('sns', region_name='ap-south-1')

ADMIN_TOPIC_ARN = os.environ.get('SNS_ADMIN_TOPIC_ARN')
GUEST_TOPIC_ARN = os.environ.get('SNS_GUEST_TOPIC_ARN')

def send_booking_confirmation_sns(user_email, booking_id, room_number, check_in, check_out):
    """Send booking confirmation via SNS -> SES Email."""
    sns.publish(
        TopicArn=GUEST_TOPIC_ARN,
        Subject=f"Booking Confirmed — {booking_id}",
        Message=f"""
Namaste! Your booking at Blissful Abodes is confirmed.
Booking ID: {booking_id}
Room: {room_number}
Check-in: {check_in} | Check-out: {check_out}

Thank you for choosing us!
        """,
        MessageAttributes={
            'email': {'DataType': 'String', 'StringValue': user_email}
        }
    )

def send_fraud_alert_sns(booking_id, fraud_score, reason):
    """Send fraud alert to admin team via SNS."""
    sns.publish(
        TopicArn=ADMIN_TOPIC_ARN,
        Subject=f"🚨 FRAUD ALERT — Booking {booking_id}",
        Message=f"""
High-risk booking detected!
Booking ID: {booking_id}
Fraud Score: {fraud_score:.2f}
Reason: {reason}

Please review in the Admin Dashboard immediately.
        """
    )
```

4. **Add to `.env`:**
```env
SNS_ADMIN_TOPIC_ARN=arn:aws:sns:ap-south-1:123456789012:blissful-booking-alerts
SNS_GUEST_TOPIC_ARN=arn:aws:sns:ap-south-1:123456789012:blissful-guest-notifications
```

5. **Replace calls** in `routes/guest.py`:
```python
from services.sns_service import send_booking_confirmation_sns, send_fraud_alert_sns
# Replace: send_booking_confirmation(...)
# With:    send_booking_confirmation_sns(...)
```

---

## Service 6: Cognito (Authentication — Replacing Flask Session Login)

**What it does:** Enterprise-grade login with Google/Facebook OAuth, MFA, and JWT tokens.

### Steps:
1. **Create Cognito User Pool:**
   - Service: Cognito → Create User Pool
   - Name: `BlissfulAbodesUsers`
   - Sign-in options: Email
   - MFA: Optional (SMS-based)
   - App Client: `blissful-web-client` (no client secret for web)

2. **Install cognito SDK:**
```bash
pip install boto3 warrant
```

3. **Create `services/cognito_service.py`:**
```python
import boto3
import os

cognito = boto3.client('cognito-idp', region_name='ap-south-1')

USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')

def register_user(email, password, first_name, last_name):
    cognito.sign_up(
        ClientId=CLIENT_ID,
        Username=email,
        Password=password,
        UserAttributes=[
            {'Name': 'email', 'Value': email},
            {'Name': 'given_name', 'Value': first_name},
            {'Name': 'family_name', 'Value': last_name},
        ]
    )

def login_user(email, password):
    response = cognito.initiate_auth(
        ClientId=CLIENT_ID,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={'USERNAME': email, 'PASSWORD': password}
    )
    return response['AuthenticationResult']  # Returns AccessToken, IdToken, RefreshToken

def verify_token(token):
    # Decode and verify JWT token
    import jwt
    # (Use python-jose for full verification with Cognito JWKS)
    return jwt.decode(token, options={"verify_signature": False})
```

4. **Add to `.env`:**
```env
COGNITO_USER_POOL_ID=ap-south-1_XXXXXXXXX
COGNITO_CLIENT_ID=your-cognito-app-client-id
COGNITO_REGION=ap-south-1
```

---

## Cost Estimate (Monthly)

| Service | Tier | Est. Cost |
|---|---|---|
| EC2 `t3.small` | On-Demand | ~$17/month |
| RDS `db.t3.micro` | Free Tier (1yr) | $0 → $15/month |
| S3 Storage | 5 GB | ~$0.12/month |
| SNS | 1M notifications | ~$0.50/month |
| Cognito | First 50,000 users | **Free** |
| OpenAI API | Usage-based | ~$5–20/month |
| **Total** | | **~$23–52/month** |

> 💡 Use **Free Tier** for 12 months with `t2.micro` (EC2) and `db.t3.micro` (RDS) to minimize cost.

---

## Deployment Checklist

- [ ] Launch EC2 instance (Ubuntu 22.04)
- [ ] SSH in, install Python/Nginx/Gunicorn
- [ ] Create RDS PostgreSQL database
- [ ] Update `DATABASE_URL` in `.env`
- [ ] Create S3 bucket, update `services/s3_service.py`
- [ ] Create SNS topics, update `services/sns_service.py`
- [ ] Create Cognito User Pool, update `services/cognito_service.py`
- [ ] Copy `.env` to EC2 with all keys
- [ ] Start Gunicorn + configure Nginx
- [ ] (Optional) Add domain + SSL via ACM + Route 53
