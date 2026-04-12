# AWS Service Integration Guide for Blissful Abodes

## Overview
This guide provides step-by-step instructions to integrate and configure 5 AWS services with your Blissful Abodes application.

### Services Covered
1. **Amazon S3** - File storage (images, QR codes, invoices)
2. **Amazon DynamoDB** - NoSQL database (sessions, chat history, audit logs)
3. **Amazon EC2** - Cloud compute instance monitoring
4. **AWS IAM** - Identity and access management
5. **Amazon SNS** - Simple notification service (emails, SMS)

---

## Prerequisites
- AWS Account with billing enabled
- AWS CLI installed locally
- IAM user with programmatic access
- Appropriate IAM permissions

---

## Step 1: Create IAM User and Generate Credentials

### 1.1 Create IAM User
1. Go to AWS Console → **IAM** → **Users** → **Create user**
2. Username: `blissful-abodes-app`
3. Select **Security credentials** → **Create access key**
4. Choose **Application running on an AWS compute service** (EC2 later)
5. Keep the credentials safe

### 1.2 Attach Policies to User
Create an inline policy with the following JSON:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::blissful-abodes-media",
                "arn:aws:s3:::blissful-abodes-media/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:UpdateItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:ap-south-1:*:table/blissful-sessions",
                "arn:aws:dynamodb:ap-south-1:*:table/blissful-chatbot-history",
                "arn:aws:dynamodb:ap-south-1:*:table/blissful-audit-logs"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:GetConsoleOutput"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "iam:GetUser",
                "sts:GetCallerIdentity",
                "sts:AssumeRole"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish",
                "sns:Subscribe"
            ],
            "Resource": [
                "arn:aws:sns:ap-south-1:*:blissful-admin-alerts",
                "arn:aws:sns:ap-south-1:*:blissful-guest-notifications"
            ]
        }
    ]
}
```

---

## Step 2: Configure S3 for File Storage

### 2.1 Create S3 Bucket
```bash
aws s3 mb s3://blissful-abodes-media --region ap-south-1
```

### 2.2 Enable Public Read for Images
```bash
aws s3api put-bucket-acl --bucket blissful-abodes-media --acl public-read
```

### 2.3 Configure CORS
```bash
aws s3api put-bucket-cors --bucket blissful-abodes-media --cors-configuration '{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"]
    }
  ]
}'
```

### 2.4 Create Folder Structure
```bash
# No need to create folders in S3, but organize keys by prefix:
# - s3://blissful-abodes-media/images/room-1-bedroom.jpg
# - s3://blissful-abodes-media/invoices/BOOKING-12345.pdf
# - s3://blissful-abodes-media/qrcodes/BOOKING-12345.png
```

---

## Step 3: Set up DynamoDB Tables

### 3.1 Create Sessions Table
```bash
aws dynamodb create-table \
  --table-name blissful-sessions \
  --attribute-definitions AttributeName=session_id,AttributeType=S \
  --key-schema AttributeName=session_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --ttl-specification Enabled=true,AttributeName=ttl \
  --region ap-south-1
```

### 3.2 Create Chatbot History Table
```bash
aws dynamodb create-table \
  --table-name blissful-chatbot-history \
  --attribute-definitions AttributeName=user_id,AttributeType=S \
                          AttributeName=timestamp,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
               AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --ttl-specification Enabled=true,AttributeName=ttl \
  --region ap-south-1
```

### 3.3 Create Audit Logs Table
```bash
aws dynamodb create-table \
  --table-name blissful-audit-logs \
  --attribute-definitions AttributeName=user_id,AttributeType=S \
                          AttributeName=timestamp,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
               AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### 3.4 Verify Tables
```bash
aws dynamodb list-tables --region ap-south-1
```

---

## Step 4: Create IAM Role for EC2

### 4.1 Create Trust Relationship JSON
Save as `trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 4.2 Create Role
```bash
aws iam create-role \
  --role-name blissful-abodes-ec2-role \
  --assume-role-policy-document file://trust-policy.json
```

### 4.3 Attach Policy to Role
```bash
aws iam put-role-policy \
  --role-name blissful-abodes-ec2-role \
  --policy-name blissful-abodes-policy \
  --policy-document file://inline-policy.json
```

### 4.4 Create Instance Profile
```bash
aws iam create-instance-profile \
  --instance-profile-name blissful-abodes-profile

aws iam add-role-to-instance-profile \
  --instance-profile-name blissful-abodes-profile \
  --role-name blissful-abodes-ec2-role
```

---

## Step 5: Set up SNS Topics for Notifications

### 5.1 Create Admin Alerts Topic
```bash
aws sns create-topic \
  --name blissful-admin-alerts \
  --region ap-south-1
```

### 5.2 Create Guest Notifications Topic
```bash
aws sns create-topic \
  --name blissful-guest-notifications \
  --region ap-south-1
```

### 5.3 Subscribe Email (Admin)
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:blissful-admin-alerts \
  --protocol email \
  --notification-endpoint admin@blissfulabodes.com \
  --region ap-south-1
```

### 5.4 Subscribe Email (Guest Notifications)
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:blissful-guest-notifications \
  --protocol email \
  --notification-endpoint support@blissfulabodes.com \
  --region ap-south-1
```

**Note:** Check your email and confirm subscriptions.

---

## Step 6: Configure Environment Variables

Update your `.env` file:

```
# === AWS Core Credentials ===
AWS_ACCESS_KEY_ID=your-access-key-from-iam
AWS_SECRET_ACCESS_KEY=your-secret-access-key-from-iam
AWS_REGION=ap-south-1

# === AWS S3 ===
S3_BUCKET=blissful-abodes-media

# === AWS DynamoDB ===
DYNAMODB_SESSIONS_TABLE=blissful-sessions
DYNAMODB_CHATBOT_TABLE=blissful-chatbot-history
DYNAMODB_AUDIT_TABLE=blissful-audit-logs

# === AWS EC2 ===
EC2_INSTANCE_ID=i-0abc1234def56789
EC2_INSTANCE_TYPE=t2.micro
EC2_PUBLIC_IP=44.208.253.176

# === AWS SNS ===
SNS_ADMIN_TOPIC_ARN=arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:blissful-admin-alerts
SNS_GUEST_TOPIC_ARN=arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:blissful-guest-notifications

# === AWS IAM ===
IAM_INSTANCE_ROLE=blissful-abodes-ec2-role
```

---

## Step 7: Test AWS Service Integration

### 7.1 Install AWS SDK
```bash
pip install boto3 botocore
```

### 7.2 Test Services
```python
# S3 Test
from services.s3_service import upload_file
result = upload_file("test.txt", "test/test.txt")
print(f"S3 Upload: {result}")

# DynamoDB Test
from services.dynamodb_service import save_session, load_session
save_session("test-session", "user1", {"data": "test"})
loaded = load_session("test-session")
print(f"DynamoDB Session: {loaded}")

# EC2 Test
from services.ec2_service import get_instance_info
info = get_instance_info()
print(f"EC2 Instance: {info}")

# IAM Test
from services.iam_service import get_caller_identity
identity = get_caller_identity()
print(f"IAM Identity: {identity}")

# SNS Test
from services.sns_service import send_fraud_alert
send_fraud_alert("BOOKING-123", 0.95, "High-risk user", "guest@example.com")
```

---

## Step 8: Deploy to EC2

### 8.1 Launch EC2 Instance
```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t2.micro \
  --iam-instance-profile Name=blissful-abodes-profile \
  --key-name your-key-pair \
  --security-groups default \
  --region ap-south-1
```

### 8.2 SSH into Instance
```bash
ssh -i your-key.pem ec2-user@YOUR_PUBLIC_IP
```

### 8.3 Clone and Deploy App
```bash
git clone https://github.com/your-repo/blissful-abodes.git
cd blissful-abodes
pip install -r requirements.txt
python app.py
```

---

## Cost Optimization

### Recommended Settings:
- **S3**: Store images in Standard tier, use S3 Intelligent-Tiering
- **DynamoDB**: Use on-demand billing (PAY_PER_REQUEST) for predictable costs
- **EC2**: Use t2.micro (eligible for free tier first year)
- **SNS**: ~$0.50 per million notifications
- **IAM**: Always free

### Estimated Monthly Cost (Low Traffic):
- S3: $1-5 (storage + transfer)
- DynamoDB: $2-10 (pay per request)
- EC2: $10-15 (t2.micro)
- SNS: $1-2 (1M notifications)
- **Total: $15-30/month**

---

## Troubleshooting

### Issue: "Unable to locate credentials"
**Solution**: Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set in `.env`

### Issue: "Access Denied" on S3
**Solution**: Check IAM policy permissions and bucket ownership

### Issue: DynamoDB table not found
**Solution**: Verify table name matches `DYNAMODB_*_TABLE` environment variables

### Issue: SNS publish fails
**Solution**: Verify topic ARN is correct and subscriptions are confirmed

---

## References
- [AWS Documentation](https://docs.aws.amazon.com/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [AWS Best Practices](https://aws.amazon.com/architecture/well-architected/)

---

## Next Steps
1. ✅ Configure AWS services
2. ✅ Set environment variables
3. ✅ Test service integrations
4. ✅ Deploy to EC2
5. Monitor CloudWatch metrics
6. Set up auto-scaling groups
7. Implement CI/CD pipeline

